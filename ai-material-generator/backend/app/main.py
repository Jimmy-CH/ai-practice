from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.generator import router as generator_router

app = FastAPI(title="AI 运营物料智能生成助手")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(generator_router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
