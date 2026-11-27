# local-pdf-rag 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `local-pdf-rag/` 下实现「PDF 上传 → 逐页解析 → 800/100 切分 → Ollama BGE-M3 向量化 → JSON 索引 → 余弦 Top-4 → Qwen2.5:3B 生成」的本地 RAG 基础闭环，并附原生 HTML 单页与假 Ollama 联调工具。

**Architecture:** FastAPI 分层模块：`config` / `schemas` / `storage`（VectorStore 协议 + JSON 实现）/ `ingestion`（pypdf 解析 + 滑窗切分）/ `services`（Ollama HTTP 客户端 + RAG 编排）/ `api`（路由）/ `main`（装配 + StaticFiles）。存储通过协议隔离，后续可替换 Redis/PostgreSQL。

**Tech Stack:** Python 3.11+、FastAPI、pypdf、httpx、pydantic-settings、pytest、pytest-asyncio、Ollama（bge-m3 + qwen2.5:3b）、原生 HTML。

---

## Task 1: 项目骨架与配置

**Files:**
- Create: `local-pdf-rag/backend/app/__init__.py`
- Create: `local-pdf-rag/backend/app/config.py`
- Create: `local-pdf-rag/backend/app/schemas.py`
- Create: `local-pdf-rag/backend/requirements.txt`
- Create: `local-pdf-rag/backend/pytest.ini`
- Create: `local-pdf-rag/backend/.env.example`
- Create: `local-pdf-rag/backend/.gitignore`

- [ ] **Step 1: 创建配置模块**

```python
# app/config.py
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBED_MODEL: str = "bge-m3"
    CHAT_MODEL: str = "qwen2.5:3b"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    TOP_K: int = 4
    MAX_UPLOAD_MB: int = 20
    OLLAMA_TIMEOUT: float = 120.0
    INDEX_PATH: str = str(BASE_DIR / "data" / "index.json")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
```

- [ ] **Step 2: 创建请求/响应模型**

```python
# app/schemas.py
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
```

- [ ] **Step 3: 创建依赖与 pytest 配置**

`requirements.txt`：

```text
fastapi>=0.115,<1.0
uvicorn[standard]>=0.30,<1.0
pypdf>=5.0,<6.0
httpx>=0.27,<1.0
pydantic-settings>=2.5,<3.0
python-dotenv>=1.0,<2.0
python-multipart>=0.0.9,<1.0
pytest>=8.0,<9.0
pytest-asyncio>=0.24,<1.0
```

`pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
testpaths = tests
pythonpath = .
```

`.env.example`：

```ini
OLLAMA_BASE_URL=http://localhost:11434
EMBED_MODEL=bge-m3
CHAT_MODEL=qwen2.5:3b
CHUNK_SIZE=800
CHUNK_OVERLAP=100
TOP_K=4
MAX_UPLOAD_MB=20
OLLAMA_TIMEOUT=120
# INDEX_PATH=./data/index.json
```

`.gitignore`：

```text
venv/
__pycache__/
*.pyc
.env
data/
.pytest_cache/
```

- [ ] **Step 4: 安装依赖并验证配置**

Run:

```powershell
cd local-pdf-rag/backend
python -m venv venv
.\venv\Scripts\python -m pip install -r requirements.txt
.\venv\Scripts\python -c "from app.config import settings; print(settings.CHUNK_SIZE, settings.TOP_K)"
```

Expected: `800 4`

- [ ] **Step 5: Commit**

```bash
git add local-pdf-rag/backend/app/__init__.py local-pdf-rag/backend/app/config.py local-pdf-rag/backend/app/schemas.py local-pdf-rag/backend/requirements.txt local-pdf-rag/backend/pytest.ini local-pdf-rag/backend/.env.example local-pdf-rag/backend/.gitignore
git commit -m "feat(local-pdf-rag): 初始化配置与请求响应模型"
```

---

## Task 2: 滑窗切分与余弦相似度

