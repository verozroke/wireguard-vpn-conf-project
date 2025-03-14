from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID

from ..models.schemas import (
    ClientResponse,
    ClientCreate,
    ClientEnableDisable,
    ClientUpdateName,
    ClientUpdateAddress,
)
from ..dependencies.auth import get_current_user, require_admin

router = APIRouter()


@router.get("/", response_model=List[ClientResponse], dependencies=[Depends(require_admin)])
async def get_clients():
    """
    Получить список всех клиентов (Только для администраторов).
    """
    return []  # Заглушка


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: UUID):
    """
    Получить информацию о клиенте по ID.
    """
    return {"id": client_id, "name": "Example Client", "clientIp": "192.168.1.10", "publicKey": "pubKey", "privateKeyRef": "privKeyRef", "subnetId": UUID("123e4567-e89b-12d3-a456-426614174000"), "isEnabled": True}  # Заглушка


@router.get("/{client_id}/qrcode")
async def get_client_qrcode(client_id: UUID):
    """
    Получить QR-код для клиента.
    """
    return {"client_id": client_id, "qrcode": "Base64-Encoded-QR"}  # Заглушка


@router.get("/{client_id}/configuration")
async def get_client_configuration(client_id: UUID):
    """
    Получить конфигурацию клиента.
    """
    return {"client_id": client_id, "configuration": "Example Configuration"}  # Заглушка


@router.post("/", response_model=ClientResponse)
async def create_client(client: ClientCreate):
    """
    Создать нового клиента.
    """
    return client  # Заглушка


@router.post("/{client_id}/enable")
async def enable_client(data: ClientEnableDisable, user=Depends(require_admin)):
    """
    Включить клиента (Только для администраторов).
    """
    return {"clientId": data.clientId, "status": "enabled"}


@router.post("/{client_id}/disable")
async def disable_client(data: ClientEnableDisable, user=Depends(require_admin)):
    """
    Отключить клиента (Только для администраторов).
    """
    return {"clientId": data.clientId, "status": "disabled"}


@router.put("/{client_id}/name", response_model=ClientResponse)
async def update_client_name(client_id: UUID, data: ClientUpdateName, user=Depends(require_admin)):
    """
    Обновить имя клиента (Только для администраторов).
    """
    return {"id": client_id, "name": data.name}


@router.put("/{client_id}/address", response_model=ClientResponse)
async def update_client_address(client_id: UUID, data: ClientUpdateAddress, user=Depends(require_admin)):
    """
    Обновить IP-адрес клиента (Только для администраторов).
    """
    return {"id": client_id, "clientIp": data.clientIp}  # Обновленный IP-адрес


@router.delete("/{client_id}")
async def delete_client(client_id: UUID, user=Depends(require_admin)):
    """
    Удалить клиента (Только для администраторов).
    """
    return {"clientId": client_id, "status": "deleted"}
