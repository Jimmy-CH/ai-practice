from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User


async def create(db: AsyncSession, user: User) -> Conversation:
    conv = Conversation(user_id=user.id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def list_by_user(db: AsyncSession, user: User) -> list[Conversation]:
    result = await db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(result)


async def get_owned(db: AsyncSession, user: User, conversation_id: int) -> Conversation:
    conv = await db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


async def delete(db: AsyncSession, user: User, conversation_id: int) -> None:
    conv = await get_owned(db, user, conversation_id)
    await db.delete(conv)
    await db.commit()


async def list_messages(db: AsyncSession, user: User, conversation_id: int) -> list[Message]:
    await get_owned(db, user, conversation_id)
    result = await db.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
    )
    return list(result)
