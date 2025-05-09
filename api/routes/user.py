from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from api.models.db import db

from ..dependencies.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from ..models.schemas import (
    UserChangePassword,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdateLogin,
)

router = APIRouter()


@router.get(
    "/", response_model=List[UserResponse], dependencies=[Depends(require_admin)]
)
async def get_users():
    """
    Получить список всех пользователей (Только для администраторов).
    """
    try:
        users = await db.user.find_many()
        return [] if not users else users

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving users: {str(e)}")


@router.get(
    "/employees",
    response_model=List[UserResponse],
    dependencies=[Depends(require_admin)],
)
async def get_employees():
    """
    Получить список всех пользователей с ролью 'Employee' (Только для администраторов).
    """
    try:
        employees = await db.user.find_many(where={"role": "Employee"})

        return [] if not employees else employees

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving employees: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_me(user_data: dict = Depends(get_current_user)):
    """
    Получить текущего аутентифицированного пользователя по токену.
    """
    try:
        user_id = str(UUID(user_data.get("id")))
        user = await db.user.find_unique(where={"id": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving user: {str(e)}")


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID):
    """
    Получить информацию о пользователе по ID.
    """
    try:
        # Поиск пользователя по ID
        user = await db.user.find_unique(where={"id": str(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving user: {str(e)}")


@router.post("/register", response_model=UserResponse)
async def register_user(data: UserCreate):
    """
    Зарегистрировать нового пользователя.
    """
    try:

        # Проверка: существует ли пользователь с таким логином
        existing_user = await db.user.find_unique(where={"login": data.login})

        if existing_user:
            raise HTTPException(status_code=400, detail="Login already taken")
        if len(data.password) < 8:
            raise HTTPException(
                status_code=400, detail="Password must be at least 8 characters long"
            )
        if len(data.password) > 32:
            raise HTTPException(
                status_code=400, detail="Password must not exceed 32 characters"
            )
        # Хешируем пароль
        hashed_password = hash_password(data.password)

        # Создаем нового пользователя в базе данных
        new_user = await db.user.create(
            data={
                "login": data.login,
                "password": hashed_password,
                "role": "Admin" if data.is_admin else "Employee",
            }
        )

        return new_user

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registering user: {str(e)}")


@router.post("/login")
async def login(data: UserLogin):
    """
    Авторизация пользователя и получение JWT-токена.
    """
    try:
        # Проверка длины пароля
        if len(data.password) < 8:
            raise HTTPException(
                status_code=400, detail="Password must be at least 8 characters long"
            )
        if len(data.password) > 32:
            raise HTTPException(
                status_code=400, detail="Password must not exceed 32 characters"
            )

        # Поиск пользователя по логину
        user = await db.user.find_unique(where={"login": data.login})
        if not user:
            raise HTTPException(status_code=400, detail="Invalid credentials")

        # Проверка правильности пароля
        if not verify_password(data.password, user.password):
            raise HTTPException(status_code=400, detail="Invalid credentials")

        # Генерация токена
        token = create_access_token({"id": user.id, "role": user.role})

        return {"access_token": token, "token_type": "bearer"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during login: {str(e)}")


@router.put("/{user_id}/login", dependencies=[Depends(require_admin)])
async def update_user_login(user_id: UUID, data: UserUpdateLogin):
    """
    Обновить логин пользователя (Только для администраторов).
    """
    try:
        user = await db.user.find_unique(where={"id": str(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        login_taken = await db.user.find_unique(where={"login": data.login})
        if login_taken and login_taken.id != str(user_id):
            raise HTTPException(status_code=400, detail="Login already taken")

        updated_user = await db.user.update(
            where={"id": str(user_id)}, data={"login": data.login}
        )

        return updated_user

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating login: {str(e)}")


@router.put("/change-password")
async def change_password(data: UserChangePassword):
    """
    Сменить пароль пользователя.
    """
    try:
        # Поиск пользователя по ID
        user = await db.user.find_unique(where={"id": str(data.userId)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Проверка старого пароля
        if not verify_password(data.oldPassword, user.password):
            raise HTTPException(status_code=400, detail="Incorrect old password")

        # Валидация длины нового пароля
        if len(data.newPassword) < 8:
            raise HTTPException(
                status_code=400,
                detail="New password must be at least 8 characters long",
            )
        if len(data.newPassword) > 32:
            raise HTTPException(
                status_code=400, detail="New password must not exceed 32 characters"
            )

        # Хешируем новый пароль
        hashed_new_password = hash_password(data.newPassword)

        # Обновляем пароль пользователя
        await db.user.update(
            where={"id": str(data.userId)}, data={"password": hashed_new_password}
        )

        return {"userId": data.userId, "status": "Password changed"}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error changing password: {str(e)}"
        )


@router.delete("/{user_id}", dependencies=[Depends(require_admin)])
async def delete_user(user_id: UUID):
    """
    Удалить пользователя (Только для администраторов).
    """
    try:
        # Проверка: существует ли пользователь
        user = await db.user.find_unique(where={"id": str(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Удаляем пользователя
        await db.user.delete(where={"id": str(user_id)})

        return {"userId": user_id, "status": "deleted"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")
