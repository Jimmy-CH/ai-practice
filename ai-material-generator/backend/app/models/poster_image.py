import hashlib
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def compute_script_hash(script_content: str) -> str:
    """脚本内容的稳定哈希（提炼缓存键）。md5 跨进程稳定，不受 PYTHONHASHSEED 影响。"""
    return hashlib.md5(script_content.encode("utf-8")).hexdigest()


class PosterPrompt(Base):
    """画面描述提炼结果缓存：同 owner 同脚本只保留一份，覆盖式更新。"""

    __tablename__ = "poster_prompts"
    __table_args__ = (UniqueConstraint("owner_id", "script_hash", name="uix_poster_prompt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    script_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "script_hash": self.script_hash,
            "prompt": self.prompt,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PosterImage(Base):
    """生成的海报图片资产：不进审核流，归属生成者本人。"""

    __tablename__ = "poster_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    source_title: Mapped[str] = mapped_column(String(255), nullable=False)
    audience: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        # file_path 为内部路径不外露；前端经鉴权的 image_url 取文件
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "source_title": self.source_title,
            "audience": self.audience,
            "prompt": self.prompt,
            "file_size": self.file_size,
            "image_url": f"/api/posters/images/{self.id}/file",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
