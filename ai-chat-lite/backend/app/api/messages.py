from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.sse import SSE_HEADERS, format_event
from app.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services.stream_manager import manager

router = APIRouter(prefix="/messages", tags=["messages"])


async def _owned_message(db: AsyncSession, user: User, message_id: int) -> tuple[Message, Conversation]:
    msg = await db.get(Message, message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="消息不存在")
    conv = await db.get(Conversation, msg.conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="消息不存在")
    return msg, conv


@router.get("/{message_id}/stream")
async def stream_message(
    message_id: int,
    resume_from: int = -1,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg, _ = await _owned_message(db, user, message_id)

    if msg.status == "streaming" and manager.get(message_id) is None:
        # 进程重启或任务丢失：收敛为失败，避免前端永远等待
        msg.status = "failed"
        msg.error = msg.error or "生成任务不存在"
        await db.commit()

    session = manager.get(message_id)
    if session is None:
        async def terminal_only():
            if msg.status == "failed":
                yield format_event(
                    "error",
                    {
                        "message_id": msg.id,
                        "status": "failed",
                        "code": "internal",
                        "message": msg.error or "生成失败",
                    },
                )
            else:
                yield format_event(
                    "done",
                    {"message_id": msg.id, "status": msg.status, "content": msg.content},
                )

        return StreamingResponse(terminal_only(), media_type="text/event-stream", headers=SSE_HEADERS)

    if resume_from < -1 or resume_from > session.last_seq:
        raise HTTPException(status_code=400, detail="resume_from 越界")
    return StreamingResponse(
        manager.subscribe(session, resume_from), media_type="text/event-stream", headers=SSE_HEADERS
    )


@router.post("/{message_id}/stop")
async def stop_message(
    message_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg, _ = await _owned_message(db, user, message_id)
    session = await manager.stop(message_id)
    status = session.status if session is not None else msg.status
    return {"message_id": message_id, "status": status}
