import ipaddress
from pathlib import Path
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
WG_CONF_DIR = Path("/etc/wireguard")
WG_CONF_PATH = WG_CONF_DIR / "wg0.conf"


def update_config_with_subnet_and_iptables(data: SubnetCreate):
    if not WG_CONF_PATH.exists():
        raise HTTPException(status_code=500, detail="wg0.conf not found")

    with open(WG_CONF_PATH, "r") as f:
        lines = f.readlines()

    new_address = f"{data.subnetIp}/{data.subnetMask}"
    updated_lines = []
    address_line_found = False

    for line in lines:
        if line.strip().startswith("Address ="):
            address_line_found = True
            existing_addresses = line.strip().split("=", 1)[1].strip().split(",")
            existing_addresses = [a.strip() for a in existing_addresses]

            if new_address in existing_addresses:
                raise HTTPException(
                    status_code=400, detail="Subnet already listed in configuration"
                )

            existing_addresses.append(new_address)
            updated_line = f"Address = {', '.join(existing_addresses)}\n"
            updated_lines.append(updated_line)
        else:
            updated_lines.append(line)

    if not address_line_found:
        raise HTTPException(status_code=500, detail="Address line not found in config")

    existing_subnets = [a.strip() for a in existing_addresses if a.strip()]
    isolation_rules_up = []
    isolation_rules_down = []
    for subnet in existing_subnets:
        if subnet == new_address:
            continue
        isolation_rules_up.append(
            f"iptables -I FORWARD -s {subnet} -d {new_address} -j DROP"
        )
        isolation_rules_up.append(
            f"iptables -I FORWARD -s {new_address} -d {subnet} -j DROP"
        )
        isolation_rules_down.append(
            f"iptables -D FORWARD -s {subnet} -d {new_address} -j DROP"
        )
        isolation_rules_down.append(
            f"iptables -D FORWARD -s {new_address} -d {subnet} -j DROP"
        )

    def update_iptables_block(lines, key, new_rules):
        updated = []
        found = False
        for line in lines:
            if line.strip().startswith(f"{key} ="):
                found = True
                parts = line.strip().split("=", 1)
                existing_cmds = parts[1].strip().split(";")
                existing_cmds = [cmd.strip() for cmd in existing_cmds if cmd.strip()]
                updated_line = f"{key} = {'; '.join(new_rules + existing_cmds)}\n"
                updated.append(updated_line)
            else:
                updated.append(line)
        if not found:
            raise HTTPException(
                status_code=500, detail=f"{key} line not found in config"
            )
        return updated

    updated_lines = update_iptables_block(updated_lines, "PostUp", isolation_rules_up)
    updated_lines = update_iptables_block(
        updated_lines, "PostDown", isolation_rules_down
    )

    with open(WG_CONF_PATH, "w") as f:
        f.writelines(updated_lines)


def update_subnet_ip_in_conf(old_ip: str, new_ip: str, mask: int):
    """
    Обновляет IP-адрес подсети в конфигурационном файле WireGuard.
    Заменяет старый IP в строке Address= и во всех iptables правилах в PostUp и PostDown.
    """
    if not WG_CONF_PATH.exists():
        raise HTTPException(status_code=500, detail="wg0.conf not found")

    old_cidr = f"{old_ip}/{mask}"
    new_cidr = f"{new_ip}/{mask}"

    with open(WG_CONF_PATH, "r") as f:
        lines = f.readlines()

    updated_lines = []

    for line in lines:
        stripped = line.strip()

        # Обновляем строку Address =
        if stripped.startswith("Address ="):
            parts = stripped.split("=", 1)
            addresses = [a.strip() for a in parts[1].split(",")]
            updated_addresses = [
                new_cidr if addr == old_cidr else addr for addr in addresses
            ]
            updated_line = f"Address = {', '.join(updated_addresses)}\n"
            updated_lines.append(updated_line)

        # Обновляем iptables правила в PostUp и PostDown
        elif stripped.startswith("PostUp =") or stripped.startswith("PostDown ="):
            updated_line = line.replace(old_cidr, new_cidr).replace(old_ip, new_ip)
            updated_lines.append(updated_line)

        # Все остальные строки — без изменений
        else:
            updated_lines.append(line)

    with open(WG_CONF_PATH, "w") as f:
        f.writelines(updated_lines)


