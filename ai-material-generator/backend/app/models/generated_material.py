import json
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def compute_analysis_hash(analysis: dict) -> str:
    """计算解析结果的稳定哈希，作为缓存键的一部分。

    只取四类要点参与哈希，排除 analysis_id、title 等元数据，
    确保同一套解析内容在不同接口间哈希一致。
    """
    normalized = json.dumps(
        {
            "新增功能": analysis.get("新增功能", []),
            "变更与优化": analysis.get("变更与优化", []),
            "注意事项": analysis.get("注意事项", []),
            "风险提示": analysis.get("风险提示", []),
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return str(hash(normalized))


class GeneratedMaterial(Base):
    __tablename__ = "generated_materials"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "source_title", "audience", "material_type", "analysis_hash",
            name="uix_generated_material",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    source_title: Mapped[str] = mapped_column(String(255), nullable=False)
    audience: Mapped[str] = mapped_column(String(64), nullable=False)
    material_type: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "source_title": self.source_title,
            "audience": self.audience,
            "material_type": self.material_type,
            "analysis_hash": self.analysis_hash,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
