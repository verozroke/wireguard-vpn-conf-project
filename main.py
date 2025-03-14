from fastapi import FastAPI
from api import router
from api.models.db import db

app = FastAPI(title="Diploma Project")

@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()

app.include_router(router)
