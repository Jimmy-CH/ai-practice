import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, verify_password
from app.database import get_db
from app.models.content import Token, User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginPayload(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(payload: LoginPayload, db: AsyncSession = Depends(get_db)) -> dict:
    user = (await db.scalars(select(User).where(User.username == payload.username))).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = uuid.uuid4().hex
    db.add(Token(token=token, user_id=user.id))
    await db.commit()
    return {"token": token, "username": user.username, "role": user.role}


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> dict:
    return {"username": user.username, "role": user.role}
