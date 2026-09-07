import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.conversation import Conversation, Message


async def get_user_conversations(db: AsyncSession, user_id: int) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_conversation(db: AsyncSession, conv_id: int, user_id: int) -> Conversation | None:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_conversation(db: AsyncSession, user_id: int, title: str = "新对话") -> Conversation:
    conv = Conversation(user_id=user_id, title=title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def delete_conversation(db: AsyncSession, conv_id: int, user_id: int) -> bool:
    conv = await get_conversation(db, conv_id, user_id)
    if conv is None:
        return False
    await db.delete(conv)
    await db.commit()
    return True


async def save_message(
    db: AsyncSession, conv_id: int, role: str, content: str,
    steps: list[dict] | None = None, title: str | None = None,
) -> Message:
    msg = Message(
        conversation_id=conv_id, role=role, content=content,
        steps=json.dumps(steps or [], ensure_ascii=False),
    )
    db.add(msg)
    if title:
        conv = await db.get(Conversation, conv_id)
        if conv:
            conv.title = title[:20]
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_messages(db: AsyncSession, conv_id: int) -> list[Message]:
    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    )
    return list(result.scalars().all())
