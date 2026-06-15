import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API Configuration
try:
    API_ID = int(os.getenv('API_ID', 0))
except ValueError:
    API_ID = 0

API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

# Database Configuration
DB_PATH = os.getenv('DB_PATH', 'data/jaseb.db')

# Admin Configuration
try:
    ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
except ValueError:
    ADMIN_ID = 0

# KlikQRIS Payment Gateway Configuration
KLIKQRIS_API_KEY = os.getenv('KLIKQRIS_API_KEY', '')
KLIKQRIS_MERCHANT_ID = os.getenv('KLIKQRIS_MERCHANT_ID', '')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '') # URL untuk menerima notifikasi pembayaran sukses
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '@geunidk')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '@Geun_ID')
BOT_USERNAME = "GeunID_bot"
MINI_APP_URL = os.getenv('MINI_APP_URL', 'https://geunidjaseb.vercel.app')


