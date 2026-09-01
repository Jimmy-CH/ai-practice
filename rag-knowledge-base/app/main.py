# app/main.py
import logging
from fastapi import FastAPI
from app.api.endpoints import router
from app.core.metrics import setup_metrics
from contextlib import asynccontextmanager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("RAG_API")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行：初始化向量库连接等
    logger.info("RAG Service is starting...")
    yield
    # 关闭时执行：释放资源等
    logger.info("RAG Service is shutting down...")

app = FastAPI(title="企业级 RAG 知识库问答 API", version="2.0.0", lifespan=lifespan)

# 挂载监控指标
setup_metrics(app)

# 挂载业务路由
app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}