**Files:**
- Create: `local-pdf-rag/backend/app/ingestion/__init__.py`
- Create: `local-pdf-rag/backend/app/ingestion/chunker.py`
- Test: `local-pdf-rag/backend/tests/test_chunker.py`
- Test: `local-pdf-rag/backend/tests/test_cosine.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_chunker.py
import pytest

from app.ingestion.chunker import TextChunker


def test_chunk_size_and_overlap():
    text = "a" * 2000
    chunks = TextChunker(800, 100).split(text)
    assert [len(c.text) for c in chunks] == [800, 800, 600]
    assert chunks[0].text[-100:] == chunks[1].text[:100]
    assert chunks[1].text[-100:] == chunks[2].text[:100]


def test_short_text_single_chunk():
    chunks = TextChunker(800, 100).split("hello")
    assert len(chunks) == 1
    assert chunks[0].text == "hello"


def test_blank_text_returns_empty():
    assert TextChunker().split("   \n\t ") == []


def test_overlap_must_be_less_than_size():
    with pytest.raises(ValueError):
        TextChunker(100, 100)
```

```python
# tests/test_cosine.py
import pytest

from app.ingestion.chunker import cosine_similarity


def test_cosine_basic_values():
    assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)


def test_zero_vector_returns_zero():
    assert cosine_similarity([0, 0], [1, 0]) == 0.0


def test_dimension_mismatch():
    with pytest.raises(ValueError):
        cosine_similarity([1, 0], [1, 0, 0])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.\venv\Scripts\python -m pytest tests/test_chunker.py tests/test_cosine.py -v`

Expected: FAIL（`ModuleNotFoundError: app.ingestion.chunker`）

- [ ] **Step 3: 实现切分与余弦**

```python
# app/ingestion/chunker.py
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkPiece:
    text: str
    start: int
    end: int


class TextChunker:
    """字符级滑窗切分：默认 800 字符，相邻片段重叠 100 字符。"""

    def __init__(self, size: int = 800, overlap: int = 100) -> None:
        if size <= 0:
            raise ValueError("size 必须大于 0")
        if overlap < 0:
            raise ValueError("overlap 不能为负数")
        if overlap >= size:
            raise ValueError("overlap 必须小于 size")
        self.size = size
        self.overlap = overlap

    def split(self, text: str) -> list[ChunkPiece]:
        if not text or not text.strip():
            return []
        step = self.size - self.overlap
        pieces: list[ChunkPiece] = []
        start = 0
        length = len(text)
        while start < length:
            end = min(start + self.size, length)
            piece = text[start:end].strip()
            if piece:
                pieces.append(ChunkPiece(text=piece, start=start, end=end))
            if end >= length:
                break
            start += step
        return pieces


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """余弦相似度；任一零向量返回 0.0，维度不一致抛 ValueError。"""
    if len(a) != len(b):
        raise ValueError("向量维度不一致")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.\venv\Scripts\python -m pytest tests/test_chunker.py tests/test_cosine.py -v`

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add local-pdf-rag/backend/app/ingestion local-pdf-rag/backend/tests/test_chunker.py local-pdf-rag/backend/tests/test_cosine.py
git commit -m "feat(local-pdf-rag): 实现 800/100 滑窗切分与余弦相似度"
```

---

## Task 3: JSON 向量存储

**Files:**
- Create: `local-pdf-rag/backend/app/storage/__init__.py`
- Create: `local-pdf-rag/backend/app/storage/base.py`
- Create: `local-pdf-rag/backend/app/storage/json_store.py`
- Test: `local-pdf-rag/backend/tests/test_json_store.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_json_store.py
import json

import pytest

from app.storage.base import ChunkRecord, DocumentRecord
from app.storage.json_store import JsonVectorStore


def make_doc(doc_id="d1"):
    return DocumentRecord(
        id=doc_id, filename="a.pdf", page_count=1, chunk_count=2,
        created_at="2026-01-01T00:00:00Z",
    )


def make_chunk(chunk_id, doc_id, text, embedding):
    return ChunkRecord(
        id=chunk_id, doc_id=doc_id, filename="a.pdf", page=1, index=0,
        start=0, end=len(text), text=text, embedding=embedding,
    )


@pytest.mark.asyncio
async def test_add_search_delete_roundtrip(tmp_path):
    path = tmp_path / "index.json"
    store = JsonVectorStore(path)
    await store.add_document(
        make_doc(),
        [make_chunk("c1", "d1", "cat", [1.0, 0.0]), make_chunk("c2", "d1", "dog", [0.0, 1.0])],
    )
    hits = await store.search([1.0, 0.0], top_k=1)
    assert hits[0].chunk.id == "c1"
    assert await store.counts() == (1, 2)

    reloaded = JsonVectorStore(path)
    assert await reloaded.counts() == (1, 2)
    assert await reloaded.delete_document("d1") is True
    assert await reloaded.counts() == (0, 0)
    assert json.loads(path.read_text(encoding="utf-8"))["documents"] == []


