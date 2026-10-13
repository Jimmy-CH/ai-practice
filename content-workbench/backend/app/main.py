import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.auth import seed_users
from app.database import Base, SessionLocal, engine
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("content_workbench")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Content Workbench 启动中...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        await seed_users(db)
    logger.info("数据库初始化完成")
    yield
    logger.info("Content Workbench 关闭")


app = FastAPI(title="Content Workbench", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
        duration = (time.time() - start) * 1000
        logger.info("%s %s %s - %.2fms", request.method, request.url.path, response.status_code, duration)
        return response
    except Exception as error:
        duration = (time.time() - start) * 1000
        logger.error("%s %s 未捕获异常: %s - %.2fms", request.method, request.url.path, error, duration, exc_info=True)
        raise


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    logger.error("未捕获的全局异常", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "内部服务器错误"})


app.include_router(api_router, prefix="/api")
