from pydantic import BaseModel, Field, field_validator


class RunCreate(BaseModel):
    repo_id: int
    base_ref: str = Field(min_length=1)
    head_ref: str = Field(min_length=1)
    version_label: str | None = None
    tone: str = "business"
    mask: bool = False

    @field_validator("version_label")
    @classmethod
    def _check_version_label(cls, v: str | None) -> str | None:
        """版本号用作归档目录名：拒绝路径分隔符与相对引用，防目录穿越。"""
        if v is None:
            return v
        v = v.strip()
        if not v:
            return v
        if any(ch in v for ch in ("/", "\\", ":")) or ".." in v:
            raise ValueError("版本号不能包含路径分隔符或相对引用")
        return v