@pytest.mark.asyncio
async def test_delete_missing_returns_false(tmp_path):
    store = JsonVectorStore(tmp_path / "index.json")
    assert await store.delete_document("nope") is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.\venv\Scripts\python -m pytest tests/test_json_store.py -v`

Expected: FAIL（`ModuleNotFoundError: app.storage`）

- [ ] **Step 3: 实现协议与 JSON 存储**

```python
# app/storage/base.py
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
    async def add_document(self, document: DocumentRecord, chunks: list[ChunkRecord]) -> None: ...
    async def list_documents(self) -> list[DocumentRecord]: ...
    async def delete_document(self, doc_id: str) -> bool: ...
    async def search(self, query_embedding: list[float], top_k: int) -> list[SearchHit]: ...
    async def counts(self) -> tuple[int, int]: ...
```

```python
# app/storage/json_store.py
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
            "documents": [doc.__dict__ for doc in self._documents],
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
            return sorted(self._documents, key=lambda doc: doc.created_at, reverse=True)

    async def delete_document(self, doc_id: str) -> bool:
        async with self._lock:
            self._ensure_loaded()
            before = len(self._documents)
            self._documents = [doc for doc in self._documents if doc.id != doc_id]
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.\venv\Scripts\python -m pytest tests/test_json_store.py -v`

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add local-pdf-rag/backend/app/storage local-pdf-rag/backend/tests/test_json_store.py
git commit -m "feat(local-pdf-rag): 实现 JSON 向量存储与余弦检索"
```

---

## Task 4: PDF 解析与样本文件

**Files:**
- Create: `local-pdf-rag/backend/app/ingestion/pdf_parser.py`
- Create: `local-pdf-rag/backend/tests/fixtures/sample.pdf`
- Test: `local-pdf-rag/backend/tests/test_parser.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_parser.py
from pathlib import Path

import pytest

from app.ingestion.pdf_parser import PdfParseError, PdfParser

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


def test_parse_sample_pdf():
    pages = PdfParser().parse_bytes(FIXTURE.read_bytes())
    assert len(pages) >= 1
    assert pages[0].page == 1
    assert "Retrieval" in pages[0].text


def test_invalid_pdf_raises():
    with pytest.raises(PdfParseError):
        PdfParser().parse_bytes(b"not a pdf")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.\venv\Scripts\python -m pytest tests/test_parser.py -v`

Expected: FAIL（`ModuleNotFoundError: app.ingestion.pdf_parser`）

- [ ] **Step 3: 实现 PDF 解析**

```python
# app/ingestion/pdf_parser.py
import io
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfParseError(Exception):
    """PDF 无法读取、加密或结构损坏。"""


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


class PdfParser:
    def parse_bytes(self, data: bytes) -> list[PageText]:
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted and not reader.decrypt(""):
                raise PdfParseError("PDF 已加密，无法解析")
            pages: list[PageText] = []
            for index, page in enumerate(reader.pages, start=1):
                pages.append(PageText(page=index, text=(page.extract_text() or "").strip()))
            return pages
        except PdfParseError:
            raise
        except PdfReadError as exc:
            raise PdfParseError(f"PDF 解析失败: {exc}") from exc
        except Exception as exc:
            raise PdfParseError(f"PDF 解析失败: {exc}") from exc
```

- [ ] **Step 4: 生成样本 PDF**

在 venv 中临时安装 `fpdf2`，生成一页含英文文本的 PDF（避免中文字体依赖），随后卸载：

```powershell
.\venv\Scripts\python -m pip install fpdf2
@'
from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=12)
pdf.multi_cell(
    0, 8,
    "Retrieval augmented generation (RAG) combines document retrieval with "
    "language model generation. This sample PDF is used by local-pdf-rag tests. "
    "It is parsed by pypdf, split into overlapping chunks, embedded with BGE-M3, "
    "and retrieved by cosine similarity.",
)
pdf.output("tests/fixtures/sample.pdf")
'@ | Set-Content -Encoding UTF8 gen_fixture.py
.\venv\Scripts\python gen_fixture.py
Remove-Item gen_fixture.py
.\venv\Scripts\python -m pip uninstall -y fpdf2
```

