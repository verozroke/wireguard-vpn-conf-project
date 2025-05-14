import base64
import ipaddress
import os
import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List
from uuid import UUID
import qrcode
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from ..dependencies.auth import get_current_user, require_admin
from ..models.db import db  # Импортируем Prisma db
from ..models.schemas import (
    ClientCreate,
    ClientEnableDisable,
    ClientResponse,
    ClientUpdateAddress,
    ClientUpdateName,
)

router = APIRouter()

DEFAULT_DNS_IP = "8.8.8.8"
DEFAULT_SERVER_IP = "51.195.217.223"
DEFAULT_SERVER_PORT = 51830
DEFAULT_ALLOWED_IPS = "0.0.0.0/0"
DEFAULT_PERSISTENT_KEEP_ALIVE = 20


WG_CONF_DIR = Path("etc/wireguard")
WG_CLIENTS_DIR = WG_CONF_DIR / "clients"
WG_CONF_PATH = WG_CONF_DIR / "wg0.conf"
WG_SERVER_PUBLIC_KEY_FILE = WG_CONF_DIR / "publickey"

def remove_peer_from_config(public_key: str):
    """Удаляет весь блок [Peer] с указанным публичным ключом из wg0.conf"""
    if not WG_CONF_PATH.exists():
        return

    with open(WG_CONF_PATH, "r") as f:
        lines = f.readlines()

    new_lines = []
    inside_peer_block = False
    current_block = []

    for line in lines:
        if line.strip() == "[Peer]":
            # Сохраняем предыдущий блок, если он не совпадает
            if current_block and not any(public_key in l for l in current_block):
                new_lines.extend(current_block)
            # Начинаем новый блок
            current_block = [line]
            inside_peer_block = True
        elif inside_peer_block:
            current_block.append(line)
            if line.strip() == "" or line.strip().startswith("[Peer]"):
                # Конец текущего блока — проверим его
                if not any(public_key in l for l in current_block):
                    new_lines.extend(current_block)
                current_block = []
                if line.strip() == "[Peer]":
                    current_block.append(line)
        else:
            new_lines.append(line)

    # Если после последней итерации остался блок — проверь его
    if current_block and not any(public_key in l for l in current_block):
        new_lines.extend(current_block)

    # Перезаписываем конфиг
    with open(WG_CONF_PATH, "w") as f:
        f.writelines(new_lines)


def add_peer_to_config(public_key: str, ip: str, mask: int):
    """Добавляет новый блок [Peer] в wg0.conf"""
    block = f"""

[Peer]
PublicKey = {public_key}
AllowedIPs = {ip}/{mask}
"""
    with open(WG_CONF_PATH, "a") as f:
        f.write(block)


def update_allowed_ips_in_config(public_key: str, new_ip: str, subnet_mask: int):
    """Обновляет строку AllowedIPs у пира с нужным публичным ключом"""
    if not WG_CONF_PATH.exists():
        return

    with open(WG_CONF_PATH, "r") as f:
        lines = f.readlines()

    new_lines = []
    inside_peer = False
    found_peer = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped == "[Peer]":
            inside_peer = True
            new_lines.append(line)
            continue

        if inside_peer and stripped.startswith("PublicKey") and public_key in stripped:
            found_peer = True
            new_lines.append(line)
            continue

        if inside_peer and stripped.startswith("AllowedIPs") and found_peer:
            # Заменяем AllowedIPs строку
            new_lines.append(f"AllowedIPs = {new_ip}/{subnet_mask}\n")
            inside_peer = False
            found_peer = False
            continue

        new_lines.append(line)

    with open(WG_CONF_PATH, "w") as f:
        f.writelines(new_lines)





def generate_client_config_text(client_ip: str, client_private_key_path: str, server_public_key: str) -> str:
    """
    Генерирует текст WireGuard-конфигурации для клиента.
    
    :param client_ip: IP-адрес клиента
    :param client_private_key_path: Путь к файлу с приватным ключом (из client.privateKeyRef)
    :param server_public_key: публичный ключ сервера (из client.publicKey)
    """
    private_key_file = Path(client_private_key_path)

    if not private_key_file.exists():
        raise FileNotFoundError("Client private key file not found")

    with open(private_key_file, "r") as f:
        private_key = f.read().strip()

    return f"""[Interface]
PrivateKey = {private_key}
Address = {client_ip}/32
DNS = {DEFAULT_DNS_IP}

[Peer]
PublicKey = {server_public_key}
Endpoint = {DEFAULT_SERVER_IP}:{DEFAULT_SERVER_PORT}
AllowedIPs = {DEFAULT_ALLOWED_IPS}
PersistentKeepAlive = {DEFAULT_PERSISTENT_KEEP_ALIVE}
""".strip()



