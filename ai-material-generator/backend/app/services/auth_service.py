from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.security import verify_password, get_password_hash


async def authenticate_user(session: AsyncSession, username: str, password: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def seed_users(session: AsyncSession) -> None:
    result = await session.execute(select(User).limit(1))
    if result.scalar_one_or_none() is not None:
        return
    users = [
        User(username="editor", password_hash=get_password_hash("editor123"), role="editor"),
        User(username="reviewer", password_hash=get_password_hash("reviewer123"), role="reviewer"),
    ]
    session.add_all(users)
    await session.commit()
