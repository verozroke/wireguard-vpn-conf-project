import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import router
from api.models.db import db
from wireguard.setup import setup_wireguard


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

origins = ["http://127.0.0.1:3000", "https://wg-vpn-panel.vercel.app"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router)
