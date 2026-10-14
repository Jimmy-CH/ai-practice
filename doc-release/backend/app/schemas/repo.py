from pydantic import BaseModel, Field


class RepoCreate(BaseModel):
    path: str = Field(min_length=1)
    name: str | None = None
