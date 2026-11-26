from fastapi import APIRouter

from app.api import auth, conversations, messages, users

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)


@api_router.get("/health")
async def health():
    return {"status": "ok"}
