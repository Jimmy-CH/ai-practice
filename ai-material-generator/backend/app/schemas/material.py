from datetime import datetime
from pydantic import BaseModel, Field


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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReviewAction(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    comment: str = ""
