"""应用启动引导：建表 + 轻量迁移 + 内置账号种子，供 main 的 lifespan 调用。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine, Base, AsyncSessionLocal
from app.services.auth_service import seed_users


async def _migrate_schema(conn) -> None:
    """为既有 SQLite 库补加 create_all 不会新增的列（项目无 alembic 的轻量迁移）。"""
    result = await conn.execute(text("PRAGMA table_info(material_assets)"))
    columns = {row[1] for row in result.fetchall()}
    if not columns:
        return
    if "reviewed_by" not in columns:
        await conn.execute(text("ALTER TABLE material_assets ADD COLUMN reviewed_by INTEGER REFERENCES users(id)"))
    if "reviewed_at" not in columns:
        await conn.execute(text("ALTER TABLE material_assets ADD COLUMN reviewed_at DATETIME"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_schema(conn)
    async with AsyncSessionLocal() as session:
        await seed_users(session)
    yield
