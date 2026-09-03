import time
import uuid
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base
from app.api.router import api_router
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("应用启动中，正在初始化数据库...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库初始化完成")
    yield
    logger.info("应用正在关闭...")


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有 HTTP 请求的日志。"""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    logger.info(f"[{request_id}] --> {request.method} {request.url.path}")

    response = await call_next(request)

    duration = (time.time() - start_time) * 1000
    logger.info(
        f"[{request_id}] <-- {response.status_code} {request.method} {request.url.path} ({duration:.1f}ms)"
    )

    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(api_router)
