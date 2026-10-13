from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.generator import router as generator_router
from app.api.auth import router as auth_router
from app.database import engine, Base, AsyncSessionLocal
from app.services.auth_service import seed_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_users(session)
    yield


app = FastAPI(title="AI 运营物料智能生成助手", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api")
app.include_router(generator_router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
