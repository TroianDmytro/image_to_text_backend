"""
Модели связанные с пользователями
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from bson import ObjectId

class UserBase(BaseModel):
    """Базовая модель пользователя"""
    email: EmailStr
    username: str

class UserCreate(UserBase):
    """Модель создания пользователя"""
    password: str
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Пароль должен содержать не менее 8 символов')
        return v

class UserUpdate(BaseModel):
    """Модель обновления пользователя"""
    email: Optional[EmailStr] = None
    is_premium: Optional[bool] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

class UserInDB(UserBase):
    """Модель пользователя в базе данных"""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    is_active: bool = True
    is_premium: bool = False
    is_admin: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserOut(UserBase):
    """Модель пользователя для ответа API"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    is_premium: bool
    is_admin: bool = False
    created_at: datetime

# Административные модели для пользователей
class AdminUserUpdate(BaseModel):
    """Модель обновления пользователя администратором"""
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_premium: Optional[bool] = None
    is_admin: Optional[bool] = None

class UserStats(BaseModel):
    """Статистика пользователя для админ-панели"""
    id: str
    username: str
    email: str
    created_at: datetime
    is_premium: bool
    is_admin: bool = False
    is_active: bool = True
    request_count: int