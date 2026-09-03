import logging

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# 异步引擎（供 FastAPI 异步路由使用）
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,       # 每次从连接池获取连接前先发 ping 检测是否可用
    pool_recycle=1800,        # 每 30 分钟回收连接，避免数据库侧超时断开
)

# 同步引擎（供 Agent 工具使用，LangChain tool 不支持 async）
SYNC_DB_URL = settings.DATABASE_URL.replace("+aiosqlite", "").replace("+aiomysql", "")
sync_engine = create_engine(
    SYNC_DB_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库 session。"""
    async with async_session() as session:
        try:
            logger.debug("获取数据库 session")
            yield session
        except Exception as e:
            logger.error(f"数据库 session 异常: {e}", exc_info=True)
            raise