Expected: `tests/fixtures/sample.pdf` 存在且 `PdfParser` 能提取到含 `Retrieval` 的文本。

- [ ] **Step 5: 运行测试确认通过**

Run: `.\venv\Scripts\python -m pytest tests/test_parser.py -v`

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add local-pdf-rag/backend/app/ingestion/pdf_parser.py local-pdf-rag/backend/tests/test_parser.py local-pdf-rag/backend/tests/fixtures/sample.pdf
git commit -m "feat(local-pdf-rag): 使用 pypdf 逐页解析 PDF 并补充样本"
```

---

## Task 5: Ollama HTTP 客户端

**Files:**
- Create: `local-pdf-rag/backend/app/services/__init__.py`
- Create: `local-pdf-rag/backend/app/services/ollama_client.py`
- Test: `local-pdf-rag/backend/tests/test_ollama_client.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ollama_client.py
import httpx
import pytest

from app.services.ollama_client import OllamaClient, OllamaError


def make_client(handler):
    transport = httpx.MockTransport(handler)
    return OllamaClient(
        base_url="http://fake-ollama",
        embed_model="bge-m3",
        chat_model="qwen2.5:3b",
        timeout=5,
        transport=transport,
    )


@pytest.mark.asyncio
async def test_embed_success():
    def handler(request):
        assert request.url.path == "/api/embed"
        return httpx.Response(200, json={"embeddings": [[1.0, 0.0], [0.0, 1.0]]})

    client = make_client(handler)
    assert await client.embed(["cat", "dog"]) == [[1.0, 0.0], [0.0, 1.0]]


@pytest.mark.asyncio
async def test_embed_count_mismatch_raises():
    def handler(request):
        return httpx.Response(200, json={"embeddings": [[1.0, 0.0]]})

    client = make_client(handler)
    with pytest.raises(OllamaError) as exc:
        await client.embed(["cat", "dog"])
    assert exc.value.code == "ollama_bad_response"


@pytest.mark.asyncio
async def test_chat_success():
    def handler(request):
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "答案"}})

    client = make_client(handler)
    assert await client.chat([{"role": "user", "content": "hi"}]) == "答案"


@pytest.mark.asyncio
async def test_unreachable_maps_to_error():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    client = make_client(handler)
    with pytest.raises(OllamaError) as exc:
        await client.embed(["cat"])
    assert exc.value.code == "ollama_unreachable"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.\venv\Scripts\python -m pytest tests/test_ollama_client.py -v`

Expected: FAIL（`ModuleNotFoundError: app.services`）

- [ ] **Step 3: 实现客户端**

```python
# app/services/ollama_client.py
import httpx


class OllamaError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class OllamaClient:
    """通过 httpx 调用 Ollama 的 /api/embed 与 /api/chat。"""

    def __init__(
        self,
        base_url: str,
        embed_model: str,
        chat_model: str,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.embed_model = embed_model
        self.chat_model = chat_model
        self.timeout = timeout
        self._transport = transport

    async def _post(self, path: str, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self._transport
            ) as client:
                response = await client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise OllamaError("ollama_unreachable", f"无法连接 Ollama: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(
                "ollama_bad_response",
                f"Ollama 返回 HTTP {response.status_code}: {response.text[:300]}",
            )
        try:
            return response.json()
        except ValueError as exc:
            raise OllamaError("ollama_bad_response", "Ollama 返回非 JSON") from exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = await self._post("/api/embed", {"model": self.embed_model, "input": texts})
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise OllamaError("ollama_bad_response", "embeddings 数量与输入不一致")
        vectors: list[list[float]] = []
        dimension = None
        for vector in embeddings:
            if not isinstance(vector, list) or not vector:
                raise OllamaError("ollama_bad_response", "embedding 为空或格式错误")
            if dimension is None:
                dimension = len(vector)
            elif len(vector) != dimension:
                raise OllamaError("ollama_bad_response", "embedding 维度不一致")
            vectors.append([float(value) for value in vector])
        return vectors

    async def chat(self, messages: list[dict]) -> str:
        data = await self._post(
            "/api/chat", {"model": self.chat_model, "messages": messages, "stream": False}
        )
        message = data.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise OllamaError("ollama_bad_response", "chat 响应缺少 message.content")
        return message["content"]

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=3.0, transport=self._transport
            ) as client:
                response = await client.get("/api/tags")
            return response.status_code == 200
        except httpx.HTTPError:
            return False
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.\venv\Scripts\python -m pytest tests/test_ollama_client.py -v`

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add local-pdf-rag/backend/app/services/__init__.py local-pdf-rag/backend/app/services/ollama_client.py local-pdf-rag/backend/tests/test_ollama_client.py
git commit -m "feat(local-pdf-rag): 实现 Ollama embed/chat 客户端与错误映射"
```

