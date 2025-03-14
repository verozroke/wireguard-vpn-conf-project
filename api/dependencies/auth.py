from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Security
from fastapi.security import OAuth2PasswordBearer
from uuid import UUID
from dotenv import load_dotenv
import os
load_dotenv()

# Конфигурация для токенов
SECRET_KEY = os.getenv("SECRET_KEY")  
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Настройка хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# FastAPI security scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Хеширование пароля"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создание JWT-токена"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Декодирование JWT-токена"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Получение текущего пользователя по токену"""
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


def require_admin(user: dict = Depends(get_current_user)):
    """Проверка роли пользователя (только для администраторов)"""
    if user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Access denied")
    return user


def require_user_or_admin(user_id: UUID, user: dict = Depends(get_current_user)):
    """Проверка: либо админ, либо пользователь может редактировать себя"""
    if user.get("role") != "Admin" and user.get("id") != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied")
    return user