@router.get("/", dependencies=[Depends(require_admin)])
async def get_clients():
    """
    Получить список всех клиентов (Только для администраторов).
    """
    try:
        # Получаем всех клиентов из базы данных
        clients = await db.client.find_many(include={"user": True, "subnet": True})

        return [] if not clients else clients
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clients: {str(e)}")


@router.get("/{user_id}/my-clients")
async def get_user_clients(user_id: UUID):
    """
    Получить всех клиентов, привязанных к пользователю по user_id,
    включая связанные user и subnet.
    """
    try:
        clients = await db.client.find_many(
            where={"userId": str(user_id)}, include={"user": True, "subnet": True}
        )

        return [] if not clients else clients

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching user clients: {str(e)}"
        )


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: UUID):
    """
    Получить информацию о клиенте по ID.
    """
    try:
        # Ищем клиента по ID
        client = await db.client.find_unique(where={"id": str(client_id)})
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
        client = await db.client.find_unique(where={"id": str(client_id)})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        config_text = generate_client_config_text(
            client_ip=client.clientIp,
            client_private_key_path=client.privateKeyRef,
            server_public_key=client.publicKey
        )
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(config_text) 
        qr.make(fit=True)

        # Создание изображения QR-кода
        img = qr.make_image(fill="black", back_color="white")

        # Сохраняем изображение в байтовый поток
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        # Конвертируем изображение в Base64
        img_base64 = base64.b64encode(buffer.read()).decode("utf-8")

        return {"client_id": client_id, "qrcode": img_base64}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating QR code: {str(e)}"
        )


