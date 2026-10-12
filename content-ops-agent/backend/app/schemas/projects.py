from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    theme: str = Field(min_length=1, max_length=2000)
    audience: str = Field(min_length=1, max_length=200)
    tone: str = Field(min_length=1, max_length=80)


class ProjectRead(ProjectCreate):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}
