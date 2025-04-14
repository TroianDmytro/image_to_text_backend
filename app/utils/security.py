"""
Утилиты для безопасности и аутентификации
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from bson import ObjectId

from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import get_database

# Утилиты безопасности
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Получение хеша пароля"""
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> tuple:
    """
    Создание JWT токена доступа
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, expire

async def create_refresh_token(user_id: str) -> tuple:
    """
    Создание refresh токена
    """
    db = get_database()
    token_value = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    refresh_token = {
        "token": token_value,
        "user_id": ObjectId(user_id),
        "expires_at": expires_at,
        "created_at": datetime.utcnow(),
        "revoked": False
    }
    
    await db.refresh_tokens.insert_one(refresh_token)
    
    return token_value, expires_at

async def get_user_by_username(username: str):
    """
    Получение пользователя по имени
    """
    db = get_database()
    return await db.users.find_one({"username": username})

async def get_user_by_email(email: str):
    """
    Получение пользователя по email
    """
    db = get_database()
    return await db.users.find_one({"email": email})

async def authenticate_user(username: str, password: str):
    """
    Аутентификация пользователя
    """
    user = await get_user_by_username(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return False
    return user

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Получение текущего пользователя из токена
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверные учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    user = await get_user_by_username(username)
    if user is None:
        raise credentials_exception
    
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Аккаунт отключен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

async def get_current_active_user(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Проверка активности пользователя
    """
    if not current_user["is_active"]:
        raise HTTPException(status_code=400, detail="Неактивный пользователь")
    return current_user

async def get_current_admin(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Проверка прав администратора
    """
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен. Требуются права администратора",
        )
    return current_user