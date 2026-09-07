from fastapi import APIRouter
from app.api import agent, auth
from app.api.datasource import router as datasource_router
from app.users import router as users_router
from app.api.conversation import router as conv_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users_router.router)
api_router.include_router(agent.router)
api_router.include_router(conv_router)
api_router.include_router(datasource_router)
