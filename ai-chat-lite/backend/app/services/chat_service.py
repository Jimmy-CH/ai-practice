from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory, utcnow
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services import conversation_service
from app.services.stream_manager import manager


async def build_prompt(db: AsyncSession, conversation_id: int) -> list[dict]:
    rows = await db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role.in_(["user", "assistant"]),
            Message.status.in_(["done", "stopped"]),
        )
        .order_by(Message.id.desc())
        .limit(settings.MAX_CONTEXT_MESSAGES)
    )
    history = list(reversed(list(rows)))
    return [{"role": "system", "content": settings.SYSTEM_PROMPT}] + [
        {"role": m.role, "content": m.content} for m in history if m.content
    ]


async def send_message(
    db: AsyncSession, user: User, conversation_id: int, content: str
) -> tuple[Message, Message]:
    conv = await conversation_service.get_owned(db, user, conversation_id)
    if manager.has_running(conv.id):
        raise HTTPException(status_code=409, detail="该会话正在生成回复，请稍候")

    user_msg = Message(conversation_id=conv.id, role="user", content=content, status="done")
    db.add(user_msg)
    if conv.title == "新对话":
        conv.title = " ".join(content.splitlines()).strip()[:20] or "新对话"
    conv.updated_at = utcnow()
    await db.flush()

    assistant_msg = Message(conversation_id=conv.id, role="assistant", content="", status="streaming")
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)

    prompt = await build_prompt(db, conv.id)
    manager.start(assistant_msg.id, conv.id, user.id, prompt)
    return user_msg, assistant_msg


async def recover_stale_streaming() -> None:
    async with async_session_factory() as db:
        await db.execute(
            update(Message)
            .where(Message.role == "assistant", Message.status == "streaming")
            .values(status="failed", error="服务重启中断", updated_at=utcnow())
        )
        await db.commit()
