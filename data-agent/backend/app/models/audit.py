"""审计日志模型。"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(100), default="")
    action = Column(String(50), nullable=False)  # query, upload, delete, login, etc.
    detail = Column(Text, default="")  # JSON or text detail
    ip_address = Column(String(50), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
