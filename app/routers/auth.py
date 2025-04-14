"""
Маршруты аутентификации
"""
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.models.user import UserCreate, UserOut
from app.models.token import Token, RefreshTokenRequest
from app.services.auth import register_user, login_user, refresh_access_token, logout
from app.utils.security import get_current_active_user

router = APIRouter(tags=["Аутентификация"])

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    """
    Регистрация нового пользователя
    """
    return await register_user(user)

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Вход в систему
    """
    return await login_user(form_data.username, form_data.password)

@router.post("/refresh-token", response_model=Token)
async def refresh_token(request: RefreshTokenRequest):
    """
    Обновление токена
    """
    return await refresh_access_token(request.refresh_token)

@router.post("/logout")
async def logout_user(request: RefreshTokenRequest):
    """
    Выход из системы
    """
    return await logout(request.refresh_token)

@router.get("/users/me", response_model=UserOut)
async def read_users_me(current_user: dict = Depends(get_current_active_user)):
    """
    Получение информации о текущем пользователе
    """
    return UserOut(
        id=str(current_user["_id"]),
        email=current_user["email"],
        username=current_user["username"],
        is_premium=current_user["is_premium"],
        is_admin=current_user.get("is_admin", False),
        created_at=current_user["created_at"]
    )