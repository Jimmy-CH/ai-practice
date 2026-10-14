from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    repo_id: int
    base_ref: str = Field(min_length=1)
    head_ref: str = Field(min_length=1)
    version_label: str | None = None
    tone: str = "business"
    mask: bool = False
