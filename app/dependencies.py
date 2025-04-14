"""
Зависимости FastAPI
"""
from fastapi import Depends
from app.utils.security import get_current_user, get_current_active_user, get_current_admin
from app.database import get_database
from app.utils.image import get_ocr_reader

# Экспортируем зависимости для использования в маршрутах
__all__ = [
    "get_current_user",
    "get_current_active_user",
    "get_current_admin",
    "get_database",
    "get_ocr_reader"
]