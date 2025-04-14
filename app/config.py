"""
Конфигурация приложения
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройки JWT
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("Отсутствует SECRET_KEY в .env файле")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Настройки MongoDB
MONGODB_URL = os.getenv("MONGODB_URL")
if not MONGODB_URL:
    raise ValueError("Отсутствует MONGODB_URL в .env файле")

DB_NAME = "ocr_db"

# Лимиты для обычных пользователей
STANDARD_USER_DAILY_REQUEST_LIMIT = 10
STANDARD_USER_HISTORY_LIMIT = 30

# CORS настройки
CORS_ORIGINS = [
    "http://localhost:3000",  # Адрес React приложения
]

# Настройки приложения
APP_TITLE = "OCR API"
APP_DESCRIPTION = "API для распознавания текста с изображений"
APP_VERSION = "1.0.0"

# Настройки изображений
ALLOWED_IMAGE_FORMATS = ["image/png", "image/jpeg", "image/jpg"]
DEFAULT_OCR_LANGUAGES = ['en', 'ru']