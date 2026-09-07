"""收藏查询 API。"""
import logging
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.users.models import User
from app.models.query import SavedQuery
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queries", tags=["SavedQueries"])


class SaveQueryRequest(BaseModel):
    name: str
    question: str
    is_favorite: bool = False


class SavedQueryOut(BaseModel):
    id: int
    name: str
    question: str
    is_favorite: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SavedQueryListOut(BaseModel):
    queries: List[SavedQueryOut]


@router.post("/", response_model=SavedQueryOut)
async def save_query(
    req: SaveQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存一个查询。"""
    sq = SavedQuery(
        user_id=current_user.id,
        name=req.name,
        question=req.question,
        is_favorite=req.is_favorite,
    )
    db.add(sq)
    await db.commit()
    await db.refresh(sq)
    return sq


@router.get("/", response_model=SavedQueryListOut)
async def list_queries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的收藏查询列表。"""
    query = (
        select(SavedQuery)
        .where(SavedQuery.user_id == current_user.id)
        .order_by(SavedQuery.created_at.desc())
    )
    result = await db.execute(query)
    queries = result.scalars().all()
    return SavedQueryListOut(queries=queries)


@router.delete("/{query_id}")
async def delete_query(
    query_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除一个收藏的查询。"""
    query = select(SavedQuery).where(
        SavedQuery.id == query_id, SavedQuery.user_id == current_user.id
    )
    result = await db.execute(query)
    sq = result.scalar_one_or_none()
    if not sq:
        raise HTTPException(404, "查询不存在")
    await db.delete(sq)
    await db.commit()
    return {"detail": "已删除"}


@router.put("/{query_id}/favorite")
async def toggle_favorite(
    query_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """切换收藏状态。"""
    query = select(SavedQuery).where(
        SavedQuery.id == query_id, SavedQuery.user_id == current_user.id
    )
    result = await db.execute(query)
    sq = result.scalar_one_or_none()
    if not sq:
        raise HTTPException(404, "查询不存在")
    sq.is_favorite = not sq.is_favorite
    await db.commit()
    return {"is_favorite": sq.is_favorite}
