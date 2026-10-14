from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class MaterialCreate(BaseModel):
    title: str
    content: str
    material_type: str
    audience: str
    source_title: str = ""
    analysis: str = "{}"


class MaterialUpdate(BaseModel):
    title: str
    content: str
    material_type: str
    audience: str


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    title: str
    content: str
    material_type: str
    audience: str
    status: str
    source_title: str
    analysis: str
    review_comment: str | None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    reviewer_username: str | None = None
    created_at: datetime
    updated_at: datetime


class ReviewAction(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    comment: str = ""
