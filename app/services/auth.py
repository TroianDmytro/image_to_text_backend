"""
Сервисы аутентификации
"""
from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import HTTPException, status
from app.database import get_database
from app.utils.security import (
    create_access_token, 
    create_refresh_token,
    authenticate_user,
    get_password_hash
)
from app.models.user import UserCreate, UserOut
from app.models.token import Token
from app.config import ACCESS_TOKEN_EXPIRE_MINUTES
from bson import ObjectId

async def register_user(user: UserCreate) -> UserOut:
    """
    Регистрация нового пользователя
    """
    db = get_database()
    
    # Проверяем, существует ли пользователь с таким email
    existing_email = await db.users.find_one({"email": user.email})
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Пользователь с таким email уже существует"
        )
    
    # Проверяем, существует ли пользователь с таким именем
    existing_username = await db.users.find_one({"username": user.username})
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Пользователь с таким именем уже существует"
        )
    
    # Создаем нового пользователя
    hashed_password = get_password_hash(user.password)
    user_data = {
        "email": user.email,
        "username": user.username,
        "hashed_password": hashed_password,
        "is_active": True,
        "is_premium": False,
        "is_admin": False,
        "created_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_data)
    user_data["_id"] = result.inserted_id
    
    # Преобразуем в модель ответа
    return UserOut(
        id=str(user_data["_id"]),
        email=user_data["email"],
        username=user_data["username"],
        is_premium=user_data["is_premium"],
        is_admin=user_data["is_admin"],
        created_at=user_data["created_at"]
    )

async def login_user(username: str, password: str) -> Token:
    """
    Аутентификация пользователя и создание токенов
    """
    user = await authenticate_user(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Создаем access token
    access_token, access_token_expires = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Создаем refresh token
    refresh_token, refresh_token_expires = await create_refresh_token(str(user["_id"]))
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_at=access_token_expires
    )

async def refresh_access_token(refresh_token: str) -> Token:
    """
    Обновление токена доступа
    """
    db = get_database()
    
    # Проверяем refresh token
    token_doc = await db.refresh_tokens.find_one({
        "token": refresh_token,
        "revoked": False,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if not token_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или истекший refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Получаем пользователя
    user = await db.users.find_one({"_id": token_doc["user_id"]})
    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или неактивен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Создаем новый access token
    access_token, access_token_expires = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Создаем новый refresh token
    new_refresh_token, refresh_token_expires = await create_refresh_token(str(user["_id"]))
    
    # Отзываем старый refresh token
    await db.refresh_tokens.update_one(
        {"_id": token_doc["_id"]},
        {"$set": {"revoked": True}}
    )
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_at=access_token_expires
    )

async def logout(refresh_token: str) -> Dict[str, str]:
    """
    Выход из системы (отзыв refresh токена)
    """
    db = get_database()
    
    # Находим и отзываем refresh token
    result = await db.refresh_tokens.update_one(
        {"token": refresh_token, "revoked": False},
        {"$set": {"revoked": True}}
    )
    
    return {"detail": "Успешный выход из системы"}