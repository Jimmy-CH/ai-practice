
from fastapi import APIRouter
from app.database import async_session
from app.schemas.user import RegisterRequest, LoginRequest
from app.services.user_service import register_user, login_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register")
async def register(req: RegisterRequest):
    async with async_session() as session:
        return await register_user(session, req.username, req.password)


@router.post("/login")
async def login(req: LoginRequest):
    async with async_session() as session:
        return await login_user(session, req.username, req.password)

