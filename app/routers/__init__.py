"""
Инициализация роутеров
"""
from fastapi import APIRouter
from app.routers.auth import router as auth_router
from app.routers.ocr import router as ocr_router
from app.routers.admin import router as admin_router

router = APIRouter()

# Подключаем маршруты
router.include_router(auth_router)
router.include_router(ocr_router)
router.include_router(admin_router)