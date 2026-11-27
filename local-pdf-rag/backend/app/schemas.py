from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(max_length=2000)


class DocumentOut(BaseModel):
    id: str
    filename: str
    page_count: int
    chunk_count: int
    created_at: str


class SourceOut(BaseModel):
    index: int
    document_id: str
    filename: str
    page: int
    score: float
    snippet: str


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceOut]


class HealthOut(BaseModel):
    status: str
    ollama_reachable: bool
    embed_model: str
    chat_model: str
    documents: int
    chunks: int
