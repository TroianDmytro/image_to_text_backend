import io
import os
import uuid
import uvicorn
import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Depends, status, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from enum import Enum
from PIL import Image, ImageFilter, ImageEnhance
import easyocr
import torch
import numpy as np
import jwt
from passlib.context import CryptContext
from typing import Optional, List, Dict, Any, Annotated
from datetime import timedelta, datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройки JWT
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("Отсутствует SECRET_KEY в .env файле")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Настройки MongoDB
MONGODB_URL = os.getenv("MONGODB_URL")
if not MONGODB_URL:
    raise ValueError("Отсутствует MONGODB_URL в .env файле")

DB_NAME = "ocr_db"

# Pydantic модели
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_at: datetime

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[datetime] = None

class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Пароль должен содержать не менее 8 символов')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    is_premium: Optional[bool] = None

class UserInDB(UserBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    is_active: bool = True
    is_premium: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    is_premium: bool
    created_at: datetime

class LanguageType(str, Enum):
    ru = "ru"
    en = "en"
    ru_en = "ru+en"
    en_ru = "en+ru"

class OcrResultRegion(BaseModel):
    bbox: List[List[float]]
    text: str
    confidence: float

class OcrResult(BaseModel):
    text: str
    model_used: str
    regions: Optional[List[OcrResultRegion]] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# Утилиты безопасности
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Инициализация FastAPI
app = FastAPI(title="OCR API", description="API для распознавания текста с изображений")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Адрес React приложения
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальная переменная для ридера EasyOCR
reader = None

# MongoDB клиент
mongodb_client = None
db = None

@app.on_event("startup")
async def startup_db_client():
    global mongodb_client, db, reader
    
    # Подключение к MongoDB
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
    except Exception as e:
        print(f"Ошибка при подключении к MongoDB: {str(e)}")
        raise e
    
    # Загружаем EasyOCR
    try:
        print("Загрузка модели EasyOCR для русского и английского языков...")
        reader = easyocr.Reader(['en', 'ru'], gpu=torch.cuda.is_available())
        print("Модель EasyOCR успешно загружена")
    except Exception as e:
        print(f"Ошибка при загрузке модели EasyOCR: {str(e)}")
        raise e

@app.on_event("shutdown")
async def shutdown_db_client():
    global mongodb_client
    if mongodb_client:
        mongodb_client.close()
        print("Соединение с MongoDB закрыто")

# Вспомогательные функции для работы с JWT и пользователями
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

async def get_user(username: str):
    if (user := await db.users.find_one({"username": username})) is not None:
        return user
    return None

async def get_user_by_email(email: str):
    if (user := await db.users.find_one({"email": email})) is not None:
        return user
    return None

async def authenticate_user(username: str, password: str):
    user = await get_user(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, expire

async def create_refresh_token(user_id: str):
    token_value = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    refresh_token = {
        "token": token_value,
        "user_id": ObjectId(user_id),
        "expires_at": expires_at,
        "created_at": datetime.utcnow(),
        "revoked": False
    }
    
    await db.refresh_tokens.insert_one(refresh_token)
    
    return token_value, expires_at

async def get_current_user(token: str = Depends(oauth2_scheme)):
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
        
    user = await get_user(username=username)
    if user is None:
        raise credentials_exception
    
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Аккаунт отключен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    if not current_user["is_active"]:
        raise HTTPException(status_code=400, detail="Неактивный пользователь")
    return current_user

def preprocess_image(image, enhance_contrast=1.5, sharpen=True):
    """
    Улучшает качество изображения для лучшего распознавания текста
    """
    # Увеличение контраста
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(enhance_contrast)
    
    # Увеличение резкости
    if sharpen:
        image = image.filter(ImageFilter.SHARPEN)
    
    return image

# Конвертирует MongoDB документ пользователя в Pydantic модель для ответа API
def user_to_response(user: dict) -> UserOut:
    return UserOut(
        id=str(user["_id"]),
        email=user["email"],
        username=user["username"],
        is_premium=user["is_premium"],
        created_at=user["created_at"]
    )

# Маршруты API
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

# Регистрация пользователя
@app.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    # Проверяем, существует ли пользователь с таким email
    if await get_user_by_email(user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Пользователь с таким email уже существует"
        )
    
    # Проверяем, существует ли пользователь с таким именем
    if await get_user(user.username):
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
        "created_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_data)
    user_data["_id"] = result.inserted_id
    
    return user_to_response(user_data)

# Вход в систему
@app.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
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
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_at": access_token_expires
    }

# Обновление токена
@app.post("/refresh-token", response_model=Token)
async def refresh_token(request: RefreshTokenRequest):
    # Проверяем refresh token
    token_doc = await db.refresh_tokens.find_one({
        "token": request.refresh_token,
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
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_at": access_token_expires
    }

# Выход из системы
@app.post("/logout")
async def logout(request: RefreshTokenRequest):
    # Находим и отзываем refresh token
    result = await db.refresh_tokens.update_one(
        {"token": request.refresh_token, "revoked": False},
        {"$set": {"revoked": True}}
    )
    
    return {"detail": "Успешный выход из системы"}

# Получение информации о текущем пользователе
@app.get("/users/me", response_model=UserOut)
async def read_users_me(current_user: dict = Depends(get_current_active_user)):
    return user_to_response(current_user)

# Распознавание текста
@app.post("/extract-text", response_class=JSONResponse)
async def extract_text_from_image(
    file: UploadFile = File(...),
    language: LanguageType = Query(LanguageType.en_ru, description="Языки для распознавания"),
    preprocess: bool = Query(True, description="Предобработка изображения для улучшения распознавания"),
    detail: bool = Query(False, description="Вернуть детальную информацию о распознанных областях"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Извлекает текст из загруженного изображения.
    """
    # Проверка лимита для обычных пользователей
    if not current_user["is_premium"]:
        # Проверяем количество запросов за последние 24 часа
        day_ago = datetime.utcnow() - timedelta(days=1)
        
        requests_count = await db.ocr_requests.count_documents({
            "user_id": current_user["_id"],
            "created_at": {"$gt": day_ago}
        })
        
        if requests_count >= 10:  # Лимит для обычных пользователей - 10 запросов в день
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Превышен лимит запросов. Обновите аккаунт до Premium для снятия ограничений."
            )
    
    # Проверка, что EasyOCR загружен
    global reader
    if reader is None:
        raise HTTPException(status_code=500, detail="Модель EasyOCR не загружена. Попробуйте позже.")
    
    # Проверка типа файла
    allowed_formats = ["image/png", "image/jpeg", "image/jpg"]
    content_type = file.content_type or ""
    
    if content_type not in allowed_formats:
        raise HTTPException(
            status_code=400, 
            detail=f"Неподдерживаемый формат файла. Поддерживаемые форматы: {', '.join(allowed_formats)}"
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
            "ru": ['ru'],
            "en": ['en'],
            "ru+en": ['ru', 'en'],
            "en+ru": ['en', 'ru']
        }
        
        # Распознавание текста
        languages = lang_map.get(language.value, ['en', 'ru'])
        
        # Используем глобальный reader вместо создания нового
        # Это ускорит обработку запросов
        result = reader.readtext(img_np)
        
        # Формируем ответ
        if detail:
            # Детальный ответ со всеми найденными текстовыми областями
            text_regions = []
            for detection in result:
                bbox, text, confidence = detection
                text_regions.append({
                    "bbox": bbox,
                    "text": text,
                    "confidence": float(confidence)
                })
            
            # Объединяем весь текст в один
            full_text = " ".join([region["text"] for region in text_regions])
            
            response = {
                "text": full_text,
                "regions": text_regions,
                "model_used": f"EasyOCR ({','.join(languages)})"
            }
        else:
            # Простой ответ только с текстом
            full_text = " ".join([detection[1] for detection in result])
            response = {
                "text": full_text,
                "model_used": f"EasyOCR ({','.join(languages)})"
            }
        
        # Сохраняем запрос в БД (асинхронно)
        background_tasks.add_task(
            save_ocr_request, 
            user_id=current_user["_id"],
            language=language.value,
            preprocess=preprocess,
            detail=detail,
            result_text=full_text
        )
        
        return JSONResponse(content=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке изображения: {str(e)}")
    finally:
        await file.close()

# История OCR запросов
@app.get("/ocr-history")
async def get_ocr_history(
    current_user: dict = Depends(get_current_active_user),
    limit: int = Query(30, description="Количество записей для возврата (макс. 100)")
):
    """
    Получает историю OCR запросов пользователя.
    """
    # Ограничиваем максимальное количество записей
    if limit > 100:
        limit = 100
    
    # Для премиум-пользователей нет ограничения на количество записей в истории
    # Для обычных пользователей возвращаем только последние записи
    if not current_user["is_premium"]:
        # Обычные пользователи получают последние N записей
        limit = min(limit, 30)
    
    # Получаем записи из базы данных
    cursor = db.ocr_requests.find(
        {"user_id": current_user["_id"]}
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

# Вспомогательная функция для сохранения OCR запроса в БД
async def save_ocr_request(user_id, language, preprocess, detail, result_text):
    """Сохраняет запрос OCR в базу данных"""
    ocr_request = {
        "user_id": user_id,
        "language": language,
        "preprocess": preprocess,
        "detail": detail,
        "result_text": result_text,
        "created_at": datetime.utcnow()
    }
    
    await db.ocr_requests.insert_one(ocr_request)

# Запуск приложения
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)