from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import settings
from app.database import init_db
from app.services import chat_service, llm_client
from app.services.stream_manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await chat_service.recover_stale_streaming()
    llm_client.init_client()
    yield
    manager.shutdown()
    await llm_client.close_client()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.include_router(api_router)

if settings.FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(settings.FRONTEND_DIR), html=True), name="frontend")
