import io
import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse
from enum import Enum
from PIL import Image, ImageFilter, ImageEnhance
import easyocr
import torch
import numpy as np
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="OCR API", description="API для распознавания текста с изображений")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Глобальная переменная для ридера EasyOCR
reader = None

class LanguageType(str, Enum):
    ru = "ru"
    en = "en"
    ru_en = "ru+en"
    en_ru = "en+ru"

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

@app.on_event("startup")
async def load_models():
    global reader
    try:
        # Загружаем EasyOCR с поддержкой русского и английского языков
        print("Загрузка модели EasyOCR для русского и английского языков...")
        reader = easyocr.Reader(['en', 'ru'], gpu=torch.cuda.is_available())
        print("Модель EasyOCR успешно загружена")
    except Exception as e:
        print(f"Ошибка при загрузке модели EasyOCR: {str(e)}")
        raise e

@app.get("/")
async def root():
    """
    Корневой эндпоинт для проверки работоспособности API.
    """
    return {
        "message": "OCR API работает. Отправьте изображение на /extract-text для распознавания текста.",
        "model": "EasyOCR с поддержкой русского и английского языков",
        "documentation": "/docs"
    }

@app.post("/extract-text", response_class=JSONResponse)
async def extract_text_from_image(
    file: UploadFile = File(...),
    language: LanguageType = Query(LanguageType.en_ru, description="Языки для распознавания"),
    preprocess: bool = Query(True, description="Предобработка изображения для улучшения распознавания"),
    detail: bool = Query(False, description="Вернуть детальную информацию о распознанных областях")
):
    """
    Извлекает текст из загруженного изображения.
    
    Args:
        file (UploadFile): Загружаемый файл изображения (PNG, JPG, JPEG).
        language (LanguageType): Языки для распознавания.
        preprocess (bool): Применять ли предобработку изображения.
        detail (bool): Вернуть детальную информацию о распознанных областях.
        
    Returns:
        JSONResponse: JSON объект с распознанным текстом.
    """
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
        
        # Создаем новый reader с указанными языками
        # Вместо проверки reader.lang_list, которая вызывала ошибку
        local_reader = easyocr.Reader(languages, gpu=torch.cuda.is_available())
        
        # Выполняем распознавание
        result = local_reader.readtext(img_np)
        
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
        
        return JSONResponse(content=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке изображения: {str(e)}")
    finally:
        await file.close()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)