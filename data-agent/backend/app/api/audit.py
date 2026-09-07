"""审计日志与用量统计 API。"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, sync_engine
from app.auth.dependencies import require_role
from app.users.models import User
from app.models.audit import AuditLog
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["Audit"])


def log_audit(user_id: int, username: str, action: str, detail: str = "", ip: str = ""):
    """同步写入审计日志（供各 API 调用）。"""
    from app.database import sync_engine
    with sync_engine.connect() as conn:
        conn.execute(
            sql_text("""
                INSERT INTO audit_logs (user_id, username, action, detail, ip_address, created_at)
                VALUES (:uid, :uname, :action, :detail, :ip, :now)
            """),
            {"uid": user_id, "uname": username, "action": action, "detail": detail, "ip": ip, "now": datetime.utcnow()}
        )
        conn.commit()


class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int]
    username: str
    action: str
    detail: str
    ip_address: str
    created_at: datetime

    class Config:
        from_attributes = True


class UsageStats(BaseModel):
    total_queries: int
    today_queries: int
    week_queries: int
    top_users: List[dict]
    top_questions: List[dict]
    daily_trend: List[dict]


@router.get("/logs", response_model=List[AuditLogOut])
async def get_logs(
    limit: int = 100,
    action: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin")),
):
    """获取审计日志（仅管理员）。"""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        query = query.where(AuditLog.action == action)
    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats", response_model=UsageStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin")),
):
    """获取用量统计（仅管理员）。"""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    # 总查询数
    total_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "query")
    )
    total_queries = total_result.scalar() or 0

    # 今日查询数
    today_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "query", AuditLog.created_at >= today_start
        )
    )
    today_queries = today_result.scalar() or 0

    # 本周查询数
    week_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "query", AuditLog.created_at >= week_start
        )
    )
    week_queries = week_result.scalar() or 0

    # Top 用户
    top_users_result = await db.execute(
        select(AuditLog.username, func.count().label("cnt"))
        .where(AuditLog.action == "query")
        .group_by(AuditLog.username)
        .order_by(func.count().desc())
        .limit(10)
    )
    top_users = [{"username": r[0], "count": r[1]} for r in top_users_result.all()]

    # Top 问题
    top_q_result = await db.execute(
        select(AuditLog.detail, AuditLog.username)
        .where(AuditLog.action == "query", AuditLog.detail != "")
        .order_by(AuditLog.created_at.desc())
        .limit(20)
    )
    question_counts = {}
    for r in top_q_result.all():
        q = r[0][:100]
        if q in question_counts:
            question_counts[q]["count"] += 1
        else:
            question_counts[q] = {"question": q, "user": r[1], "count": 1}
    top_questions = sorted(question_counts.values(), key=lambda x: x["count"], reverse=True)[:10]

    # 每日趋势（近 30 天）
    daily_result = await db.execute(
        select(func.date(AuditLog.created_at).label("d"), func.count().label("cnt"))
        .where(AuditLog.action == "query", AuditLog.created_at >= now - timedelta(days=30))
        .group_by(func.date(AuditLog.created_at))
        .order_by(func.date(AuditLog.created_at))
    )
    daily_trend = [{"date": str(r[0]), "count": r[1]} for r in daily_result.all()]

    return UsageStats(
        total_queries=total_queries,
        today_queries=today_queries,
        week_queries=week_queries,
        top_users=top_users,
        top_questions=top_questions,
        daily_trend=daily_trend,
    )
