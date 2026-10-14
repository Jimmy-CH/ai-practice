from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  确保模型在 metadata 中注册
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="释文 DocRelease", lifespan=lifespan)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
