from fastapi import APIRouter
from .routes import client, subnet, user

router = APIRouter()
router.include_router(client.router)
router.include_router(subnet.router)
router.include_router(user.router)
