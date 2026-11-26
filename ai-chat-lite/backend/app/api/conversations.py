from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.conversation import ConversationList, ConversationOut
from app.schemas.message import MessageList, SendMessageRequest, SendMessageResponse
from app.services import chat_service, conversation_service
from app.services.stream_manager import manager

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await conversation_service.create(db, user)


@router.get("", response_model=ConversationList)
async def list_conversations(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    items = await conversation_service.list_by_user(db, user)
    return ConversationList(
        items=[
            ConversationOut.model_validate(c).model_copy(update={"running": manager.has_running(c.id)})
            for c in items
        ]
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await manager.cancel_conversation(conversation_id)
    await conversation_service.delete(db, user, conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{conversation_id}/messages", response_model=MessageList)
async def list_messages(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await conversation_service.list_messages(db, user, conversation_id)
    return MessageList(items=items)


@router.post(
    "/{conversation_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    conversation_id: int,
    payload: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_msg, assistant_msg = await chat_service.send_message(
        db, user, conversation_id, payload.content
    )
    return SendMessageResponse(user_message=user_msg, assistant_message=assistant_msg)
