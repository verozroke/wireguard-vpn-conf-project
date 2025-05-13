import os
import subprocess
from pathlib import Path


def setup_wireguard():
    WG_CONF_DIR = Path("wg-conf")
    PRIVATE_KEY_PATH = WG_CONF_DIR / "privatekey"
    PUBLIC_KEY_PATH = WG_CONF_DIR / "publickey"
    WG0_CONF_PATH = WG_CONF_DIR / "wg0.conf"

    LISTEN_PORT = 51820
    WG_INTERFACE_IP = "10.0.0.1/24"

    # Создаём директорию, если её нет
    WG_CONF_DIR.mkdir(parents=True, exist_ok=True)

    # Проверка: надо ли генерировать ключи и конфиг
    should_create_conf = (
        not PRIVATE_KEY_PATH.exists()
        or not PUBLIC_KEY_PATH.exists()
        or not WG0_CONF_PATH.exists()
    )

    if should_create_conf:
        try:
            # Генерация приватного ключа
            private_key = (
                subprocess.check_output("wg genkey", shell=True).decode().strip()
            )
            with open(PRIVATE_KEY_PATH, "w") as f:
                f.write(private_key)

            # Генерация публичного ключа на основе приватного
            public_key = (
                subprocess.check_output(f"echo {private_key} | wg pubkey", shell=True)
                .decode()
                .strip()
            )
            with open(PUBLIC_KEY_PATH, "w") as f:
                f.write(public_key)

            # Создание конфигурационного файла wg0.conf
            wg0_conf = f"""[Interface]
PrivateKey = {private_key}
Address = {WG_INTERFACE_IP}
ListenPort = {LISTEN_PORT}
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o ens3 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o ens3 -j MASQUERADE
"""
            with open(WG0_CONF_PATH, "w") as f:
                f.write(wg0_conf)

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"WireGuard setup failed: {e}")

    # Возврат ключей (для логов, переменных среды и т.д.)
    private_key = PRIVATE_KEY_PATH.read_text().strip()
    public_key = PUBLIC_KEY_PATH.read_text().strip()

    return {"WG_PRIVATE_KEY": private_key, "WG_PUBLIC_KEY": public_key}