---

## Task 6: RAG 服务编排

**Files:**
- Create: `local-pdf-rag/backend/app/services/rag_service.py`
- Test: `local-pdf-rag/backend/tests/test_rag_service.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_rag_service.py
import pytest

from app.config import settings
from app.ingestion.pdf_parser import PageText
from app.services.rag_service import EmptyIndexError, RagService
from app.storage.json_store import JsonVectorStore


class FakeOllama:
    def __init__(self):
        self.chat_messages = None

    async def embed(self, texts):
        return [[1.0, 0.0] if "cat" in text else [0.0, 1.0] for text in texts]

    async def chat(self, messages):
        self.chat_messages = messages
        return "答案 [a.pdf p1]"


class FakeParser:
    def parse_bytes(self, data):
        return [PageText(page=1, text="cat " * 500)]


@pytest.mark.asyncio
async def test_ingest_and_ask(tmp_path):
    store = JsonVectorStore(tmp_path / "index.json")
    ollama = FakeOllama()
    service = RagService(store=store, ollama=ollama, parser=FakeParser())

    document = await service.ingest("a.pdf", b"ignored")
    assert document.page_count == 1
    assert document.chunk_count == 3

    response = await service.ask("cat?")
    assert response.answer == "答案 [a.pdf p1]"
    assert len(response.sources) == min(settings.TOP_K, 3)
    assert response.sources[0].index == 1
    assert "a.pdf p1" in ollama.chat_messages[1]["content"]


@pytest.mark.asyncio
async def test_ask_empty_index_raises(tmp_path):
    service = RagService(
        store=JsonVectorStore(tmp_path / "index.json"),
        ollama=FakeOllama(),
        parser=FakeParser(),
    )
    with pytest.raises(EmptyIndexError):
        await service.ask("hi")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.\venv\Scripts\python -m pytest tests/test_rag_service.py -v`

Expected: FAIL（`ModuleNotFoundError: app.services.rag_service`）

- [ ] **Step 3: 实现 RAG 编排**

