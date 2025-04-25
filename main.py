from contextlib import asynccontextmanager
from fastapi import FastAPI
from api import router
from api.models.db import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    await db.connect()
    print("Database connected successfully")
    
    yield  # This is where the app runs

    # Shutdown logic
    await db.disconnect()
    print("Database disconnected successfully")
app = FastAPI(title="Diploma Project",  lifespan=lifespan)


app.include_router(router)
