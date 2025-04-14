"""
Модели связанные с токенами и аутентификацией
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class Token(BaseModel):
    """Модель ответа с токенами"""
    access_token: str
    refresh_token: str
    token_type: str
    expires_at: datetime

class TokenPayload(BaseModel):
    """Модель данных токена"""
    sub: Optional[str] = None
    exp: Optional[datetime] = None

class RefreshTokenRequest(BaseModel):
    """Модель запроса на обновление токена"""
    refresh_token: str