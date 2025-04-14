"""
Утилиты для обработки изображений
"""
from PIL import Image, ImageFilter, ImageEnhance
import easyocr
import torch
import numpy as np

# Глобальная переменная для ридера EasyOCR
reader = None

def init_ocr_reader():
    """
    Инициализация объекта EasyOCR
    """
    global reader
    try:
        print("Загрузка модели EasyOCR для русского и английского языков...")
        reader = easyocr.Reader(['en', 'ru'], gpu=torch.cuda.is_available())
        print("Модель EasyOCR успешно загружена")
        return reader
    except Exception as e:
        print(f"Ошибка при загрузке модели EasyOCR: {str(e)}")
        raise e

def get_ocr_reader():
    """
    Получение объекта EasyOCR
    """
    global reader
    if reader is None:
        reader = init_ocr_reader()
    return reader

def preprocess_image(image, enhance_contrast=1.5, sharpen=True):
    """
    Улучшает качество изображения для лучшего распознавания текста
    
    Args:
        image: PIL.Image - входное изображение
        enhance_contrast: float - коэффициент увеличения контраста
        sharpen: bool - применять ли увеличение резкости
        
    Returns:
        PIL.Image - обработанное изображение
    """
    # Увеличение контраста
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(enhance_contrast)
    
    # Увеличение резкости
    if sharpen:
        image = image.filter(ImageFilter.SHARPEN)
    
    return image

def perform_ocr(image_np, languages=['en', 'ru']):
    """
    Выполняет распознавание текста на изображении
    
    Args:
        image_np: numpy.ndarray - изображение в формате numpy array
        languages: list - список языков для распознавания
        
    Returns:
        list - результаты распознавания
    """
    ocr_reader = get_ocr_reader()
    return ocr_reader.readtext(image_np)