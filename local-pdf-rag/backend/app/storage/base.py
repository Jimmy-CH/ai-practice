from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class DocumentRecord:
    id: str
    filename: str
    page_count: int
    chunk_count: int
    created_at: str


@dataclass
class ChunkRecord:
    id: str
    doc_id: str
    filename: str
    page: int
    index: int
    start: int
    end: int
    text: str
    embedding: list[float] = field(default_factory=list)


@dataclass
class SearchHit:
    chunk: ChunkRecord
    score: float


class VectorStore(Protocol):
    """存储协议；JSON 实现可被 Redis/PostgreSQL 实现替换。"""

    async def add_document(self, document: DocumentRecord, chunks: list[ChunkRecord]) -> None: ...

    async def list_documents(self) -> list[DocumentRecord]: ...

    async def delete_document(self, doc_id: str) -> bool: ...

    async def search(self, query_embedding: list[float], top_k: int) -> list[SearchHit]: ...

    async def counts(self) -> tuple[int, int]: ...
