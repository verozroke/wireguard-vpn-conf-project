import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import router
from api.models.db import db
from wireguard.setup import setup_wireguard
import ssl

# TODO: change the project directory structure of API routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    await db.connect()
    print("Database connected successfully")

    wg_keys = setup_wireguard()
    os.environ["WG_PRIVATE_KEY"] = wg_keys["WG_PRIVATE_KEY"]
    os.environ["WG_PUBLIC_KEY"] = wg_keys["WG_PUBLIC_KEY"]
    yield  # This is where the app runs

    # Shutdown logic
    await db.disconnect()
    print("Database disconnected successfully")


app = FastAPI(title="Diploma Project", lifespan=lifespan)
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain('cert.pem', keyfile='key.pem')
origins = ["http://127.0.0.1:3000", "https://wg-vpn-panel.vercel.app"]

# Добавляем CORS миддлвару
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # откуда можно отправлять запросы
    allow_credentials=True,  # разрешать куки, авторизацию и т.д.
    allow_methods=["*"],  # разрешить все методы (GET, POST, PUT и т.д.)
    allow_headers=["*"],  # разрешить все заголовки
)


app.include_router(router)
