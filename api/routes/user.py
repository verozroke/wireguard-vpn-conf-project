import random
from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies.email import send_email
from api.models.db import db

from ..dependencies.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from ..models.schemas import (
    EmailRequest,
    UserChangePassword,
    UserCreate,
    UserLogin,
    UserUpdateLogin,
    VerifyRequest,
)

router = APIRouter()
verification_codes: Dict[str, str] = {}

@router.get(
    "/", dependencies=[Depends(require_admin)]
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


@router.get("/me")
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


@router.get("/{user_id}")
async def get_user(user_id: UUID):
    """
    Получить информацию о пользователе по ID.
    """
    try:
        user = await db.user.find_unique(where={"id": str(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving user: {str(e)}")


@router.post("/register")
async def register_user(data: UserCreate):
    """
    Зарегистрировать нового пользователя.
    """
    try:  
        
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
        
        
        hashed_password = hash_password(data.password)


        new_user = await db.user.create(
            data={
                "login": data.login,
                "email": data.email,
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
        if len(data.password) < 8:
            raise HTTPException(
                status_code=400, detail="Password must be at least 8 characters long"
            )
        if len(data.password) > 32:
            raise HTTPException(
                status_code=400, detail="Password must not exceed 32 characters"
            )
        

        user = await db.user.find_unique(where={"login": data.login})
        print(user)
        if not user:
            raise HTTPException(status_code=400, detail="Invalid credentials")

        # if user.email != data.email:
        #     raise HTTPException(status_code=400, detail="This is not email of your login.")
          
        if not verify_password(data.password, user.password):
            raise HTTPException(status_code=400, detail="Invalid credentials")
        

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
        user = await db.user.find_unique(where={"id": str(data.userId)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not verify_password(data.oldPassword, user.password):
            raise HTTPException(status_code=400, detail="Incorrect old password")

        if len(data.newPassword) < 8:
            raise HTTPException(
                status_code=400,
                detail="New password must be at least 8 characters long",
            )
        if len(data.newPassword) > 32:
            raise HTTPException(
                status_code=400, detail="New password must not exceed 32 characters"
            )

        hashed_new_password = hash_password(data.newPassword)

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
        user = await db.user.find_unique(where={"id": str(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        await db.user.delete(where={"id": str(user_id)})

        return {"userId": user_id, "status": "deleted"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")



@router.post("/send-email")
def send_verification_email(data: EmailRequest):
    code = f"{random.randint(100000, 999999)}"
    verification_codes[data.email] = code

    try:
        send_email(
            to_email=data.email,
            subject="Your verification code",
            body=f"Your verification code is: {code}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    return {"message": "Verification code sent to your email."}

@router.post("/verify-email")
def verify_email_code(data: VerifyRequest):
    expected_code = verification_codes.get(data.email)
    if not expected_code:
        raise HTTPException(status_code=404, detail="No code sent to this email.")
    if data.code != expected_code:
        raise HTTPException(status_code=400, detail="Invalid verification code.")
    
    # Optional: remove used code after verification
    del verification_codes[data.email]
    return {"message": "Email verified successfully."}

