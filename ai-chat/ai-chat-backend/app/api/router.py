
from fastapi import APIRouter
from app.api import auth, users, chat

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(chat.router)
