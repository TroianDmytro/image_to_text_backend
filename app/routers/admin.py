"""
Маршруты для административной панели
"""
from fastapi import APIRouter, Depends, Query, Path, HTTPException, status
import math

from app.models.admin import DashboardStats, SystemSettings
from app.models.user import AdminUserUpdate
from app.models.ocr import OcrStatistics
from app.services.admin import get_dashboard_stats, get_system_settings, update_system_settings
from app.services.user import get_users_list, admin_update_user, admin_delete_user
from app.services.ocr import get_ocr_statistics
from app.utils.security import get_current_admin

router = APIRouter(
    prefix="/admin",
    tags=["Администрирование"],
    dependencies=[Depends(get_current_admin)]
)

@router.get("/dashboard", response_model=DashboardStats)
async def admin_dashboard(current_user: dict = Depends(get_current_admin)):
    """
    Получение статистики для главной страницы панели администратора
    """
    return await get_dashboard_stats()

@router.get("/users")
async def admin_get_users(
    current_user: dict = Depends(get_current_admin),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Получение списка пользователей с пагинацией
    """
    return await get_users_list(page, limit)

@router.put("/users/{user_id}")
async def admin_update_user_endpoint(
    user_id: str = Path(..., title="ID пользователя"),
    user_data: AdminUserUpdate = ...,
    current_user: dict = Depends(get_current_admin)
):
    """
    Обновление информации о пользователе администратором
    """
    # Проверяем, что администратор не лишает сам себя прав администратора
    if str(current_user["_id"]) == user_id and user_data.is_admin is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы не можете лишить себя прав администратора"
        )
    
    return await admin_update_user(user_id, user_data)

@router.delete("/users/{user_id}")
async def admin_delete_user_endpoint(
    user_id: str = Path(..., title="ID пользователя"),
    current_user: dict = Depends(get_current_admin)
):
    """
    Удаление пользователя администратором
    """
    return await admin_delete_user(user_id, str(current_user["_id"]))

@router.get("/ocr-stats", response_model=OcrStatistics)
async def admin_get_ocr_stats(
    current_user: dict = Depends(get_current_admin),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    date_filter: str = Query(None, regex="^(all|today|week|month)$"),
    language: str = Query(None)
):
    """
    Получение статистики OCR и списка запросов с фильтрацией
    """
    return await get_ocr_statistics(page, limit, date_filter, language)

@router.get("/settings", response_model=SystemSettings)
async def admin_get_settings(current_user: dict = Depends(get_current_admin)):
    """
    Получение системных настроек
    """
    return await get_system_settings()

@router.put("/settings", response_model=SystemSettings)
async def admin_update_settings(
    settings: SystemSettings,
    current_user: dict = Depends(get_current_admin)
):
    """
    Обновление системных настроек
    """
    return await update_system_settings(settings)