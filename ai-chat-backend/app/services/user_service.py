
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.auth import get_password_hash, verify_password, create_access_token
from fastapi import HTTPException


async def register_user(session: AsyncSession, username: str, password: str):
    existing = await session.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    hashed = get_password_hash(password)
    new_user = User(username=username, hashed_password=hashed)
    session.add(new_user)
    await session.commit()
    return {"message": "User registered successfully"}


async def login_user(session: AsyncSession, username: str, password: str):
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}
