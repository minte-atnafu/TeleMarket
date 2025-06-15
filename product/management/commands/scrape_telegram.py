import os
import asyncio
import logging
import re
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
import boto3
from botocore.config import Config
from tenacity import retry, stop_after_attempt, wait_exponential
from io import BytesIO
from decouple import config
from django.core.management.base import BaseCommand
from asgiref.sync import sync_to_async
from product.models import Product
from transformers import pipeline, AutoTokenizer
from huggingface_hub import login
import torch
from django.db import transaction, connection
from django.conf import settings
from decimal import Decimal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
api_id = config('TELEGRAM_API_ID')
api_hash = config('TELEGRAM_API_HASH')
phone = config('TELEGRAM_PHONE')
s3_bucket_name = config('S3_BUCKET_NAME', default='telemarket')
telegram_password = config('TELEGRAM_PASSWORD', default='')
model_name = config('HF_MODEL_NAME', default='habrev/telemarket-ner-model')
hf_token = config('HF_API_TOKEN', default=None)

class TelegramScraper:
    def __init__(self):
        # Initialize Hugging Face login if token exists
        if hf_token:
            login(token=hf_token)
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=config('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=config('AWS_SECRET_ACCESS_KEY'),
            region_name=config('AWS_DEFAULT_REGION', default='eu-north-1'),
            config=Config(
                signature_version='s3v4',
                retries={'max_attempts': 3}
            )
        )
        
        self.session_string = config('TELEGRAM_SESSION_STRING', default='')
        self.client = TelegramClient(
            StringSession(self.session_string),
            api_id,
            api_hash
        )
        
        # Initialize NER pipeline with proper authentication
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading model on device: {device}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.ner_pipeline = pipeline(
            "token-classification",
            model=model_name,
            tokenizer=self.tokenizer,
            device=device,
            aggregation_strategy="simple",
            token=hf_token if hf_token else None
        )
        
        # Verify DB connection on startup
        self.verify_db_connection()

    def verify_db_connection(self):
        """Verify connection to Neon database"""
        try:
            connection.ensure_connection()
            logger.info(f"✅ Connected to Neon DB at: {settings.DATABASES['default']['HOST']}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Neon DB: {str(e)}")
            raise

    async def authenticate(self):
        """Connect and authenticate with Telegram"""
        try:
            # Ensure we're connected first
            if not self.client.is_connected():
                await self.client.connect()

            if not await self.client.is_user_authorized():
                logger.info("Starting authentication...")
                await self.client.send_code_request(phone)
                
                if telegram_password:
                    try:
                        await self.client.sign_in(phone=phone, password=telegram_password)
                    except SessionPasswordNeededError:
                        logger.error("2FA password is required but incorrect or not provided")
                        raise
                else:
                    code = input("Enter the code you received: ")
                    await self.client.sign_in(phone=phone, code=code)

                new_session_string = self.client.session.save()
                logger.info(f"Add this to your .env file as TELEGRAM_SESSION_STRING:\n{new_session_string}")
            
            logger.info("Successfully authenticated")
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            await self.client.disconnect()
            raise

    def _preprocess_text(self, text):
        """Clean message text before NER processing while preserving important info"""
        if not text:
            return ""
            
        # Remove emojis but keep basic punctuation and symbols
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F700-\U0001F77F"  # alchemical symbols
            "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0001F251" 
            "]+", flags=re.UNICODE
        )
        text = emoji_pattern.sub(r'', text)
        
        # Normalize whitespace but keep newlines as they might separate product info
        text = re.sub(r'[^\S\n]+', ' ', text).strip()
        
        return text

    async def _predict_ner(self, text):
        """Run NER model prediction"""
        try:
            # Run synchronous model in thread pool
            results = await asyncio.to_thread(
                self.ner_pipeline,
                text
            )
            return results
        except Exception as e:
            logger.error(f"NER prediction failed: {e}")
            return []

    def merge_entities(self, ner_output):
        """Improved entity merging that handles different model output formats"""
        entities = {
            "Product": [],
            "Price": [],
            "Location": []
        }
        
        current_entity = None
        
        for item in ner_output:
            # Handle both dictionary and tuple formats
            if isinstance(item, dict):
                word = item.get('word', '')
                entity = item.get('entity_group', item.get('entity', 'O'))
                score = item.get('score', 0)
            else:
                word, entity = item  # For tuple format
                score = 1.0
            
            # Skip special tokens
            if word in [self.tokenizer.cls_token, self.tokenizer.sep_token, self.tokenizer.pad_token]:
                continue
                
            # Handle subword tokens
            is_subword = word.startswith('##')
            word = word[2:] if is_subword else (' ' + word)
            
            # Map entity types to our expected format
            entity_type = None
            if entity == "LABEL_0" or entity == "LABEL_1":
                entity_type = "Product"
            elif entity == "LABEL_3":
                entity_type = "Price"
            elif entity == "LABEL_4" or entity == "LABEL_5":
                entity_type = "Location"
            
            if entity_type:
                if current_entity and current_entity['type'] == entity_type:
                    # Continue current entity
                    current_entity['text'] += word
                    current_entity['score'] = max(current_entity['score'], score)
                else:
                    # New entity starts
                    if current_entity:
                        entities[current_entity['type']].append(current_entity)
                    current_entity = {
                        'text': word.lstrip(),
                        'type': entity_type,
                        'score': score
                    }
            else:
                # Entity ends
                if current_entity:
                    entities[current_entity['type']].append(current_entity)
                current_entity = None
        
        # Add the last entity if exists
        if current_entity:
            entities[current_entity['type']].append(current_entity)
        
        # Select the highest confidence entity for each type
        final_entities = {}
        for key, values in entities.items():
            if values:
                # Sort by score descending and take the highest
                values.sort(key=lambda x: x['score'], reverse=True)
                final_entities[key] = values[0]['text']
            else:
                final_entities[key] = ""
        
        return final_entities

    def _parse_price(self, price_str):
        """More robust price parsing"""
        if not price_str:
            return None
            
        try:
            # Handle various price formats:
            # 25,000.50 ETB -> 25000.50
            # $100 -> 100
            # 15000 -> 15000
            # 10k -> 10000
            
            # Remove all non-digit characters except decimal point
            price_clean = re.sub(r'[^\d.]', '', price_str.lower())
            
            # Handle 'k' suffix (e.g., 10k = 10000)
            if 'k' in price_str.lower() and '.' not in price_clean:
                price_clean += '000'
            
            # Convert to Decimal
            return Decimal(price_clean) if price_clean else None
        except Exception as e:
            logger.warning(f"Price conversion failed for '{price_str}': {e}")
            return None

    async def process_message(self, message, channel):
        """Process a single Telegram message"""
        media_url = None
        if message.media and hasattr(message.media, 'photo'):
            try:
                file_obj = BytesIO()
                await self.client.download_media(message.media, file=file_obj)
                file_obj.seek(0)
                
                filename = f"{channel.lstrip('@')}_{message.id}.jpg"
                s3_key = f"photos/{filename}"
                
                media_url = await self.upload_to_s3(file_obj, s3_bucket_name, s3_key)
                logger.info(f"Uploaded {filename} to S3")
            except Exception as e:
                logger.error(f"Media processing failed: {e}")
            finally:
                if 'file_obj' in locals():
                    file_obj.close()
                    
        return {
            "id": str(message.id),
            "product_name": "",
            "price": None,
            "username": channel,
            "location": "",
            "media_path": media_url,
            "message": message.text
        }

    async def process_message_with_hf(self, message_data):
        """Enhanced message processing with NER"""
        try:
            if not message_data.get('message'):
                logger.warning(f"No message text for ID {message_data.get('id')}")
                return message_data
                
            # Preprocess text
            clean_text = self._preprocess_text(message_data['message'])
            logger.debug(f"Processing text: {clean_text}")
            
            # Get NER predictions
            hf_response = await self._predict_ner(clean_text)
            logger.debug(f"Raw NER output: {hf_response}")
            
            entities = self.merge_entities(hf_response)
            logger.debug(f"Merged entities: {entities}")
                
            # Parse price
            price = self._parse_price(entities.get('Price', ''))
            
            # Update message data
            message_data.update({
                'product_name': entities.get('Product', '')[:255],
                'price': price,
                'location': entities.get('Location', '')[:255],
                'ner_raw_output': str(hf_response)  # For debugging
            })
            
            logger.info(f"Extracted - Product: {message_data['product_name']}, Price: {message_data['price']}, Location: {message_data['location']}")
            return message_data
            
        except Exception as e:
            logger.error(f"NLP processing failed: {e}", exc_info=True)
            return message_data

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def upload_to_s3(self, file_obj, bucket, key):
        """Upload file to S3"""
        try:
            file_obj.seek(0)
            await sync_to_async(self.s3_client.upload_fileobj)(
                file_obj,
                bucket,
                key
            )
            return f"https://{bucket}.s3.amazonaws.com/{key}"
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            raise

    async def save_to_database(self, message_data):
        """Save data to database using only existing model fields"""
        try:
            # Prepare data for database
            db_data = {
                'id': str(message_data['id']),
                'product_name': message_data.get('product_name', '')[:255],
                'price': Decimal(str(message_data['price'])) if message_data['price'] is not None else None,
                'username': message_data.get('username', '')[:255],
                'location': message_data.get('location', '')[:255],
                'media_path': message_data.get('media_path', '')
            }
            
            # Verify we have required fields
            if not db_data['id']:
                raise ValueError("Missing required field: id")
                
            # Use sync_to_async for database operations
            @sync_to_async
            def _save_product():
                with transaction.atomic():
                    product, created = Product.objects.update_or_create(
                        id=db_data['id'],
                        defaults=db_data
                    )
                    return created
            
            # Save to database
            created = await _save_product()
            logger.info(f"💾 {'Created' if created else 'Updated'} product {db_data['id']}")
            return True
                
        except Exception as e:
            logger.error(f"💥 Database save failed for {message_data.get('id')}: {str(e)}", exc_info=True)
            return False

    async def run_scraper(self):
        """Main scraping loop"""
        try:
            # Connect and authenticate
            if not self.client.is_connected():
                await self.client.connect()
            
            if not await self.authenticate():
                raise RuntimeError("Authentication failed")

            # Setup message handler
            @self.client.on(events.NewMessage(chats=['@ethio_brand_collection', '@samcomptech', '@onetimetester']))
            async def handler(event):
                try:
                    logger.info(f"New message received: {event.message.text}")
                    
                    message_data = await self.process_message(event.message, event.chat.username)
                    message_data = await self.process_message_with_hf(message_data)
                    
                    # Debug output before saving
                    logger.info(f"Processed data: {message_data}")
                    
                    success = await self.save_to_database(message_data)
                    logger.info(f"Processed message {message_data['id']} - {'Success' if success else 'Failed'}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)

            logger.info("🚀 Scraper started successfully")
            await self.client.run_until_disconnected()

        except Exception as e:
            logger.error(f"Scraper failed: {e}")
            raise
        finally:
            if self.client.is_connected():
                await self.client.disconnect()

class Command(BaseCommand):
    help = 'Telegram scraper with local NER model integration'

    def handle(self, *args, **options):
        scraper = TelegramScraper()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(scraper.run_scraper())
        except KeyboardInterrupt:
            logger.info("Scraper stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            loop.close()