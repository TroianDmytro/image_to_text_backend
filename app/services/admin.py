"""
Сервисы для администрирования
"""
from datetime import datetime, timedelta
from typing import Dict, Any
from bson import ObjectId

from app.database import get_database
from app.models.admin import DashboardStats, SystemSettings
from app.models.user import UserStats

async def get_dashboard_stats() -> DashboardStats:
    """
    Получение статистики для главной страницы админ-панели
    """
    db = get_database()
    
    # Общее количество пользователей
    total_users = await db.users.count_documents({})
    
    # Количество премиум пользователей
    premium_users = await db.users.count_documents({"is_premium": True})
    
    # Общее количество запросов
    total_requests = await db.ocr_requests.count_documents({})
    
    # Количество запросов сегодня
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    requests_today = await db.ocr_requests.count_documents({"created_at": {"$gte": today}})
    
    # Последние зарегистрированные пользователи
    recent_users_cursor = db.users.find().sort("created_at", -1).limit(10)
    recent_users = []
    
    async for user in recent_users_cursor:
        # Подсчет количества запросов для каждого пользователя
        request_count = await db.ocr_requests.count_documents({"user_id": user["_id"]})
        recent_users.append(UserStats(
            id=str(user["_id"]),
            username=user["username"],
            email=user["email"],
            created_at=user["created_at"],
            is_premium=user["is_premium"],
            is_admin=user.get("is_admin", False),
            is_active=user.get("is_active", True),
            request_count=request_count
        ))
    
    # Количество запросов по дням (за последние 30 дней)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    pipeline = [
        {
            "$match": {
                "created_at": {"$gte": thirty_days_ago}
            }
        },
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"},
                    "day": {"$dayOfMonth": "$created_at"}
                },
                "count": {"$sum": 1},
                "date": {"$first": "$created_at"}
            }
        },
        {
            "$sort": {"date": 1}
        }
    ]
    
    requests_by_day = []
    async for doc in db.ocr_requests.aggregate(pipeline):
        requests_by_day.append({
            "date": doc["date"].isoformat(),
            "count": doc["count"]
        })
    
    # Распределение по языкам
    pipeline = [
        {
            "$group": {
                "_id": "$language",
                "count": {"$sum": 1}
            }
        },
        {
            "$sort": {"count": -1}
        }
    ]
    
    language_distribution = []
    async for doc in db.ocr_requests.aggregate(pipeline):
        language_distribution.append({
            "language": doc["_id"],
            "count": doc["count"]
        })
    
    # Активность пользователей (топ-10)
    pipeline = [
        {
            "$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "_id",
                "as": "user"
            }
        },
        {
            "$unwind": "$user"
        },
        {
            "$group": {
                "_id": "$user_id",
                "username": {"$first": "$user.username"},
                "requests": {"$sum": 1}
            }
        },
        {
            "$sort": {"requests": -1}
        },
        {
            "$limit": 10
        }
    ]
    
    user_activity = []
    async for doc in db.ocr_requests.aggregate(pipeline):
        user_activity.append({
            "username": doc["username"],
            "requests": doc["requests"]
        })
    
    return DashboardStats(
        totalUsers=total_users,
        premiumUsers=premium_users,
        totalRequests=total_requests,
        requestsToday=requests_today,
        recentUsers=recent_users,
        requestsByDay=requests_by_day,
        languageDistribution=language_distribution,
        userActivity=user_activity
    )

async def get_system_settings() -> SystemSettings:
    """
    Получение системных настроек
    """
    db = get_database()
    
    # Получаем настройки из коллекции settings или используем значения по умолчанию
    settings = await db.settings.find_one({"_id": "system_settings"})
    
    if not settings:
        # Если настройки не найдены, используем значения по умолчанию
        default_settings = SystemSettings(
            request_limit=10,
            default_language="ru+en",
            preprocess_by_default=True,
            admin_email="admin@example.com",
            maintenance_mode=False,
            max_file_size=5
        )
        
        # Создаем запись с настройками по умолчанию
        await db.settings.insert_one({
            "_id": "system_settings",
            **default_settings.dict()
        })
        
        return default_settings
    
    # Удаляем поле _id из результата
    settings.pop("_id", None)
    
    return SystemSettings(**settings)

async def update_system_settings(settings: SystemSettings) -> SystemSettings:
    """
    Обновление системных настроек
    """
    db = get_database()
    
    # Обновляем настройки в базе данных
    await db.settings.update_one(
        {"_id": "system_settings"},
        {"$set": settings.dict()},
        upsert=True
    )
    
    return settings