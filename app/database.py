"""
Настройка подключения к базе данных
"""
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import MONGODB_URL, DB_NAME

# MongoDB клиент
mongodb_client = None
db = None

async def connect_to_mongodb():
    """
    Подключение к MongoDB
    """
    global mongodb_client, db
    
    print(f"Подключение к MongoDB по URL: {MONGODB_URL}")
    try:
        mongodb_client = AsyncIOMotorClient(MONGODB_URL)
        # Проверка соединения
        await mongodb_client.admin.command('ping')
        print("Успешно подключено к MongoDB")
        db = mongodb_client[DB_NAME]
        
        # Создаем индексы для коллекций
        await db.users.create_index("email", unique=True)
        await db.users.create_index("username", unique=True)
        await db.refresh_tokens.create_index("token", unique=True)
        
        return db
    except Exception as e:
        print(f"Ошибка при подключении к MongoDB: {str(e)}")
        raise e

async def close_mongodb_connection():
    """
    Закрытие соединения с MongoDB
    """
    global mongodb_client
    if mongodb_client:
        mongodb_client.close()
        print("Соединение с MongoDB закрыто")

def get_database():
    """
    Получить объект базы данных
    """
    return db