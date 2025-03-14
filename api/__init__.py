from fastapi import APIRouter
from .routes import client, subnet, user

router = APIRouter()
router.include_router(client.router, prefix="/client", tags=["clients"])
router.include_router(subnet.router, prefix="/subnet", tags=["subnets"])
router.include_router(user.router, prefix="/user", tags=["users"])
