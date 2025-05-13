import ipaddress
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies.auth import require_admin
from ..models.db import db  # Импортируем Prisma db
from ..models.schemas import (
    SubnetCreate,
    SubnetResponse,
    SubnetUpdateName,
    SubnetUpdateSubnetIp,
    SubnetUpdateSubnetMask,
)

router = APIRouter()


@router.get(
    "/", response_model=List[SubnetResponse], dependencies=[Depends(require_admin)]
)
async def get_subnets():
    """
    Получить список всех подсетей (Только для администраторов).
    """
    try:
        # Получаем все подсети из базы данных
        subnets = await db.subnet.find_many()
        return [] if not subnets else subnets

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching subnets: {str(e)}")


@router.get("/{subnet_id}", response_model=SubnetResponse)
async def get_subnet(subnet_id: UUID):
    """
    Получить информацию о подсети по ID.
    """
    try:
        # Ищем подсеть по ID
        subnet = await db.subnet.find_unique(where={"id": str(subnet_id)})
        if not subnet:
            raise HTTPException(status_code=404, detail="Subnet not found")
        return subnet

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching subnet: {str(e)}")


@router.post("/", response_model=SubnetResponse, dependencies=[Depends(require_admin)])
async def create_subnet(data: SubnetCreate):
    """
    Создать новую подсеть (Только для администраторов).
    """
    try:
        # Валидация маски подсети
        if data.subnetMask < 0 or data.subnetMask > 32:
            raise HTTPException(
                status_code=400, detail="Subnet mask must be between 0 and 32"
            )

        # Валидация IP-адреса и проверка, что это именно адрес сети (а не, например, host)
        try:
            # Пытаемся создать сеть
            net = ipaddress.IPv4Network(
                f"{data.subnetIp}/{data.subnetMask}", strict=True
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid subnet IP: {str(e)}")

        # Проверка существования подсети с таким же IP
        existing_subnet = await db.subnet.find_unique(where={"subnetIp": data.subnetIp})
        if existing_subnet:
            raise HTTPException(
                status_code=400, detail="Subnet with this IP already exists"
            )

        # Проверка существования подсети с таким же именем
        existing_name_subnet = await db.subnet.find_first(where={"name": data.name})
        if existing_name_subnet:
            raise HTTPException(
                status_code=400, detail="Subnet with this name already exists"
            )

        # Всё валидно — создаем подсеть
        created_subnet = await db.subnet.create(
            data={
                "name": data.name,
                "subnetIp": data.subnetIp,
                "subnetMask": data.subnetMask,
                "userId": str(data.userId),
            }
        )

        return created_subnet

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating subnet: {str(e)}")


@router.put("/{subnet_id}/name", dependencies=[Depends(require_admin)])
async def update_subnet_name(subnet_id: UUID, data: SubnetUpdateName):
    """
    Обновить имя подсети (Только для администраторов).
    """
    try:
        # Проверяем существование подсети
        subnet = await db.subnet.find_unique(where={"id": str(subnet_id)})
        if not subnet:
            raise HTTPException(status_code=404, detail="Subnet not found")

        # Обновляем имя подсети
        updated_subnet = await db.subnet.update(
            where={"id": str(subnet_id)}, data={"name": data.name}
        )

        return updated_subnet

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating subnet name: {str(e)}"
        )


@router.put("/{subnet_id}/subnet-ip", dependencies=[Depends(require_admin)])
async def update_subnet_ip(subnet_id: UUID, data: SubnetUpdateSubnetIp):
    """
    Обновить IP-адрес подсети (Только для администраторов).
    """
    try:
        # Проверяем существование подсети
        subnet = await db.subnet.find_unique(where={"id": str(subnet_id)})
        if not subnet:
            raise HTTPException(status_code=404, detail="Subnet not found")

        # Валидация: IP должен быть корректным и подходить как адрес подсети
        try:
            net = ipaddress.IPv4Network(
                f"{data.subnetIp}/{subnet.subnetMask}", strict=True
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid subnet IP: {str(e)}")

        # Обновляем IP-адрес подсети
        updated_subnet = await db.subnet.update(
            where={"id": str(subnet_id)}, data={"subnetIp": data.subnetIp}
        )

        return updated_subnet

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating subnet IP: {str(e)}"
        )


@router.put("/{subnet_id}/subnet-mask", dependencies=[Depends(require_admin)])
async def update_subnet_mask(subnet_id: UUID, data: SubnetUpdateSubnetMask):
    """
    Обновить маску подсети (Только для администраторов).
    """
    try:
        # Проверяем существование подсети
        subnet = await db.subnet.find_unique(where={"id": str(subnet_id)})
        if not subnet:
            raise HTTPException(status_code=404, detail="Subnet not found")

        # Проверка маски подсети (должна быть в диапазоне от 0 до 32)
        if data.subnetMask < 0 or data.subnetMask > 32:
            raise HTTPException(
                status_code=400, detail="Subnet mask must be between 0 and 32"
            )

        # Обновляем маску подсети
        updated_subnet = await db.subnet.update(
            where={"id": str(subnet_id)}, data={"subnetMask": data.subnetMask}
        )

        return updated_subnet

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating subnet mask: {str(e)}"
        )


@router.delete("/{subnet_id}", dependencies=[Depends(require_admin)])
async def delete_subnet(subnet_id: UUID):
    """
    Удалить подсеть (Только для администраторов).
    """
    try:
        # Проверка: существует ли подсеть
        subnet = await db.subnet.find_unique(where={"id": str(subnet_id)})
        if not subnet:
            raise HTTPException(status_code=404, detail="Subnet not found")

        # Удаляем подсеть
        await db.subnet.delete(where={"id": str(subnet_id)})

        return {"subnetId": subnet_id, "status": "deleted"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting subnet: {str(e)}")
