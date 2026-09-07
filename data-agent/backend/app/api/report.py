"""定时报告 API。"""
import json
import asyncio
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.users.models import User
from app.models.report import ScheduledReport
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Reports"])


class CreateReportRequest(BaseModel):
    name: str
    question: str
    schedule_type: str = "daily"  # daily, weekly
    schedule_time: str = "09:00"


class ReportOut(BaseModel):
    id: int
    name: str
    question: str
    schedule_type: str
    schedule_time: str
    last_result: str
    last_run_at: Optional[datetime]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/", response_model=ReportOut)
async def create_report(
    req: CreateReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建定时报告。"""
    report = ScheduledReport(
        user_id=current_user.id,
        name=req.name,
        question=req.question,
        schedule_type=req.schedule_type,
        schedule_time=req.schedule_time,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


@router.get("/", response_model=List[ReportOut])
async def list_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的定时报告列表。"""
    query = (
        select(ScheduledReport)
        .where(ScheduledReport.user_id == current_user.id)
        .order_by(ScheduledReport.created_at.desc())
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.put("/{report_id}/toggle", response_model=ReportOut)
async def toggle_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """启用/禁用定时报告。"""
    query = select(ScheduledReport).where(
        ScheduledReport.id == report_id,
        ScheduledReport.user_id == current_user.id,
    )
    result = await db.execute(query)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(404, "报告不存在")
    report.is_active = not report.is_active
    await db.commit()
    await db.refresh(report)
    return report


@router.delete("/{report_id}")
async def delete_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除定时报告。"""
    query = select(ScheduledReport).where(
        ScheduledReport.id == report_id,
        ScheduledReport.user_id == current_user.id,
    )
    result = await db.execute(query)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(404, "报告不存在")
    await db.delete(report)
    await db.commit()
    return {"detail": "已删除"}


@router.post("/{report_id}/run")
async def run_report_now(
    report_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """立即执行一次报告。"""
    query = select(ScheduledReport).where(
        ScheduledReport.id == report_id,
        ScheduledReport.user_id == current_user.id,
    )
    result = await db.execute(query)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(404, "报告不存在")

    # 在后台执行 Agent 查询
    from app.agent.langchain_agent import run_agent
    agent_result = await run_agent(report.question)
    report.last_result = agent_result.answer
    report.last_run_at = datetime.utcnow()
    await db.commit()

    return {"detail": "执行完成", "result": agent_result.answer}
