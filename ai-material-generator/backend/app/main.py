import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.generator import router as generator_router
from app.api.auth import router as auth_router
from app.api.materials import router as materials_router
from app.api.analyses import router as analyses_router
from app.api.generated_materials import router as generated_materials_router
from app.database import engine, Base, AsyncSessionLocal
from app.services.auth_service import seed_users


logger = logging.getLogger("app.main")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_users(session)
    yield


app = FastAPI(title="AI 运营物料智能生成助手", lifespan=lifespan)


@app.middleware("http")
async def log_request_duration(request: Request, call_next):
    start = time.perf_counter()
    method = request.method
    path = request.url.path
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(f"[{method}] {path} -> {response.status_code} ({duration_ms:.2f}ms)")
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
