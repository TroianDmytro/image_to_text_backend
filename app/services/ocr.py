"""
Сервисы для OCR функциональности
"""
import io
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List
from fastapi import HTTPException, status, UploadFile
from PIL import Image
import numpy as np
from bson import ObjectId

from app.database import get_database
from app.utils.image import preprocess_image, perform_ocr
from app.models.ocr import LanguageType, OcrResult, OcrStatistics, OcrResultRegion
from app.config import ALLOWED_IMAGE_FORMATS, STANDARD_USER_DAILY_REQUEST_LIMIT, STANDARD_USER_HISTORY_LIMIT

async def check_user_request_limit(user_id: str, is_premium: bool) -> None:
    """
    Проверка лимита запросов для пользователя
    """
    if not is_premium:
        db = get_database()
        day_ago = datetime.utcnow() - timedelta(days=1)
        
        requests_count = await db.ocr_requests.count_documents({
            "user_id": ObjectId(user_id),
            "created_at": {"$gt": day_ago}
        })
        
        if requests_count >= STANDARD_USER_DAILY_REQUEST_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Превышен лимит запросов. Обновите аккаунт до Premium для снятия ограничений."
            )

async def extract_text(
    file: UploadFile,
    language: LanguageType,
    preprocess: bool,
    detail: bool,
    user_id: str,
    is_premium: bool
) -> OcrResult:
    """
    Извлечение текста из изображения
    """
    # Проверка лимита запросов
    await check_user_request_limit(user_id, is_premium)
    
    # Проверка типа файла
    content_type = file.content_type or ""
    
    if content_type not in ALLOWED_IMAGE_FORMATS:
        raise HTTPException(
            status_code=400, 
            detail=f"Неподдерживаемый формат файла. Поддерживаемые форматы: {', '.join(ALLOWED_IMAGE_FORMATS)}"
        )
    
    try:
        # Чтение файла
        content = await file.read()
        image = Image.open(io.BytesIO(content)).convert("RGB")
        
        # Предобработка изображения при необходимости
        if preprocess:
            image = preprocess_image(image)
        
        # Преобразование в numpy array для EasyOCR
        img_np = np.array(image)
        
        # Определение языков для распознавания
        lang_map = {
            LanguageType.ru: ['ru'],
            LanguageType.en: ['en'],
            LanguageType.ru_en: ['ru', 'en'],
            LanguageType.en_ru: ['en', 'ru']
        }
        
        # Распознавание текста
        languages = lang_map.get(language, ['en', 'ru'])
        result = perform_ocr(img_np, languages)
        
        # Формируем ответ
        if detail:
            # Детальный ответ со всеми найденными текстовыми областями
            text_regions = []
            for detection in result:
                bbox, text, confidence = detection
                text_regions.append(OcrResultRegion(
                    bbox=bbox,
                    text=text,
                    confidence=float(confidence)
                ))
            
            # Объединяем весь текст в один
            full_text = " ".join([region.text for region in text_regions])
            
            response = OcrResult(
                text=full_text,
                regions=text_regions,
                model_used=f"EasyOCR ({','.join(languages)})"
            )
        else:
            # Простой ответ только с текстом
            full_text = " ".join([detection[1] for detection in result])
            response = OcrResult(
                text=full_text,
                model_used=f"EasyOCR ({','.join(languages)})"
            )
        
        # Сохраняем запрос в БД
        await save_ocr_request(
            user_id=user_id,
            language=language.value,
            preprocess=preprocess,
            detail=detail,
            result_text=full_text
        )
        
        return response
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке изображения: {str(e)}")

async def save_ocr_request(user_id: str, language: str, preprocess: bool, detail: bool, result_text: str) -> None:
    """
    Сохранение запроса OCR в базу данных
    """
    db = get_database()
    ocr_request = {
        "user_id": ObjectId(user_id),
        "language": language,
        "preprocess": preprocess,
        "detail": detail,
        "result_text": result_text,
        "created_at": datetime.utcnow()
    }
    
    await db.ocr_requests.insert_one(ocr_request)

async def get_user_ocr_history(user_id: str, is_premium: bool, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Получение истории OCR запросов пользователя
    """
    db = get_database()
    
    # Ограничиваем максимальное количество записей
    if limit > 100:
        limit = 100
    
    # Для премиум-пользователей нет ограничения на количество записей в истории
    # Для обычных пользователей возвращаем только последние записи
    if not is_premium:
        limit = min(limit, STANDARD_USER_HISTORY_LIMIT)
    
    # Получаем записи из базы данных
    cursor = db.ocr_requests.find(
        {"user_id": ObjectId(user_id)}
    ).sort("created_at", -1).limit(limit)
    
    # Преобразуем документы в список
    result = []
    async for doc in cursor:
        result.append({
            "id": str(doc["_id"]),
            "language": doc["language"],
            "preprocess": doc["preprocess"],
            "detail": doc["detail"],
            "result_text": doc["result_text"],
            "created_at": doc["created_at"].isoformat()
        })
    
    return result

async def get_ocr_statistics(
    page: int = 1, 
    limit: int = 10, 
    date_filter: str = None, 
    language: str = None
) -> OcrStatistics:
    """
    Получение статистики OCR для админ-панели
    """
    db = get_database()
    
    # Подготовка фильтров
    filter_query = {}
    
    if date_filter:
        now = datetime.utcnow()
        if date_filter == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            filter_query["created_at"] = {"$gte": start_date}
        elif date_filter == "week":
            start_date = now - timedelta(days=7)
            filter_query["created_at"] = {"$gte": start_date}
        elif date_filter == "month":
            start_date = now - timedelta(days=30)
            filter_query["created_at"] = {"$gte": start_date}
    
    if language:
        filter_query["language"] = language
    
    # Получение общей статистики
    total_requests = await db.ocr_requests.count_documents({})
    
    # Количество запросов сегодня
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    requests_today = await db.ocr_requests.count_documents({"created_at": {"$gte": today}})
    
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
    
    # Топ пользователей по количеству запросов
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
                "count": {"$sum": 1}
            }
        },
        {
            "$sort": {"count": -1}
        },
        {
            "$limit": 10
        }
    ]
    
    top_users = []
    async for doc in db.ocr_requests.aggregate(pipeline):
        top_users.append({
            "username": doc["username"],
            "count": doc["count"]
        })
    
    # Пагинация для списка запросов
    skip = (page - 1) * limit
    
    # Получение списка запросов с пользовательской информацией
    pipeline = [
        {
            "$match": filter_query
        },
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
            "$sort": {"created_at": -1}
        },
        {
            "$skip": skip
        },
        {
            "$limit": limit
        }
    ]
    
    requests = []
    async for doc in db.ocr_requests.aggregate(pipeline):
        requests.append({
            "id": str(doc["_id"]),
            "user_id": str(doc["user_id"]),
            "username": doc["user"]["username"],
            "language": doc["language"],
            "preprocess": doc["preprocess"],
            "detail": doc["detail"],
            "result_text": doc["result_text"],
            "created_at": doc["created_at"]
        })
    
    # Общее количество запросов с учетом фильтров (для пагинации)
    total_filtered_requests = await db.ocr_requests.count_documents(filter_query)
    total_pages = math.ceil(total_filtered_requests / limit)
    
    return OcrStatistics(
        total_requests=total_requests,
        requests_today=requests_today,
        requests_by_day=requests_by_day,
        top_users=top_users,
        language_distribution=language_distribution,
        requests=requests,
        total_pages=total_pages
    )