def update_subnet_mask_in_conf(subnet_ip: str, old_mask: int, new_mask: int):
    if not WG_CONF_PATH.exists():
        raise HTTPException(status_code=500, detail="wg0.conf not found")

    old_cidr = f"{subnet_ip}/{old_mask}"
    new_cidr = f"{subnet_ip}/{new_mask}"

    with open(WG_CONF_PATH, "r") as f:
        lines = f.readlines()

    updated_lines = []

    for line in lines:
        # Обновляем Address=
        if line.strip().startswith("Address ="):
            parts = line.strip().split("=", 1)
            addresses = [a.strip() for a in parts[1].split(",")]
            updated_addresses = [
                new_cidr if addr == old_cidr else addr for addr in addresses
            ]
            updated_lines.append(f"Address = {', '.join(updated_addresses)}\n")
        # Обновляем iptables в PostUp/PostDown
        elif line.strip().startswith("PostUp =") or line.strip().startswith(
            "PostDown ="
        ):
            updated_line = line.replace(old_cidr, new_cidr)
            updated_lines.append(updated_line)
        else:
            updated_lines.append(line)

    with open(WG_CONF_PATH, "w") as f:
        f.writelines(updated_lines)


async def remove_subnet_from_conf(subnet_ip: str, mask: int):
    if not WG_CONF_PATH.exists():
        raise HTTPException(status_code=500, detail="wg0.conf not found")

    cidr = f"{subnet_ip}/{mask}"

    with open(WG_CONF_PATH, "r") as f:
        lines = f.readlines()

    updated_lines = []
    has_other_subnets = await db.subnet.find_many(
        where={"subnetIp": {"not": subnet_ip}}
    )

    for line in lines:
        if line.strip().startswith("Address ="):
            addresses = [a.strip() for a in line.strip().split("=", 1)[1].split(",")]
            addresses = [a for a in addresses if a != cidr]
            updated_lines.append(f"Address = {', '.join(addresses)}\n")

        elif line.strip().startswith("PostUp =") or line.strip().startswith(
            "PostDown ="
        ):
            if not has_other_subnets:
                # Reset to default rules
                if "PostUp" in line:
                    updated_lines.append(
                        "PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o ens3 -j MASQUERADE\n"
                    )
                else:
                    updated_lines.append(
                        "PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o ens3 -j MASQUERADE\n"
                    )
            else:
                # Remove subnet references only
                updated_line = (
                    line.replace(f"-s {cidr} -d", "")
                    .replace(f"-s {subnet_ip} -d {cidr}", "")
                    .replace(f"{cidr}", "")
                    .replace(f"{subnet_ip}", "")
                )
                updated_lines.append(updated_line)
        else:
            updated_lines.append(line)

    with open(WG_CONF_PATH, "w") as f:
        f.writelines(updated_lines)


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
        if data.subnetMask < 0 or data.subnetMask > 32:
            raise HTTPException(
                status_code=400, detail="Subnet mask must be between 0 and 32"
            )

        try:
            network = ipaddress.IPv4Network(f"{data.subnetIp}/{data.subnetMask}", strict=True)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid subnet IP: {str(e)}")

        existing_subnet = await db.subnet.find_unique(where={"subnetIp": data.subnetIp})
        if existing_subnet:
            raise HTTPException(
                status_code=400, detail="Subnet with this IP already exists"
            )

        existing_name_subnet = await db.subnet.find_first(where={"name": data.name})
        if existing_name_subnet:
            raise HTTPException(
                status_code=400, detail="Subnet with this name already exists"
            )

        # Вычисляем первый usable IP в подсети
        all_hosts = list(network.hosts())
        if not all_hosts:
            raise HTTPException(status_code=400, detail="No usable IPs in this subnet")

        first_host_ip = all_hosts[0]
        firstSubnetIp = f"{first_host_ip}/{data.subnetMask}"
        print('check 1')
        update_config_with_subnet_and_iptables({
          'name': data.name,
          'subnetIp': firstSubnetIp,
          'subnetMask': data.subnetMask,
          'userId': data.userId
        })
        print('check 2')
        

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
        # Получаем подсеть вместе с клиентами
        subnet = await db.subnet.find_unique(
            where={"id": str(subnet_id)}, include={"clients": True}
        )
        if not subnet:
            raise HTTPException(status_code=404, detail="Subnet not found")

        if subnet.clients and len(subnet.clients) > 0:
            raise HTTPException(
                status_code=400,
                detail="You can't change the subnet IP address when there's clients attached to this subnet",
            )

        try:
            old_network = ipaddress.IPv4Network(f"{subnet.subnetIp}/{subnet.subnetMask}", strict=True)
            new_network = ipaddress.IPv4Network(f"{data.subnetIp}/{subnet.subnetMask}", strict=True)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid subnet IP: {str(e)}")

        # ✅ Получаем первый usable IP в старой и новой подсети
        old_first_ip = str(list(old_network.hosts())[0])
        new_first_ip = str(list(new_network.hosts())[0])

        # ✅ Обновляем конфиг-файл (Address= и iptables)
        update_subnet_ip_in_conf(
            old_ip=old_first_ip,
            new_ip=new_first_ip,
            mask=subnet.subnetMask
        )

        # Обновляем IP-адрес в базе
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

        # ❌ Если есть клиенты — нельзя менять маску
        if subnet.clients and len(subnet.clients) > 0:
            raise HTTPException(
                status_code=400,
                detail="You can't change the subnet mask when there's clients attached to this subnet",
            )

        # ❌ Проверка, что subnetIp остаётся сетевым адресом при новой маске
        try:
            old_network = ipaddress.IPv4Network(
                f"{subnet.subnetIp}/{subnet.subnetMask}", strict=True
            )
            new_network = ipaddress.IPv4Network(
                f"{subnet.subnetIp}/{data.subnetMask}", strict=True
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Your new subnet mask is not compatible with subnetIP. Change the SubnetIp",
            )
            
        # ✅ Получаем первый usable IP
        first_ip = str(list(old_network.hosts())[0])  # или new_network.hosts()[0], по сути одинаково

        # ✅ Обновляем маску в конфиге и iptables
        update_subnet_mask_in_conf(
            subnet_ip=first_ip,
            old_mask=subnet.subnetMask,
            new_mask=data.subnetMask,
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
        # Получаем подсеть с клиентами
        subnet = await db.subnet.find_unique(
            where={"id": str(subnet_id)}, include={"clients": True}
        )
        if not subnet:
            raise HTTPException(status_code=404, detail="Subnet not found")

        # ❌ Нельзя удалить, если есть клиенты
        if subnet.clients and len(subnet.clients) > 0:
            raise HTTPException(
                status_code=400,
                detail="You can't delete a subnet that has clients attached to it",
            )

        # ✅ Получаем usable IP (обычно первый хост в подсети)
        try:
            network = ipaddress.IPv4Network(
                f"{subnet.subnetIp}/{subnet.subnetMask}", strict=True
            )
            first_usable_ip = str(next(network.hosts()))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid subnet: {str(e)}")

        # ✅ Удаляем из конфигурации (Address= и iptables)
        await remove_subnet_from_conf(subnet_ip=first_usable_ip, mask=subnet.subnetMask)

        # ✅ Удаляем из базы
        await db.subnet.delete(where={"id": str(subnet_id)})

        return {"subnetId": subnet_id, "status": "deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting subnet: {str(e)}")
