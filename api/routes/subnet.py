from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID
from ..models.schemas import SubnetResponse, SubnetCreate, SubnetUpdateName, SubnetUpdateSubnetIp, SubnetUpdateSubnetMask
from ..dependencies.auth import require_admin

router = APIRouter()


@router.get("/", response_model=List[SubnetResponse], dependencies=[Depends(require_admin)])
async def get_subnets():
    """
    Получить список всех подсетей (Только для администраторов).
    """
    return []  # Заглушка


@router.get("/{subnet_id}", response_model=SubnetResponse)
async def get_subnet(subnet_id: UUID):
    """
    Получить информацию о подсети по ID.
    """
    return {"id": subnet_id, "name": "HR Subnet", "subnetIp": "192.168.1.0", "subnetMask": 24}  # Заглушка


@router.post("/", response_model=SubnetResponse)
async def create_subnet(data: SubnetCreate):
    """
    Создать новую подсеть (Только для администраторов).
    """
    if not require_admin(data.userId):
        raise HTTPException(status_code=403, detail="Access denied")
    return data  # Заглушка


@router.put("/{subnet_id}/name")
async def update_subnet_name(subnet_id: UUID, data: SubnetUpdateName):
    """
    Обновить имя подсети (Только для администраторов).
    """
    if not require_admin(data.userId):
        raise HTTPException(status_code=403, detail="Access denied")
    return {"subnetId": subnet_id, "newName": data.name}


@router.put("/{subnet_id}/subnet-ip")
async def update_subnet_ip(subnet_id: UUID, data: SubnetUpdateSubnetIp):
    """
    Обновить IP-адрес подсети (Только для администраторов).
    """
    if not require_admin(data.userId):
        raise HTTPException(status_code=403, detail="Access denied")
    return {"subnetId": subnet_id, "newSubnetIp": data.subnetIp}


@router.put("/{subnet_id}/subnet-mask")
async def update_subnet_mask(subnet_id: UUID, data: SubnetUpdateSubnetMask):
    """
    Обновить маску подсети (Только для администраторов).
    """
    if not require_admin(data.userId):
        raise HTTPException(status_code=403, detail="Access denied")
    return {"subnetId": subnet_id, "newSubnetMask": data.subnetMask}


@router.delete("/{subnet_id}")
async def delete_subnet(subnet_id: UUID, user=Depends(require_admin)):
    """
    Удалить подсеть (Только для администраторов).
    """
    return {"subnetId": subnet_id, "status": "deleted"}
