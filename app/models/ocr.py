"""
Модели связанные с OCR
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class LanguageType(str, Enum):
    """Типы языков для распознавания"""
    ru = "ru"
    en = "en"
    ru_en = "ru+en"
    en_ru = "en+ru"

class OcrResultRegion(BaseModel):
    """Модель региона с распознанным текстом"""
    bbox: List[List[float]]
    text: str
    confidence: float

class OcrResult(BaseModel):
    """Модель результата OCR"""
    text: str
    model_used: str
    regions: Optional[List[OcrResultRegion]] = None

class OcrRequestInfo(BaseModel):
    """Модель информации о запросе OCR для админ-панели"""
    id: str
    user_id: str
    username: str
    language: str
    preprocess: bool
    detail: bool
    result_text: str
    created_at: datetime

class OcrStatistics(BaseModel):
    """Модель статистики OCR для админ-панели"""
    total_requests: int
    requests_today: int
    requests_by_day: List[Dict[str, Any]]
    top_users: List[Dict[str, Any]]
    language_distribution: List[Dict[str, Any]]
    requests: List[OcrRequestInfo]
    total_pages: int