```python
# app/services/rag_service.py
import uuid
from datetime import datetime, timezone
from functools import lru_cache

from app.config import settings
from app.ingestion.chunker import TextChunker
from app.ingestion.pdf_parser import PdfParser
from app.schemas import AskResponse, DocumentOut, SourceOut
from app.services.ollama_client import OllamaClient
from app.storage.base import ChunkRecord, DocumentRecord, SearchHit, VectorStore
from app.storage.json_store import JsonVectorStore


class EmptyDocumentError(Exception):
    """PDF 中没有任何可切分的文本。"""


class EmptyIndexError(Exception):
    """知识库中没有片段，无法检索。"""


class RagService:
    def __init__(
        self,
        store: VectorStore,
        ollama: OllamaClient,
        parser: PdfParser | None = None,
        chunker: TextChunker | None = None,
    ) -> None:
        self.store = store
        self.ollama = ollama
        self.parser = parser or PdfParser()
        self.chunker = chunker or TextChunker(settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)

    async def ingest(self, filename: str, data: bytes) -> DocumentOut:
        pages = self.parser.parse_bytes(data)
        pieces = []
        for page in pages:
            for piece in self.chunker.split(page.text):
                pieces.append((page.page, piece))
        if not pieces:
            raise EmptyDocumentError("PDF 未提取到可用文本")

        embeddings = await self.ollama.embed([piece.text for _, piece in pieces])
        doc_id = uuid.uuid4().hex
        chunks = [
            ChunkRecord(
                id=uuid.uuid4().hex,
                doc_id=doc_id,
                filename=filename,
                page=page_no,
                index=index,
                start=piece.start,
                end=piece.end,
                text=piece.text,
                embedding=embedding,
            )
            for index, ((page_no, piece), embedding) in enumerate(zip(pieces, embeddings))
        ]
        document = DocumentRecord(
            id=doc_id,
            filename=filename,
            page_count=len(pages),
            chunk_count=len(chunks),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        await self.store.add_document(document, chunks)
        return DocumentOut(**document.__dict__)

    async def ask(self, question: str) -> AskResponse:
        _, chunk_count = await self.store.counts()
        if chunk_count == 0:
            raise EmptyIndexError("知识库为空，请先上传 PDF")

        query_embedding = (await self.ollama.embed([question]))[0]
        hits = await self.store.search(query_embedding, settings.TOP_K)
        answer = await self.ollama.chat(self._build_messages(question, hits))
        sources = [
            SourceOut(
                index=index,
                document_id=hit.chunk.doc_id,
                filename=hit.chunk.filename,
                page=hit.chunk.page,
                score=round(hit.score, 4),
                snippet=hit.chunk.text[:120],
            )
            for index, hit in enumerate(hits, start=1)
        ]
        return AskResponse(answer=answer, sources=sources)

    @staticmethod
    def _build_messages(question: str, hits: list[SearchHit]) -> list[dict]:
        context = "\n\n".join(
            f"[{index}] ({hit.chunk.filename} p{hit.chunk.page})\n{hit.chunk.text}"
            for index, hit in enumerate(hits, start=1)
        )
        system = (
            "你是文档问答助手。只依据下方上下文回答；如果上下文不足以回答，"
            "请明确说“根据提供的文档无法回答”。引用时在句末标注 [文件名 p页码]。"
        )
        user = f"上下文:\n{context}\n\n问题: {question}"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]


@lru_cache(maxsize=1)
def get_service() -> RagService:
    """延迟装配默认服务；测试通过 dependency_overrides 替换。"""
    return RagService(
        store=JsonVectorStore(settings.INDEX_PATH),
        ollama=OllamaClient(
            base_url=settings.OLLAMA_BASE_URL,
            embed_model=settings.EMBED_MODEL,
            chat_model=settings.CHAT_MODEL,
            timeout=settings.OLLAMA_TIMEOUT,
        ),
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.\venv\Scripts\python -m pytest tests/test_rag_service.py -v`

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add local-pdf-rag/backend/app/services/rag_service.py local-pdf-rag/backend/tests/test_rag_service.py
git commit -m "feat(local-pdf-rag): 编排入库、向量检索与问答生成"
```

---

## Task 7: API 路由与应用装配

**Files:**
- Create: `local-pdf-rag/backend/app/api/__init__.py`
- Create: `local-pdf-rag/backend/app/api/routes.py`
- Create: `local-pdf-rag/backend/app/main.py`
- Test: `local-pdf-rag/backend/tests/test_api.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api.py
from pathlib import Path

import httpx
import pytest

from app.ingestion.pdf_parser import PageText
from app.main import app
from app.services.rag_service import RagService, get_service
from app.storage.json_store import JsonVectorStore

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


class FakeOllama:
    async def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]

    async def chat(self, messages):
        return "根据文档，答案如下 [sample.pdf p1]"

    async def ping(self):
        return True


class FakeParser:
    def parse_bytes(self, data):
        return [PageText(page=1, text="Retrieval augmented generation " * 200)]


