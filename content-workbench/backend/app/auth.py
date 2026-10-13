import hashlib
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.content import User

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(8).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 10000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
    except ValueError:
        return False
    return hash_password(password, salt) == stored


async def seed_users(db: AsyncSession) -> None:
    if not (await db.scalars(select(User).limit(1))).first():
        db.add_all([
            User(username="editor", password_hash=hash_password("editor123"), role="editor"),
            User(username="reviewer", password_hash=hash_password("review123"), role="reviewer"),
        ])
        await db.commit()


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer), db: AsyncSession = Depends(get_db)) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    from app.models.content import Token

    row = (await db.scalars(select(Token).where(Token.token == credentials.credentials))).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")
    return await db.get(User, row.user_id)


def require_role(role: str):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"需要 {role} 角色")
        return user
    return dependency
