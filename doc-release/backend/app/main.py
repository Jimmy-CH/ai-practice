import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Match
from sqlalchemy import select

import seed_sample_repo
from app import models  # noqa: F401  确保模型在 metadata 中注册
from app.api import repos as repos_api
from app.api import runs as runs_api
from app.config import settings
from app.database import AsyncSessionLocal, Base, engine
from app.models import Repo


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
    await _ensure_sample_repo()
    yield


app = FastAPI(title="释文 DocRelease", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


app.include_router(repos_api.router)
app.include_router(runs_api.router)


def register_static(app: FastAPI, static_dir: Path) -> None:
    """挂载前端产物与 SPA 回退；目录不存在时跳过（开发模式不受影响）。

    必须在所有 API 路由注册之后调用，避免 catch-all 拦截 /api。
    """
    if not static_dir.is_dir():
        return
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # catch-all 会拦截 Starlette 的尾斜杠重定向，这里用框架真实路由匹配补偿该行为
    # （include_router 生成的路由无 path 属性，不能用路径字符串白名单）
    def _matches_other_route(path: str, method: str) -> bool:
        scope = {"type": "http", "path": path, "method": method, "headers": []}
        for route in app.routes:
            if getattr(route, "path", None) == "/{full_path:path}":
                continue
            match, _child = route.matches(scope)
            if match != Match.NONE:
                return True
        return False

    @app.api_route(
        "/{full_path:path}",
        methods=["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        include_in_schema=False,
    )
    async def spa_fallback(request: Request, full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            if full_path.endswith("/"):
                target = "/" + full_path.rstrip("/")
                if _matches_other_route(target, request.method):
                    query = request.scope.get("query_string", b"")
                    location = target + (f"?{query.decode('latin-1')}" if query else "")
                    return RedirectResponse(location, status_code=307)
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if request.method in ("GET", "HEAD"):
            candidate = (static_dir / full_path).resolve()
            if full_path and candidate.is_file() and candidate.is_relative_to(static_dir.resolve()):
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")
        return JSONResponse({"detail": "Not Found"}, status_code=404)


register_static(app, Path(settings.static_dir))
