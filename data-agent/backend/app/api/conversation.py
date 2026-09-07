from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.users.models import User
from app.schemas.conversation import (
    ConversationOut, ConversationCreate, MessageOut, SaveMessageRequest,
)
from app.services import conversation as conv_service

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("/", response_model=list[ConversationOut])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的会话列表。"""
    return await conv_service.get_user_conversations(db, current_user.id)


@router.post("/", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conv(
    req: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建新会话。"""
    return await conv_service.create_conversation(db, current_user.id, req.title)


@router.get("/{conv_id}", response_model=list[MessageOut])
async def get_conv_messages(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会话的消息记录。"""
    conv = await conv_service.get_conversation(db, conv_id, current_user.id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    messages = await conv_service.get_messages(db, conv_id)
    return [MessageOut.from_orm_model(m) for m in messages]


@router.post("/{conv_id}/messages")
async def save_msg(
    conv_id: int,
    req: SaveMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """保存消息到会话。"""
    conv = await conv_service.get_conversation(db, conv_id, current_user.id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    msg = await conv_service.save_message(db, conv_id, req.role, req.content, req.steps)
    return {"id": msg.id}


@router.delete("/{conv_id}")
async def delete_conv(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除会话。"""
    deleted = await conv_service.delete_conversation(db, conv_id, current_user.id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    return {"message": "会话已删除"}
