"""
Маршруты для OCR функциональности
"""
from fastapi import APIRouter, Depends, File, UploadFile, Query, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Dict, Any

from app.models.ocr import LanguageType, OcrResult
from app.services.ocr import extract_text, get_user_ocr_history
from app.utils.security import get_current_active_user

router = APIRouter(tags=["OCR"])

@router.post("/extract-text", response_class=JSONResponse)
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
    try:
        result = await extract_text(
            file=file,
            language=language,
            preprocess=preprocess,
            detail=detail,
            user_id=str(current_user["_id"]),
            is_premium=current_user["is_premium"]
        )
        
        return JSONResponse(content=result.dict())
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке изображения: {str(e)}")

@router.get("/ocr-history")
async def get_ocr_history(
    current_user: dict = Depends(get_current_active_user),
    limit: int = Query(30, description="Количество записей для возврата (макс. 100)")
):
    """
    Получает историю OCR запросов пользователя.
    """
    result = await get_user_ocr_history(
        user_id=str(current_user["_id"]),
        is_premium=current_user["is_premium"],
        limit=limit
    )
    
    return result