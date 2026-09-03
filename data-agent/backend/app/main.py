import asyncio
import time
import uuid
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    try:
        logger.info("应用正在关闭...")
        await engine.dispose()
        logger.info("数据库连接已关闭")
    except asyncio.CancelledError:
        logger.warning("应用关闭被中断")


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
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

    try:
        response = await call_next(request)
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"[{request_id}] <-- 500 {request.method} {request.url.path} ({duration:.1f}ms) 异常: {e}"
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误"},
            headers={"X-Request-ID": request_id},
        )

    duration = (time.time() - start_time) * 1000
    logger.info(
        f"[{request_id}] <-- {response.status_code} {request.method} {request.url.path} ({duration:.1f}ms)"
    )

    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(api_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """健康检查端点，用于部署存活探测。"""
    return {"status": "ok"}
