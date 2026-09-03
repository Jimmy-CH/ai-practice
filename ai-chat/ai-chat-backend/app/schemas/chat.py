
from typing import List, Dict, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: str = "deepseek-chat"
    stream: bool = True
    resume_from: Optional[int] = -1
