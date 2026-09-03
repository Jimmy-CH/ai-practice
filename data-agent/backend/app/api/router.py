from fastapi import APIRouter
from app.api import agent, auth
from app.users import router as users_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users_router.router)
api_router.include_router(agent.router)
