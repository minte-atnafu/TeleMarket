import asyncio
import os
import logging
import pandas as pd
import re
import torch
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import MemorySession
from transformers import AutoModelForTokenClassification, AutoTokenizer
import boto3
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential
from io import BytesIO
import shutil

from django.core.management.base import BaseCommand
from django.utils import timezone
from base.models import Product  # Adjust if your model is elsewhere

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

os.environ["HF_HOME"] = "/tmp/huggingface_cache"
os.environ["HUGGINGFACE_HUB_CACHE"] = "/tmp/huggingface_cache"
cache_dir = os.environ["HF_HOME"]

try:
    shutil.rmtree(cache_dir, ignore_errors=True)
    os.makedirs(cache_dir, exist_ok=True)
except Exception as e:
    logging.warning(f"Could not clean cache directory {cache_dir}: {e}")

api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')
phone = os.getenv('TELEGRAM_PHONE')
s3_bucket_name = os.getenv('S3_BUCKET_NAME', 'telemarket')

if not all([api_id, api_hash, phone]):
    logging.error("Missing required Telegram credentials (TELEGRAM_API_ID, TELEGRAM_API_HASH, or TELEGRAM_PHONE)")
    raise ValueError("Telegram credentials not set in environment variables")

try:
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_DEFAULT_REGION', 'eu-north-1')
    )
    logging.info(f"Attempting to access S3 bucket: {s3_bucket_name}")
    s3_client.head_bucket(Bucket=s3_bucket_name)
    logging.info(f"Successfully connected to S3 bucket: {s3_bucket_name}")
except ClientError as e:
    error_code = e.response['Error']['Code']
    error_message = e.response['Error']['Message']
    logging.error(f"Error connecting to S3: {error_code} - {error_message}")
    raise Exception(f"S3 connection failed: {error_code} - {error_message}")
except Exception as e:
    logging.error(f"Failed to initialize S3 client: {e}")
    raise

client = TelegramClient(MemorySession(), api_id, api_hash)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def upload_to_s3(file_obj, bucket, key):
    s3_client.upload_fileobj(file_obj, bucket, key)

async def process_message(message, channel):
    media_path = None
    try:
        if message.media and hasattr(message.media, 'photo'):
            filename = f"{channel.lstrip('@')}_{message.id}.jpg"
            s3_key = f"photos/{filename}"
            file_obj = BytesIO()
            await client.download_media(message.media, file=file_obj)
            file_obj.seek(0)
            try:
                upload_to_s3(file_obj, s3_bucket_name, s3_key)
                media_path = f"s3://{s3_bucket_name}/{s3_key}"
                logging.info(f"Uploaded {filename} to {media_path}")
            except Exception as e:
                logging.error(f"Error uploading {filename} to S3: {e}")
                media_path = None
            finally:
                file_obj.close()
    except Exception as e:
        logging.error(f"Error processing media for message {message.id} in {channel}: {e}")
        media_path = None

    return {
        "Channel_Username": channel,
        "Message_ID": message.id,
        "Message": message.message if message.message else "",
        "Date": message.date,
        "Media_Path": media_path
    }

def preprocess_data(df):
    df = df[df['Message'].str.strip() != '']
    def remove_emojis(text):
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F700-\U0001F77F"
            "\U0001F780-\U0001F7FF"
            "\U0001F800-\U0001F8FF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE,
        )
        return emoji_pattern.sub(r'', text)
    df['Message'] = df['Message'].apply(remove_emojis)
    return df

def apply_ner_model(df, model_path):
    try:
        model = AutoModelForTokenClassification.from_pretrained(model_path, cache_dir=cache_dir)
        tokenizer = AutoTokenizer.from_pretrained(model_path, cache_dir=cache_dir)
    except Exception as e:
        logging.error(f"Error loading NER model: {e}")
        return df
    def predict_ner(sentence):
        try:
            inputs = tokenizer(sentence, return_tensors="pt", truncation=True, padding=True, is_split_into_words=False)
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits
            predictions = torch.argmax(logits, dim=2)
            tokens = tokenizer.convert_ids_to_tokens(inputs['input_ids'][0])
            ner_tags = ['B-Product', 'I-Product', 'B-PRICE', 'I-PRICE', 'B-LOC', 'I-LOC', 'O']
            extracted_entities = []
            for i, token in enumerate(tokens):
                if token in tokenizer.special_tokens_map.values():
                    continue
                label_idx = predictions[0][i].item()
                label = ner_tags[label_idx] if label_idx < len(ner_tags) else 'O'
                extracted_entities.append((token, label))
            return extracted_entities
        except Exception as e:
            logging.error(f"Error processing NER for sentence '{sentence}': {e}")
            return []
    df['NER_Output'] = df['Message'].apply(predict_ner)
    return df

