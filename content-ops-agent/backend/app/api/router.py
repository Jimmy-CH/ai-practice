from fastapi import APIRouter

from app.api.delivery import router as delivery_router
from app.api.generation import router as generation_router
from app.api.projects import router as projects_router
from app.api.sources import router as sources_router, webhook_router

api_router = APIRouter()
api_router.include_router(projects_router)
api_router.include_router(generation_router)
api_router.include_router(delivery_router)
api_router.include_router(sources_router)
api_router.include_router(webhook_router)
