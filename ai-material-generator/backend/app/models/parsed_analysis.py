import json
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ParsedAnalysis(Base):
    __tablename__ = "parsed_analyses"
    __table_args__ = (UniqueConstraint("owner_id", "source_title", name="uix_owner_title"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    source_title: Mapped[str] = mapped_column(String(255), nullable=False)

    new_features: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    changes: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    notices: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    risks: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "source_title": self.source_title,
            "新增功能": json.loads(self.new_features),
            "变更与优化": json.loads(self.changes),
            "注意事项": json.loads(self.notices),
            "风险提示": json.loads(self.risks),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