@pytest.mark.asyncio
async def test_full_flow(tmp_path):
    service = RagService(
        store=JsonVectorStore(tmp_path / "index.json"),
        ollama=FakeOllama(),
        parser=FakeParser(),
    )
    app.dependency_overrides[get_service] = lambda: service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["ollama_reachable"] is True

        upload = await client.post(
            "/api/documents",
            files={"file": ("sample.pdf", FIXTURE.read_bytes(), "application/pdf")},
        )
        assert upload.status_code == 201
        document = upload.json()
        assert document["chunk_count"] > 0

        listed = await client.get("/api/documents")
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        asked = await client.post("/api/ask", json={"question": "what is RAG?"})
        assert asked.status_code == 200
        payload = asked.json()
        assert payload["answer"]
        assert payload["sources"][0]["filename"] == "sample.pdf"
        assert payload["sources"][0]["index"] == 1

        deleted = await client.delete(f"/api/documents/{document['id']}")
        assert deleted.status_code == 204
        assert (await client.get("/api/documents")).json() == []
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ask_empty_index(tmp_path):
    service = RagService(
        store=JsonVectorStore(tmp_path / "index.json"),
        ollama=FakeOllama(),
        parser=FakeParser(),
    )
    app.dependency_overrides[get_service] = lambda: service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/ask", json={"question": "hi"})
        assert response.status_code == 400
        assert response.json()["detail"].startswith("empty_index")
        empty = await client.post("/api/ask", json={"question": "   "})
        assert empty.status_code == 400
        assert empty.json()["detail"].startswith("empty_question")
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_non_pdf_rejected(tmp_path):
    service = RagService(
        store=JsonVectorStore(tmp_path / "index.json"),
        ollama=FakeOllama(),
        parser=FakeParser(),
    )
    app.dependency_overrides[get_service] = lambda: service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/documents", files={"file": ("a.txt", b"hello", "text/plain")}
        )
        assert response.status_code == 400
        assert response.json()["detail"].startswith("unsupported_file")
    app.dependency_overrides.clear()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.\venv\Scripts\python -m pytest tests/test_api.py -v`

Expected: FAIL（`ModuleNotFoundError: app.main`）

- [ ] **Step 3: 实现路由**

```python
# app/api/routes.py
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.config import settings
from app.ingestion.pdf_parser import PdfParseError
from app.schemas import AskRequest, AskResponse, DocumentOut, HealthOut
from app.services.ollama_client import OllamaError
from app.services.rag_service import EmptyDocumentError, EmptyIndexError, RagService, get_service

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthOut)
async def health(service: RagService = Depends(get_service)) -> HealthOut:
    documents, chunks = await service.store.counts()
    return HealthOut(
        status="ok",
        ollama_reachable=await service.ollama.ping(),
        embed_model=settings.EMBED_MODEL,
        chat_model=settings.CHAT_MODEL,
        documents=documents,
        chunks=chunks,
    )


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    service: RagService = Depends(get_service),
) -> DocumentOut:
    filename = file.filename or "unknown.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="unsupported_file: 仅支持 PDF")
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="file_too_large: 文件超过大小限制")
    try:
        return await service.ingest(filename, data)
    except EmptyDocumentError as exc:
        raise HTTPException(status_code=400, detail=f"empty_document: {exc}") from exc
    except PdfParseError as exc:
        raise HTTPException(status_code=400, detail=f"parse_failed: {exc}") from exc
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=f"{exc.code}: {exc.message}") from exc


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(service: RagService = Depends(get_service)) -> list[DocumentOut]:
    documents = await service.store.list_documents()
    return [DocumentOut(**document.__dict__) for document in documents]


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: str, service: RagService = Depends(get_service)) -> None:
    if not await service.store.delete_document(doc_id):
        raise HTTPException(status_code=404, detail="document_not_found")


@router.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest, service: RagService = Depends(get_service)) -> AskResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="empty_question: 问题不能为空")
    try:
        return await service.ask(question)
    except EmptyIndexError as exc:
        raise HTTPException(status_code=400, detail=f"empty_index: {exc}") from exc
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=f"{exc.code}: {exc.message}") from exc
```

- [ ] **Step 4: 实现应用装配**

```python
# app/main.py
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="Local PDF RAG")
app.include_router(router)

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
```

- [ ] **Step 5: 运行测试确认通过**

Run: `.\venv\Scripts\python -m pytest tests/test_api.py -v`

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add local-pdf-rag/backend/app/api local-pdf-rag/backend/app/main.py local-pdf-rag/backend/tests/test_api.py
git commit -m "feat(local-pdf-rag): 提供上传/列表/删除/问答接口并挂载前端"
```

---

## Task 8: 假 Ollama 与前端页面

**Files:**
- Create: `local-pdf-rag/backend/scripts/fake_ollama.py`
- Create: `local-pdf-rag/frontend/index.html`

- [ ] **Step 1: 实现假 Ollama**

