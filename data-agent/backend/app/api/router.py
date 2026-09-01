from fastapi import APIRouter
from app.api import agent

api_router = APIRouter(prefix="/api")
api_router.include_router(agent.router)
