from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    steps: list[dict]
    created_at: datetime

    @classmethod
    def from_orm_model(cls, msg) -> "MessageOut":
        import json
        return cls(
            id=msg.id, role=msg.role, content=msg.content,
            steps=json.loads(msg.steps) if isinstance(msg.steps, str) else msg.steps,
            created_at=msg.created_at,
        )


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationCreate(BaseModel):
    title: Optional[str] = "新对话"


class SaveMessageRequest(BaseModel):
    role: str
    content: str
    steps: list[dict] | None = None
