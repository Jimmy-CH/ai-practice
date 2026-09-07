"""查询分享 API。"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.users.models import User
from app.models.share import SharedQuery
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/share", tags=["Share"])


class ShareQueryRequest(BaseModel):
    question: str
    answer: str
    steps: list = []
    chart_data: Optional[dict] = None
    expires_hours: Optional[int] = None  # None = 不过期


class ShareQueryOut(BaseModel):
    token: str
    url: str
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class SharedQueryDetail(BaseModel):
    question: str
    answer: str
    steps: list
    chart_data: Optional[dict]
    created_at: datetime
    expires_at: Optional[datetime]


@router.post("/", response_model=ShareQueryOut)
async def create_share(
    req: ShareQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建一个分享链接。"""
    expires_at = None
    if req.expires_hours:
        expires_at = datetime.utcnow() + timedelta(hours=req.expires_hours)

    sq = SharedQuery(
        user_id=current_user.id,
        question=req.question,
        answer=req.answer,
        steps_json=json.dumps(req.steps, ensure_ascii=False),
        chart_data_json=json.dumps(req.chart_data, ensure_ascii=False) if req.chart_data else "",
        expires_at=expires_at,
    )
    db.add(sq)
    await db.commit()
    await db.refresh(sq)

    url = f"/shared/{sq.token}"
    return ShareQueryOut(token=sq.token, url=url, expires_at=sq.expires_at)


@router.get("/{token}", response_model=SharedQueryDetail)
async def get_shared(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """获取分享内容（公开接口，无需登录）。"""
    query = select(SharedQuery).where(SharedQuery.token == token)
    result = await db.execute(query)
    sq = result.scalar_one_or_none()
    if not sq:
        raise HTTPException(404, "分享不存在")

    if sq.expires_at and sq.expires_at < datetime.utcnow():
        raise HTTPException(410, "分享已过期")

    return SharedQueryDetail(
        question=sq.question,
        answer=sq.answer,
        steps=json.loads(sq.steps_json) if sq.steps_json else [],
        chart_data=json.loads(sq.chart_data_json) if sq.chart_data_json else None,
        created_at=sq.created_at,
        expires_at=sq.expires_at,
    )


@router.get("/", response_model=List[dict])
async def list_shares(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户创建的分享列表。"""
    query = (
        select(SharedQuery)
        .where(SharedQuery.user_id == current_user.id)
        .order_by(SharedQuery.created_at.desc())
    )
    result = await db.execute(query)
    shares = result.scalars().all()
    return [
        {
            "token": s.token,
            "question": s.question,
            "created_at": s.created_at.isoformat(),
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        }
        for s in shares
    ]
