import base64
from io import BytesIO
import os
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID
from fastapi.responses import FileResponse
import qrcode
from ..models.schemas import (
    ClientResponse,
    ClientCreate,
    ClientEnableDisable,
    ClientUpdateName,
    ClientUpdateAddress,
)
from ..dependencies.auth import get_current_user, require_admin
from tempfile import NamedTemporaryFile
from ..models.schemas import ClientResponse
from ..dependencies.auth import require_admin
from ..models.db import db  # Импортируем Prisma db

router = APIRouter()


@router.get("/", response_model=List[ClientResponse], dependencies=[Depends(require_admin)])
async def get_clients():
    """
    Получить список всех клиентов (Только для администраторов).
    """
    try:
        # Получаем всех клиентов из базы данных
        clients = await db.client.find_many()
        if not clients:
            raise HTTPException(status_code=404, detail="No clients found")
        return clients
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clients: {str(e)}")

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: UUID):
    """
    Получить информацию о клиенте по ID.
    """
    try:
        # Ищем клиента по ID
        client = await db.client.find_unique(where={"id": client_id})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        return client
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching client: {str(e)}")


@router.get("/{client_id}/qrcode")
async def get_client_qrcode(client_id: UUID):
    """
    Получить QR-код для клиента.
    """
    try:
        # Ищем клиента по ID
        client = await db.client.find_unique(where={"id": client_id})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Генерация QR-кода с текстом "Заглушка"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        # TODO: change to real client configuration
        qr.add_data("Заглушка")  # Можно заменить на конфигурацию клиента
        qr.make(fit=True)

        # Создание изображения QR-кода
        img = qr.make_image(fill='black', back_color='white')

        # Сохраняем изображение в байтовый поток
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        # Конвертируем изображение в Base64
        img_base64 = base64.b64encode(buffer.read()).decode("utf-8")

        return {"client_id": client_id, "qrcode": img_base64}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating QR code: {str(e)}")



@router.get("/{client_id}/configuration")
async def get_client_configuration(client_id: UUID):
    """
    Получить конфигурацию клиента в виде файла.
    """
    try:
        # Ищем клиента по ID
        client = await db.client.find_unique(where={"id": client_id})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Ищем подсеть, к которой привязан клиент
        subnet = await db.subnet.find_unique(where={"id": client.subnetId})
        if not subnet:
            raise HTTPException(status_code=404, detail="Subnet not found")

        # Формируем имя файла
        file_name = f"configuration_{subnet.name}_{client.name}.conf"

        # Создаем временный файл
        with NamedTemporaryFile(delete=False, mode="w", suffix=".conf") as temp_file:
            temp_file_path = temp_file.name
            # TODO: change to the real configuration text
            temp_file.write("Заглушка")  # Пока текст "Заглушка"

        # Отправляем файл в качестве ответа
        response = FileResponse(path=temp_file_path, filename=file_name, media_type="text/plain")

        # После отправки файла удаляем временный файл
        os.remove(temp_file_path)

        return response

    except Exception as e:
        # В случае ошибки, если файл был создан, удаляем его
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Error generating configuration file: {str(e)}")



@router.post("/", response_model=ClientResponse)
async def create_client(client: ClientCreate):
    """
    Создать нового клиента.
    """
    try:
        # Проверяем существование подсети
        subnet = await db.subnet.find_unique(where={"id": client.subnetId})
        if not subnet:
            raise HTTPException(status_code=404, detail="Subnet not found")
        public_key = 'zaglushka'
        private_key_ref = 'zaglushka'
        # TODO: make that client publicKeyRef and privateKeyRef will be created before saving him to conf file
        # TODO: make client to create in configuration file too as PEER=
        # Создаем клиента в базе данных

        created_client = await db.client.create(
            data={
                "name": client.name,
                "clientIp": client.clientIp,
                "publicKey": public_key,
                "privateKeyRef": private_key_ref,
                "subnetId": str(client.subnetId),  # Преобразуем UUID в строку
            }
        )

        # Возвращаем созданного клиента
        return created_client

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating client: {str(e)}")


@router.post("/{client_id}/enable", dependencies=[Depends(require_admin)])
async def enable_client(data: ClientEnableDisable ):
    """
    Включить клиента (Только для администраторов).
    """
    try:
        # Ищем клиента по ID
        client = await db.client.find_unique(where={"id": data.clientId})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Проверяем, был ли клиент деактивирован (isEnabled = False)
        if client.isEnabled:
            raise HTTPException(status_code=400, detail="Client is already enabled")
        # TODO: Add client as PEER to the configuration
        # Активируем клиента (изменяем флаг isEnabled на True)
        updated_client = await db.client.update(
            where={"id": data.clientId},
            data={"isEnabled": True}
        )

        return {"clientId": updated_client.clientId, "status": "enabled"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enabling client: {str(e)}")


@router.post("/{client_id}/disable", dependencies=[Depends(require_admin)])
async def disable_client(data: ClientEnableDisable,  ):
    """
    Отключить клиента (Только для администраторов).
    """
    try:
        # Ищем клиента по ID
        client = await db.client.find_unique(where={"id": data.clientId})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Проверяем, был ли клиент уже деактивирован (isEnabled = False)
        if not client.isEnabled:
            raise HTTPException(status_code=400, detail="Client is already disabled")
        # TODO: Remove client as PEER to the configuration
        # Деактивируем клиента (изменяем флаг isEnabled на False)
        updated_client = await db.client.update(
            where={"id": data.clientId},
            data={"isEnabled": False}
        )

        return {"clientId": updated_client.clientId, "status": "disabled"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error disabling client: {str(e)}")



@router.put("/{client_id}/name", response_model=ClientResponse, dependencies=[Depends(require_admin)])
async def update_client_name(client_id: UUID, data: ClientUpdateName ):
    """
    Обновить имя клиента (Только для администраторов).
    """
    try:
        # Ищем клиента по ID
        client = await db.client.find_unique(where={"id": client_id})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Проверка, не совпадает ли новое имя с текущим
        if client.name == data.name:
            raise HTTPException(status_code=400, detail="New name is the same as the current name")

        # Обновляем имя клиента в базе данных
        updated_client = await db.client.update(
            where={"id": client_id},
            data={"name": data.name}
        )

        return updated_client

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating client name: {str(e)}")


@router.put("/{client_id}/address", response_model=ClientResponse, dependencies=[Depends(require_admin)])
async def update_client_address(client_id: UUID, data: ClientUpdateAddress ):
    """
    Обновить IP-адрес клиента (Только для администраторов).
    """
    try:
        # Ищем клиента по ID
        client = await db.client.find_unique(where={"id": client_id})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Проверка, не совпадает ли новый IP с текущим
        if client.clientIp == data.clientIp:
            raise HTTPException(status_code=400, detail="New IP address is the same as the current IP address")

        # TODO: update the IP-address of the PEER in the configuration file
        # Обновляем IP-адрес клиента в базе данных
        updated_client = await db.client.update(
            where={"id": client_id},
            data={"clientIp": data.clientIp}
        )

        return updated_client

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating client IP: {str(e)}")

@router.delete("/{client_id}", dependencies=[Depends(require_admin)])
async def delete_client(client_id: UUID ):
    """
    Удалить клиента (Только для администраторов).
    """
    try:
        # Ищем клиента по ID
        client = await db.client.find_unique(where={"id": client_id})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # TODO: delete the client PEER from configuration file
        # Удаляем клиента из базы данных
        await db.client.delete(where={"id": client_id})


        return {"clientId": client_id, "status": "deleted"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting client: {str(e)}")