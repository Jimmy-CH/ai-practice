import json
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.api.generator import router as generator_router
from app.api.auth import router as auth_router
from app.api.materials import router as materials_router
from app.api.analyses import router as analyses_router
from app.api.generated_materials import router as generated_materials_router
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
app.include_router(auth_router, prefix="/api")
app.include_router(materials_router, prefix="/api")
app.include_router(analyses_router, prefix="/api/analyses")
app.include_router(generated_materials_router, prefix="/api/generated-materials")
app.include_router(generator_router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
