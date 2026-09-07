"""定时报告模型。"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from app.database import Base


class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(200), nullable=False)
    question = Column(Text, nullable=False)  # 要执行的查询问题
    schedule_type = Column(String(20), default="daily")  # daily, weekly
    schedule_time = Column(String(10), default="09:00")  # HH:MM
    last_result = Column(Text, default="")  # 最近一次执行结果
    last_run_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
