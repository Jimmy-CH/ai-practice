import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

import seed_sample_repo
from app import models  # noqa: F401  确保模型在 metadata 中注册
from app.api.router import api_router
from app.config import settings
from app.database import AsyncSessionLocal, Base, engine
from app.models import Repo
from app.services import pipeline_service
from app.static_serving import register_static

logger = logging.getLogger(__name__)


async def _ensure_sample_repo() -> None:
    """首次启动时幂等生成示例仓库并注册为 is_sample=True 的仓库记录。"""
    repo_path = await asyncio.to_thread(seed_sample_repo.generate, Path(settings.sample_repo_dir))
    resolved = str(repo_path.resolve())
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(Repo).where(Repo.path == resolved))).scalar_one_or_none()
        if existing is None:
            name = "order-center" if repo_path.name == seed_sample_repo.REPO_DIR_NAME else repo_path.name
            db.add(Repo(name=name, path=resolved, is_sample=True))
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 上次进程遗留的 pending/running 运行已无任务在跑，启动时先收敛为失败
    interrupted = await pipeline_service.recover_stale_runs()
    if interrupted:
        logger.warning("已将 %s 条上次中断的运行标记为失败", interrupted)
    await _ensure_sample_repo()
    yield
    await pipeline_service.shutdown_runs()


app = FastAPI(title="释文 DocRelease", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router)

register_static(app, Path(settings.static_dir))
