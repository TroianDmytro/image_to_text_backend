"""
Сервисы для работы с пользователями
"""
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from bson import ObjectId
import math

from app.database import get_database
from app.models.user import UserOut, UserUpdate, UserStats, AdminUserUpdate

def user_to_response(user: Dict[str, Any]) -> UserOut:
    """
    Преобразование объекта пользователя из БД в модель ответа API
    """
    return UserOut(
        id=str(user["_id"]),
        email=user["email"],
        username=user["username"],
        is_premium=user["is_premium"],
        is_admin=user.get("is_admin", False),
        created_at=user["created_at"]
    )

async def get_user_profile(user_id: str) -> UserOut:
    """
    Получение профиля пользователя
    """
    db = get_database()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return user_to_response(user)

async def update_user_profile(user_id: str, user_data: UserUpdate) -> UserOut:
    """
    Обновление профиля пользователя
    """
    db = get_database()
    
    # Проверяем существование пользователя
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Подготавливаем данные для обновления
    update_data = {}
    
    if user_data.email is not None:
        # Проверяем, что email не занят другим пользователем
        existing_user = await db.users.find_one({"email": user_data.email, "_id": {"$ne": ObjectId(user_id)}})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже существует"
            )
        update_data["email"] = user_data.email
    
    if user_data.is_premium is not None:
        update_data["is_premium"] = user_data.is_premium
    
    # Обновляем пользователя
    if update_data:
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
    
    # Получаем обновленного пользователя
    updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    return user_to_response(updated_user)

async def get_users_list(page: int = 1, limit: int = 10) -> Dict[str, Any]:
    """
    Получение списка пользователей с пагинацией для админ-панели
    """
    db = get_database()
    skip = (page - 1) * limit
    
    # Получаем пользователей с пагинацией
    users_cursor = db.users.find().sort("created_at", -1).skip(skip).limit(limit)
    users = []
    
    async for user in users_cursor:
        # Подсчет количества запросов для каждого пользователя
        request_count = await db.ocr_requests.count_documents({"user_id": user["_id"]})
        users.append(UserStats(
            id=str(user["_id"]),
            username=user["username"],
            email=user["email"],
            created_at=user["created_at"],
            is_active=user.get("is_active", True),
            is_premium=user.get("is_premium", False),
            is_admin=user.get("is_admin", False),
            request_count=request_count
        ))
    
    # Общее количество пользователей (для пагинации)
    total_users = await db.users.count_documents({})
    total_pages = math.ceil(total_users / limit)
    
    return {
        "users": users,
        "total": total_users,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }

async def admin_update_user(user_id: str, user_data: AdminUserUpdate) -> Dict[str, Any]:
    """
    Обновление пользователя администратором
    """
    db = get_database()
    
    # Проверяем существование пользователя
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Подготавливаем данные для обновления
    update_data = {}
    
    if user_data.email is not None:
        # Проверяем, что email не занят другим пользователем
        existing_user = await db.users.find_one({"email": user_data.email, "_id": {"$ne": ObjectId(user_id)}})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже существует"
            )
        update_data["email"] = user_data.email
    
    if user_data.is_active is not None:
        update_data["is_active"] = user_data.is_active
    
    if user_data.is_premium is not None:
        update_data["is_premium"] = user_data.is_premium
        
    if user_data.is_admin is not None:
        update_data["is_admin"] = user_data.is_admin
    
    # Обновляем пользователя
    if update_data:
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
    
    # Получаем обновленного пользователя
    updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    return {
        "id": str(updated_user["_id"]),
        "username": updated_user["username"],
        "email": updated_user["email"],
        "is_active": updated_user.get("is_active", True),
        "is_premium": updated_user.get("is_premium", False),
        "is_admin": updated_user.get("is_admin", False),
        "created_at": updated_user["created_at"]
    }

async def admin_delete_user(user_id: str, admin_id: str) -> Dict[str, str]:
    """
    Удаление пользователя администратором
    """
    db = get_database()
    
    # Проверяем существование пользователя
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Проверяем, что администратор не пытается удалить сам себя
    if str(user["_id"]) == admin_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы не можете удалить собственную учетную запись"
        )
    
    # Удаляем пользователя
    await db.users.delete_one({"_id": ObjectId(user_id)})
    
    # Удаляем все связанные с пользователем refresh токены
    await db.refresh_tokens.delete_many({"user_id": ObjectId(user_id)})
    
    # Удаляем или анонимизируем запросы OCR пользователя
    await db.ocr_requests.delete_many({"user_id": ObjectId(user_id)})
    
    return {"detail": "Пользователь успешно удален"}