"""
Модели связанные с административной панелью
"""
from typing import List, Dict, Any
from pydantic import BaseModel
from app.models.user import UserStats

class DashboardStats(BaseModel):
    """Модель статистики для главной страницы админ-панели"""
    totalUsers: int
    premiumUsers: int
    totalRequests: int
    requestsToday: int
    recentUsers: List[UserStats]
    requestsByDay: List[Dict[str, Any]]
    languageDistribution: List[Dict[str, Any]]
    userActivity: List[Dict[str, Any]]

class SystemSettings(BaseModel):
    """Модель системных настроек"""
    request_limit: int
    default_language: str
    preprocess_by_default: bool
    admin_email: str
    maintenance_mode: bool
    max_file_size: int