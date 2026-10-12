from datetime import datetime

from pydantic import BaseModel, Field


class TextSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class GitSourceCreate(BaseModel):
    repository: str = Field(min_length=1, max_length=255)
    release: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)


class SourceRead(TextSourceCreate):
    id: str
    project_id: str
    source_type: str
    created_at: datetime

    model_config = {"from_attributes": True}