def merge_entities(ner_output):
    extracted_entities = {"Product": [], "Price": [], "Location": []}
    current_entity = {"Product": "", "Price": "", "Location": ""}
    current_label = None
    ner_tags = {
        'B-Product': 'Product', 'I-Product': 'Product',
        'B-PRICE': 'Price', 'I-PRICE': 'Price',
        'B-LOC': 'Location', 'I-LOC': 'Location',
        'O': None
    }
    for token, label in ner_output:
        entity_type = ner_tags.get(label)
        if entity_type:
            if current_label == entity_type:
                current_entity[current_label] += " " + token
            else:
                if current_label and current_entity[current_label]:
                    extracted_entities[current_label].append(current_entity[current_label].strip())
                current_label = entity_type
                current_entity[current_label] = token
        else:
            if current_label and current_entity[current_label]:
                extracted_entities[current_label].append(current_entity[current_label].strip())
            current_label = None
    if current_label and current_entity[current_label]:
        extracted_entities[current_label].append(current_entity[current_label].strip())
    return {key: " ".join(value) for key, value in extracted_entities.items()}

def save_to_postgres(row):
    try:
        Product.objects.create(
            channel_username=row["Channel_Username"],
            message_id=row["Message_ID"],
            message=row["Message"],
            date=row["Date"] if row["Date"] else timezone.now(),
            media_path=row["Media_Path"],
            product=row["Product"],
            price=row["Price"],
            location=row["Location"],
        )
        logging.info(f"Saved message {row['Message_ID']} from {row['Channel_Username']} to Postgres")
    except Exception as e:
        logging.error(f"Error saving to Postgres: {e}")

class Command(BaseCommand):
    help = 'Scrape Telegram, preprocess, run NER, upload to S3, and save to Postgres'

    def handle(self, *args, **options):
        asyncio.run(self.main())

    async def main(self):
        channels = ['@ethio_brand_collection', '@samcomptech', '@phonehub27', '@onetimetester']
        model_path = os.getenv('NER_MODEL_PATH', 'habrev/telemarket-ner-model')

        @client.on(events.NewMessage(chats=channels))
        async def handler(event):
            channel = event.chat.username
            message = event.message
            logging.info(f"New message in {channel}: {message.id}")
            try:
                data = await process_message(message, channel)
                df = pd.DataFrame([data])
                df = preprocess_data(df)
                if df.empty:
                    logging.warning(f"No valid data after preprocessing for message {message.id} in {channel}")
                    return
                df = apply_ner_model(df, model_path)
                df["Product"] = ""
                df["Price"] = ""
                df["Location"] = ""
                for index, row in df.iterrows():
                    extracted = merge_entities(row["NER_Output"])
                    df.at[index, "Product"] = extracted["Product"]
                    df.at[index, "Price"] = extracted["Price"]
                    df.at[index, "Location"] = extracted["Location"]
                    save_to_postgres(df.loc[index])
                logging.info(f"Processed and saved message {message.id} from {channel}")
            except Exception as e:
                logging.error(f"Error processing message {message.id} in {channel}: {e}")

        try:
            password = os.getenv('TELEGRAM_PASSWORD')
            await client.start(phone=phone, password=password)
            logging.info("Listening for new messages...")
            await client.run_until_disconnected()
        except SessionPasswordNeededError:
            logging.error("Two-factor authentication required. Please provide TELEGRAM_PASSWORD in environment variables.")
            raise RuntimeError("Two-factor authentication requires TELEGRAM_PASSWORD.")
        except Exception as e:
            logging.error(f"Error starting client: {e}")
            raise
