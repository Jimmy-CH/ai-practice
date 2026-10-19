import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.clock import iso_utc, utcnow
from app.database import Base

STEP_NAMES = [
    "定位仓库与变更范围",
    "收集变更（diff 与统计）",
    "AST 解析变更结构",
    "LLM 业务化语义改写",
    "产物生成并归档",
]


def blank_steps() -> list[dict]:
    return [{"index": i, "name": name, "status": "pending"} for i, name in enumerate(STEP_NAMES)]


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey("repos.id"))
    base_ref: Mapped[str] = mapped_column(String(200))
    head_ref: Mapped[str] = mapped_column(String(200))
    version_label: Mapped[str] = mapped_column(String(200))
    tone: Mapped[str] = mapped_column(String(20), default="business")
    mask: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    current_step: Mapped[int] = mapped_column(Integer, default=-1)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    logs: Mapped[list] = mapped_column(JSON, default=list)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "repo_id": self.repo_id,
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "version_label": self.version_label,
            "tone": self.tone,
            "mask": self.mask,
            "status": self.status,
            "current_step": self.current_step,
            "steps": self.steps or [],
            "logs": self.logs or [],
            "stats": self.stats or {},
            "result": self.result,
            "error": self.error,
            "created_at": iso_utc(self.created_at),
            "finished_at": iso_utc(self.finished_at),
        }
