import asyncio
import json
import os
import tempfile
from pathlib import Path

from app.ingestion.chunker import cosine_similarity
from app.storage.base import ChunkRecord, DocumentRecord, SearchHit


class JsonVectorStore:
    """单文件 JSON 向量库；写入使用临时文件 + os.replace 保证原子性。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()
        self._documents: list[DocumentRecord] = []
        self._chunks: list[ChunkRecord] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._documents = [DocumentRecord(**item) for item in raw.get("documents", [])]
            self._chunks = [ChunkRecord(**item) for item in raw.get("chunks", [])]
        self._loaded = True

    def _write_atomic(self) -> None:
        payload = {
            "version": 1,
            "documents": [document.__dict__ for document in self._documents],
            "chunks": [chunk.__dict__ for chunk in self._chunks],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self.path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def add_document(self, document: DocumentRecord, chunks: list[ChunkRecord]) -> None:
        async with self._lock:
            self._ensure_loaded()
            self._documents.append(document)
            self._chunks.extend(chunks)
            self._write_atomic()

    async def list_documents(self) -> list[DocumentRecord]:
        async with self._lock:
            self._ensure_loaded()
            return sorted(self._documents, key=lambda document: document.created_at, reverse=True)

    async def delete_document(self, doc_id: str) -> bool:
        async with self._lock:
            self._ensure_loaded()
            before = len(self._documents)
            self._documents = [document for document in self._documents if document.id != doc_id]
            self._chunks = [chunk for chunk in self._chunks if chunk.doc_id != doc_id]
            if len(self._documents) == before:
                return False
            self._write_atomic()
            return True

    async def search(self, query_embedding: list[float], top_k: int) -> list[SearchHit]:
        async with self._lock:
            self._ensure_loaded()
            hits = [
                SearchHit(chunk=chunk, score=cosine_similarity(query_embedding, chunk.embedding))
                for chunk in self._chunks
            ]
            hits.sort(key=lambda hit: hit.score, reverse=True)
            return hits[:top_k]

    async def counts(self) -> tuple[int, int]:
        async with self._lock:
            self._ensure_loaded()
            return len(self._documents), len(self._chunks)
