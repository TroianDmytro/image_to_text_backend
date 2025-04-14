"""
Основной файл приложения FastAPI
"""
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import CORS_ORIGINS, APP_TITLE, APP_DESCRIPTION, APP_VERSION
from app.database import connect_to_mongodb, close_mongodb_connection
from app.utils.image import init_ocr_reader
from app.routers import router

# Инициализация FastAPI
app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение маршрутов
app.include_router(router)

@app.on_event("startup")
async def startup():
    """
    Действия при запуске приложения
    """
    # Подключение к MongoDB
    await connect_to_mongodb()
    
    # Инициализация EasyOCR
    init_ocr_reader()

@app.on_event("shutdown")
async def shutdown():
    """
    Действия при остановке приложения
    """
    await close_mongodb_connection()

@app.get("/")
async def root():
    """
    Корневой эндпоинт для проверки работоспособности API.
    """
    return {
        "message": "OCR API работает. Доступны эндпоинты для авторизации и распознавания текста.",
        "model": "EasyOCR с поддержкой русского и английского языков",
        "documentation": "/docs"
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Глобальный обработчик исключений
    """
    return JSONResponse(
        status_code=500,
        content={"detail": f"Внутренняя ошибка сервера: {str(exc)}"}
    )

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)