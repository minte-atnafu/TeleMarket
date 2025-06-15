# myapp/utils/telegram_username_mapper.py
TELEGRAM_USERNAME_MAP = {
    # Existing mappings
    "Sami Tech": "samcomptech",
    "Tech Hub": "techhub",
    
    # New mappings (added per your request)
    "EthioBrand®": "ethio_brand_collection",
    "Phone hub📱": "phonehub27",
    "tester": "onetimetester",
    
    # Add more as needed...
}

def get_telegram_username(display_name):
    return TELEGRAM_USERNAME_MAP.get(display_name.strip(), "default_username")  # `.strip()` removes whitespace