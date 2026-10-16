import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.routing import Match

from app.api.router import register_routers
from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.services.auth_service import seed_users


SENSITIVE_KEYS = {"password", "token", "access_token", "refresh_token", "api_key", "authorization"}
BODY_LOG_MAX_LENGTH = 500


def _sanitize_body(raw: bytes, content_type: str) -> str:
    """将请求体转为可安全打印的文本，敏感字段与表单数据脱敏，超长截断。"""
    if not raw:
        return ""
    if content_type.startswith("application/x-www-form-urlencoded") or content_type.startswith("multipart/form-data"):
        return "<form-data redacted>"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return "<binary>"
    if content_type.startswith("application/json"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data = {
                    key: ("***" if key.lower() in SENSITIVE_KEYS else value)
                    for key, value in data.items()
                }
            text = json.dumps(data, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            pass
    if len(text) > BODY_LOG_MAX_LENGTH:
        return text[:BODY_LOG_MAX_LENGTH] + f"...(truncated, total {len(text)} chars)"
    return text


logger = logging.getLogger("app.main")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


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


app = FastAPI(title="AI 运营物料智能生成助手", lifespan=lifespan)


@app.middleware("http")
async def log_request_duration(request: Request, call_next):
    start = time.perf_counter()
    method = request.method
    path = request.url.path
    query = request.url.query
    client_ip = request.client.host if request.client else "-"
    content_type = request.headers.get("content-type", "")
    body_preview = ""
    if method in ("POST", "PUT", "PATCH"):
        raw_body = await request.body()
        body_preview = _sanitize_body(raw_body, content_type)
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    suffix = f"?{query}" if query else ""
    body_part = f" body={body_preview}" if body_preview else ""
    logger.info(
        f"[{method}] {path}{suffix} ip={client_ip}{body_part} "
        f"-> {response.status_code} ({duration_ms:.2f}ms)"
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# 全部接口路由集中在 app/api/router.py 注册，便于一文件总览所有接口
register_routers(app)


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

    def _partial_match_methods(path: str, method: str) -> list[str]:
        """路径已注册但方法不匹配时返回允许的方法，复刻原生 405/Allow 语义。"""
        scope = {"type": "http", "path": path, "method": method, "headers": []}
        methods: set[str] = set()
        for route in app.routes:
            if getattr(route, "path", None) == "/{full_path:path}":
                continue
            match, _child = route.matches(scope)
            if match == Match.PARTIAL:
                methods |= _collect_methods(route, scope)
        return sorted(methods)

    def _collect_methods(route, scope: dict) -> set[str]:
        """聚合路由允许的方法；兼容 FastAPI 0.141 _IncludedRouter 聚合路由。

        _IncludedRouter 的 prefix 存于 include_context 而非子路由 path，
        直接遍历 original_router.routes 匹配会全部 NONE，
        必须走 effective_candidates()（已应用 prefix 的有效候选）。
        """
        methods = getattr(route, "methods", None)
        if methods:
            return {m for m in methods if m != "HEAD"}
        result: set[str] = set()
        if hasattr(route, "effective_candidates"):
            for candidate in route.effective_candidates():
                match, _child = candidate.matches(scope)
                if match != Match.NONE:
                    result |= _collect_methods(candidate, scope)
            return result
        inner = getattr(route, "original_router", None)
        for sub in getattr(inner, "routes", None) or []:
            match, _child = sub.matches(scope)
            if match != Match.NONE:
                result |= _collect_methods(sub, scope)
        return result

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
            else:
                allowed = _partial_match_methods("/" + full_path, request.method)
                if allowed:
                    return JSONResponse(
                        {"detail": "Method Not Allowed"},
                        status_code=405,
                        headers={"Allow": ", ".join(allowed)},
                    )
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if request.method in ("GET", "HEAD"):
            candidate = (static_dir / full_path).resolve()
            if full_path and candidate.is_file() and candidate.is_relative_to(static_dir.resolve()):
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")
        return JSONResponse({"detail": "Not Found"}, status_code=404)


register_static(app, Path(settings.static_dir))
