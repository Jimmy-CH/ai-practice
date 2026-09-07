"""分享查询模型。"""
import secrets
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from app.database import Base


def generate_share_token():
    return secrets.token_urlsafe(16)


class SharedQuery(Base):
    __tablename__ = "shared_queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(64), unique=True, default=generate_share_token)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    steps_json = Column(Text, default="[]")  # JSON string of steps
    chart_data_json = Column(Text, default="")  # JSON string of chart data
    expires_at = Column(DateTime, nullable=True)  # None = no expiry
    created_at = Column(DateTime, default=datetime.utcnow)
