"""API 路由汇总：main 只负责应用装配，不直接声明业务路由。"""

from fastapi import APIRouter

from app.api import repos, runs

api_router = APIRouter()
api_router.include_router(repos.router)
api_router.include_router(runs.router)


@api_router.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
