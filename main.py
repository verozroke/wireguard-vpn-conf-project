from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from prisma import Prisma

app = FastAPI()


class CreatePostDto(BaseModel):
    title: str
    content: Optional[str] = None
    published: bool


@app.get("/")
def list_posts():
    db = Prisma()
    db.connect()

    posts = db.post.find_many()

    db.disconnect()

    return posts


@app.post("/")
def create_post(dto: CreatePostDto):
    db = Prisma()
    db.connect()

    post = db.post.create(data=dto.model_dump(exclude_none=True))

    db.disconnect()

    return post