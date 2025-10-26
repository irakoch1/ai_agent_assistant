import os
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()


class Config:
    # TelegramGBIB YF HECCRJV
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    if DATABASE_URL:
        # Разбор строки подключения для Render
        db_url = urlparse(DATABASE_URL)
        DB_HOST = db_url.hostname
        DB_PORT = db_url.port
        DB_NAME = db_url.path[1:]  # Убираем начальный '/'
        DB_USER = db_url.username
        DB_PASSWORD = db_url.password
    else:
        # Параметры для локальной разработки
        DB_HOST = os.getenv("DB_HOST")
        DB_PORT = os.getenv("DB_PORT", 5432)
        DB_NAME = os.getenv("DB_NAME")
        DB_USER = os.getenv("DB_USER")
        DB_PASSWORD = os.getenv("DB_PASSWORD")

    # LLM Service
    LLM_API_KEY = os.getenv("LLM_API_KEY")
    LLM_API_URL = os.getenv(
        "LLM_API_URL", "https://api.deepseek.com/v1/chat/completions"
    )
    LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

    # Настройки планировщика уведомлений
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
