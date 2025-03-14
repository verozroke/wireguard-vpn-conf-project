from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID
from ..models.schemas import (
    UserResponse, UserCreate, UserUpdateLogin, UserUpdateClientId,
    UserChangePassword, UserDelete
)
from ..dependencies.auth import require_admin, create_access_token, get_current_user

router = APIRouter()


@router.get("/", response_model=List[UserResponse], dependencies=[Depends(require_admin)])
async def get_users():
    """
    Получить список всех пользователей (Только для администраторов).
    """
    return []  # Заглушка


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID):
    """
    Получить информацию о пользователе по ID.
    """
    return {"id": user_id, "login": "example_user", "clientId": 1, "role": "Employee"}  # Заглушка


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    """
    Получить текущего аутентифицированного пользователя.
    """
    return current_user


@router.post("/register")
async def register_user(data: UserCreate):
    """
    Зарегистрировать нового пользователя.
    """
    return {"message": "User registered", "user": data}  # Заглушка


@router.post("/login")
async def login(data: UserCreate):
    """
    Авторизация пользователя и получение JWT-токена.
    """
    user = None
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@router.put("/{user_id}/login")
async def update_user_login(user_id: UUID, data: UserUpdateLogin):
    """
    Обновить логин пользователя (Только для администраторов).
    """
    if not require_admin(data.userId):
        raise HTTPException(status_code=403, detail="Access denied")
    return {"userId": user_id, "newLogin": data.login}


@router.put("/{user_id}/client-id")
async def update_user_client(user_id: UUID, data: UserUpdateClientId):
    """
    Обновить Client ID пользователя (Только для администраторов).
    """
    if not require_admin(data.userId):
        raise HTTPException(status_code=403, detail="Access denied")
    return {"userId": user_id, "newClientId": data.clientId}


@router.put("/change-password")
async def change_password(data: UserChangePassword):
    """
    Сменить пароль пользователя.
    """
    return {"userId": data.userId, "status": "Password changed"}


@router.delete("/{user_id}")
async def delete_user(user_id: UUID, user=Depends(require_admin)):
    """
    Удалить пользователя (Только для администраторов).
    """
    return {"userId": user_id, "status": "deleted"}