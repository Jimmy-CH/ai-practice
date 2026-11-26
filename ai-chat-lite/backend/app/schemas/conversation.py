from datetime import datetime

from pydantic import BaseModel


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    running: bool = False

    model_config = {"from_attributes": True}


class ConversationList(BaseModel):
    items: list[ConversationOut]