@router.get("/{client_id}/configuration")
async def get_client_configuration(client_id: UUID):
    """
    Получить конфигурацию клиента в виде файла.
    """
    try:
        # Ищем клиента по ID
        client = await db.client.find_unique(
            where={"id": str(client_id)},
            include={"subnet": True}
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        if not client.subnet:
            raise HTTPException(status_code=404, detail="Subnet not found")

        # Генерация конфигурации
        config_text = generate_client_config_text(
            client_ip=client.clientIp,
            client_private_key_path=client.privateKeyRef,
            server_public_key=client.publicKey
        )

        # Формируем имя файла
        file_name = f"configuration_{client.subnet.name}_{client.name}.conf"

        # Создаем временный файл
        temp_file = NamedTemporaryFile(delete=False, mode="w", suffix=".conf")
        temp_file_path = temp_file.name
        try:
            temp_file.write(config_text) 
        finally:
            temp_file.close()

        # Создаем фоновую задачу на удаление файла после отправки
        background_task = BackgroundTask(os.remove, temp_file_path)

        # Отправляем файл и привязываем удаление после отправки
        return FileResponse(
            path=temp_file_path,
            filename=file_name,
            media_type="text/plain",
            background=background_task,
        )

    except Exception as e:
        # В случае ошибки, если файл был создан, удаляем его
        if "temp_file_path" in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(
            status_code=500, detail=f"Error generating configuration file: {str(e)}"
        )


@router.post("/")
async def create_client(client: ClientCreate):
    """
    Создать нового клиента.
    """
    try:
        # Проверяем существование подсети
        subnet = await db.subnet.find_unique(where={"id": str(client.subnetId)})
        if not subnet:
            raise HTTPException(status_code=404, detail="Subnet not found")

        # Валидация IP-адреса
        try:
            network = ipaddress.IPv4Network(
                f"{subnet.subnetIp}/{subnet.subnetMask}", strict=True
            )
            client_ip = ipaddress.IPv4Address(client.clientIp)

            if client_ip not in network:
                raise HTTPException(
                    status_code=400, detail="Client IP is not within the subnet range"
                )
            if client_ip == network.network_address:
                raise HTTPException(
                    status_code=400, detail="Client IP cannot be the network address"
                )
            if client_ip == network.broadcast_address:
                raise HTTPException(
                    status_code=400, detail="Client IP cannot be the broadcast address"
                )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid IP address: {str(e)}")

        # 1. Создаём клиента в БД с временными значениями
        created_client = await db.client.create(
            data={
                "name": client.name,
                "clientIp": client.clientIp,
                "publicKey": ".",
                "privateKeyRef": ".",
                "subnetId": str(client.subnetId),
                "userId": str(client.userId),
            },
            include={"user": True, "subnet": True},
        )

        # 2. Генерация ключей и сохранение в файлы
        client_dir = WG_CLIENTS_DIR / created_client.id
        client_dir.mkdir(parents=True, exist_ok=True)

        private_key = subprocess.check_output("wg genkey", shell=True).decode().strip()
        public_key = (
            subprocess.check_output(f"echo {private_key} | wg pubkey", shell=True)
            .decode()
            .strip()
        )

        private_key_path = client_dir / "privatekey"
        public_key_path = client_dir / "publickey"

        private_key_path.write_text(private_key)
        public_key_path.write_text(public_key)

        # 3. Добавление в конфигурацию wg0.conf
        peer_config = f"""

[Peer]
PublicKey = {public_key}
AllowedIPs = {client.clientIp}/{subnet.subnetMask}
"""
        with open(WG_CONF_PATH, "a") as f:
            f.write(peer_config)

        # 4. Обновляем клиента с реальными данными
        updated_client = await db.client.update(
            where={"id": created_client.id},
            data={"publicKey": public_key, "privateKeyRef": str(private_key_path)},
            include={"user": True, "subnet": True},
        )

        return updated_client

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating client: {str(e)}")


@router.post("/{client_id}/enable", dependencies=[Depends(require_admin)])
async def enable_client(data: ClientEnableDisable):
    """
    Включить клиента (Только для администраторов).
    """
    try:
        client = await db.client.find_unique(
            where={"id": str(data.clientId)}, include={"subnet": True}
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        if client.isEnabled:
            raise HTTPException(status_code=400, detail="Client is already enabled")
        # ✅ Добавляем клиента как PEER
        add_peer_to_config(client.publicKey, client.clientIp, client.subnet.subnetMask)

        # Обновляем флаг в БД
        updated_client = await db.client.update(
            where={"id": str(data.clientId)}, data={"isEnabled": True}
        )

        return {"clientId": updated_client.id, "status": "enabled"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enabling client: {str(e)}")


@router.post("/{client_id}/disable", dependencies=[Depends(require_admin)])
async def disable_client(data: ClientEnableDisable):
    """
    Отключить клиента (Только для администраторов).
    """
    try:
        client = await db.client.find_unique(where={"id": str(data.clientId)})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        if not client.isEnabled:
            raise HTTPException(status_code=400, detail="Client is already disabled")

        # ✅ Удаляем клиента из wg0.conf
        remove_peer_from_config(client.publicKey)

        updated_client = await db.client.update(
            where={"id": str(data.clientId)}, data={"isEnabled": False}
        )

        return {"clientId": updated_client.id, "status": "disabled"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error disabling client: {str(e)}")


@router.put(
    "/{client_id}/name",
    # dependencies=[Depends(require_admin)],
)
async def update_client_name(client_id: UUID, data: ClientUpdateName):
    """
    Обновить имя клиента .
    """
    try:
        # Ищем клиента по ID
        client = await db.client.find_unique(where={"id": str(client_id)})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Обновляем имя клиента в базе данных
        updated_client = await db.client.update(
            where={"id": str(client_id)},
            data={"name": data.name},
            include={"user": True, "subnet": True},
        )

        return updated_client

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating client name: {str(e)}"
        )


@router.put(
    "/{client_id}/address",
    # dependencies=[Depends(require_admin)],
)
async def update_client_address(client_id: UUID, data: ClientUpdateAddress):
    """
    Обновить IP-адрес клиента .
    """
    try:
        # Ищем клиента по ID
        client = await db.client.find_unique(
            where={"id": str(client_id)}, include={"subnet": True}
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        try:
            # Сеть клиента (по его подсети)
            subnet_network = ipaddress.IPv4Network(
                f"{client.subnet.subnetIp}/{client.subnet.subnetMask}", strict=True
            )
            client_ip = ipaddress.IPv4Address(data.clientIp)

            if client_ip not in subnet_network:
                raise HTTPException(
                    status_code=400,
                    detail="Client IP is not within the client's subnet",
                )

            if client_ip == subnet_network.network_address:
                raise HTTPException(
                    status_code=400,
                    detail="Client IP cannot be the network address of the subnet",
                )

            if client_ip == subnet_network.broadcast_address:
                raise HTTPException(
                    status_code=400,
                    detail="Client IP cannot be the broadcast address of the subnet",
                )

        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid client IP address: {str(e)}"
            )
        # Обновляем IP-адрес в конфигурации
        update_allowed_ips_in_config(
            client.publicKey, data.clientIp, client.subnet.subnetMask
        )
        # Обновляем IP-адрес клиента в базе данных
        updated_client = await db.client.update(
            where={"id": str(client_id)},
            data={"clientIp": data.clientIp},
            include={"user": True, "subnet": True},
        )

        return updated_client

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating client IP: {str(e)}"
        )


@router.delete("/{client_id}", dependencies=[Depends(require_admin)])
async def delete_client(client_id: UUID):
    """
    Удалить клиента (Только для администраторов).
    """
    try:
        # Ищем клиента по ID
        client = await db.client.find_unique(where={"id": str(client_id)})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # ✅ Удаляем PEER из wg0.conf по publicKey
        remove_peer_from_config(client.publicKey)

        # 2. Удаляем ключи
        client_key_dir = WG_CLIENTS_DIR / str(client_id)
        if client_key_dir.exists():
            shutil.rmtree(client_key_dir)

        # Удаляем клиента из базы данных
        await db.client.delete(where={"id": str(client_id)})

        return {"clientId": str(client_id), "status": "deleted"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting client: {str(e)}")