```python
# scripts/fake_ollama.py
import hashlib
import math

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="Fake Ollama")


def _vector(text: str, dimension: int = 16) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = [digest[index] / 255.0 for index in range(dimension)]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


@app.post("/api/embed")
async def embed(payload: dict) -> dict:
    texts = payload.get("input", [])
    return {"embeddings": [_vector(str(text)) for text in texts]}


@app.post("/api/chat")
async def chat(payload: dict) -> dict:
    messages = payload.get("messages", [])
    question = next(
        (item.get("content", "") for item in reversed(messages) if item.get("role") == "user"),
        "",
    )
    answer = (
        "（假 Ollama 响应）已根据检索到的上下文生成答案。"
        "真实环境请安装 Ollama 并拉取 bge-m3、qwen2.5:3b。\n\n"
        f"收到的问题：{question[:200]}"
    )
    return {"message": {"role": "assistant", "content": answer}}


@app.get("/api/tags")
async def tags() -> dict:
    return {"models": [{"name": "bge-m3"}, {"name": "qwen2.5:3b"}]}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=11434)
```

- [ ] **Step 2: 实现前端单页**

`frontend/index.html` 包含：上传表单、文档列表（带删除）、提问表单、答案区、来源卡片；`fetch` 使用相对路径；`escapeHtml` 防止 XSS；上传/提问期间显示状态。

- [ ] **Step 3: 启动假 Ollama 与后端，浏览器验证**

```powershell
# 终端 A
cd local-pdf-rag/backend
.\venv\Scripts\python scripts/fake_ollama.py

# 终端 B
cd local-pdf-rag/backend
.\venv\Scripts\python -m uvicorn app.main:app --port 8000
```

打开 `http://localhost:8000`，上传 `tests/fixtures/sample.pdf`，提问，确认答案与来源出现。

- [ ] **Step 4: Commit**

```bash
git add local-pdf-rag/backend/scripts/fake_ollama.py local-pdf-rag/frontend/index.html
git commit -m "feat(local-pdf-rag): 增加假 Ollama 与原生前端页面"
```

---

## Task 9: README、文档索引与整体验证

**Files:**
- Create: `local-pdf-rag/README.md`
- Modify: `.qoder/docs/README.md`
- Modify: 仓库根 `README.md`（子项目清单与架构树）

- [ ] **Step 1: 编写子项目 README**

包含：项目简介、技术栈、目录、快速开始（真 Ollama 与假 Ollama 两条路径）、API 表、测试命令、生产化改造（Redis 会话缓存 + PostgreSQL/pgvector）、设计/实现文档链接。

- [ ] **Step 2: 更新文档索引**

在 `.qoder/docs/README.md` 增加：

```markdown
| local-pdf-rag | [设计说明](local-pdf-rag-设计说明.md) · [实施计划](local-pdf-rag-实施计划.md) · [实现说明](local-pdf-rag-实现说明.md) |
```

在仓库根 `README.md` 的总览表、架构树、学习路径中加入第 10 个子项目。

- [ ] **Step 3: 全量测试**

Run:

```powershell
cd local-pdf-rag/backend
.\venv\Scripts\python -m pytest -v
```

Expected: 全部通过（切分/余弦/存储/解析/客户端/服务/接口）。

- [ ] **Step 4: 真实联调（假 Ollama）**

按 Task 8 Step 3 启动两个服务，验证：

- `GET /api/health` 返回 `ollama_reachable: true`
- 上传后 `GET /api/documents` 有记录
- 提问返回 `answer` 与 4 条以内 `sources`
- 删除后列表为空

- [ ] **Step 5: Commit**

```bash
git add local-pdf-rag/README.md .qoder/docs/README.md README.md
git commit -m "docs(local-pdf-rag): 补充 README 与文档索引"
```

---

## Self-Review

**Spec coverage:**
- PDF 解析 → Task 4
- 800/100 切分 → Task 2
- BGE-M3 向量化 → Task 5（Ollama `/api/embed`）
- JSON 存储 → Task 3
- 余弦 Top-4 → Task 2 + Task 3 + Task 6
- Qwen2.5 生成 → Task 5 + Task 6
- 原生前端 → Task 8
- 生产改造留接口 → Task 3（`VectorStore` 协议）+ README 说明
- 测试与假 Ollama → Task 5/6/7/8

**Placeholder scan:** 无 TBD/TODO；所有代码步骤均给出可执行代码。

**Type consistency:** `ChunkPiece`、`ChunkRecord`、`SearchHit`、`DocumentRecord` 在 Task 2/3/6 中命名与字段一致；`get_service` 在 Task 6 定义、Task 7 通过 `Depends` 使用、测试用 `dependency_overrides` 替换。
