# multi-agent-research 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个可运行的多 Agent 调研报告系统：本地资料库 → Planner 拆解 → 人工确认大纲 → 检索/分析/写作/核查 → 带引用 Markdown 报告。

**Architecture:** 自研状态机编排五个固定角色；SQLite 持久化 run / step / evidence；后台 asyncio 任务执行，SSE 推送轨迹；检索为中文 2-gram BM25，LLM 走 DeepSeek（测试注入 FakeLLM）。

**Tech Stack:** Python 3.11、FastAPI 0.141.1、SQLAlchemy 2.0.52 + aiosqlite 0.20.0、pydantic-settings 2.15.0、httpx 0.28.1、pypdf 5.x、pytest 9.1.1 + pytest-asyncio 1.3.0；前端 Vue 3.5 + TypeScript + Vite 5 + Element Plus 2.14 + Pinia 2.2 + marked + dompurify。

**文档位置：** 按本仓库约定保存于 `.qoder/docs/multi-agent-research-实施计划.md`（覆盖 skill 默认的 `docs/superpowers/plans/`）。

**设计依据：** `.qoder/docs/multi-agent-research-设计说明.md`（下称「设计说明」）。

---

## 文件地图

| 文件 | 职责 |
| --- | --- |
| `backend/app/config.py` | 环境变量与默认值 |
| `backend/app/database.py` | async engine / session 工厂 / 懒加载 / PRAGMA |
| `backend/app/models/content.py` | 6 张表 ORM |
| `backend/app/schemas.py` | 请求/响应模型 |
| `backend/app/retrieval/chunker.py` | 800/100 滑窗切分 |
| `backend/app/retrieval/tokenizer.py` | 中文 2-gram 分词 |
| `backend/app/retrieval/base.py` | `EvidenceHit` 与 `Retriever` 协议 |
| `backend/app/retrieval/bm25.py` | BM25 索引与 `SqlBM25Retriever` |
| `backend/app/retrieval/ingest.py` | PDF/TXT/MD 解析与入库 |
| `backend/app/services/llm.py` | `LLMClient` 协议、`DeepSeekClient`、`FakeLLM` |
| `backend/app/agents/base.py` | JSON 解析、围栏剥离、重试 |
| `backend/app/agents/prompts.py` | 四个 LLM 角色的 prompt |
| `backend/app/agents/planner.py` | Planner |
| `backend/app/agents/researcher.py` | Researcher |
| `backend/app/agents/analyst.py` | Analyst |
| `backend/app/agents/writer.py` | Writer |
| `backend/app/agents/reviewer.py` | Reviewer |
| `backend/app/orchestrator/state.py` | 状态枚举与转移守卫 |
| `backend/app/orchestrator/events.py` | 进程内事件总线 |
| `backend/app/orchestrator/runner.py` | 阶段执行器与后台任务注册表 |
| `backend/app/api/errors.py` | 统一 `{"detail": {code, message}}` 错误构造 |
| `backend/app/api/documents.py` | 资料库接口 |
| `backend/app/api/runs.py` | 运行 CRUD、大纲、恢复、取消、报告下载 |
| `backend/app/api/events.py` | SSE 快照与增量推送 |
| `backend/app/api/router.py` | 路由汇总 |
| `backend/app/main.py` | `create_app()` 与 lifespan |
| `backend/tests/*` | pytest 用例 |
| `frontend/src/api.ts` | fetch 封装与错误归一 |
| `frontend/src/types.ts` | 与后端 schema 对齐的类型 |
| `frontend/src/status.ts` | 状态文案 / 颜色 / 时间格式化 |
| `frontend/src/stores/documents.ts` | 资料库状态 |
| `frontend/src/stores/runs.ts` | 运行列表、详情与 SSE 生命周期 |
| `frontend/src/components/DocumentPanel.vue` | 左列资料库 |
| `frontend/src/components/RunListPanel.vue` | 中列任务 |
| `frontend/src/components/RunDetailPanel.vue` | 右列详情 |

**统一约定（后续任务不再重复）：**

- 后端命令均在 `multi-agent-research/backend` 下执行，Python 用 `.\venv\Scripts\python`。
- 错误响应统一 `{"detail": {"code": "...", "message": "..."}}`。
- LLM prompt 首行都带角色标记 `（ROLE=planner|analyst|writer|reviewer）`，FakeLLM 据此路由。
- 所有 pytest 用例不触网。

---

### Task 1: 后端骨架与配置

**Files:**
- Create: `multi-agent-research/backend/requirements.txt`
- Create: `multi-agent-research/backend/pytest.ini`
- Create: `multi-agent-research/backend/.env.example`
- Create: `multi-agent-research/backend/.gitignore`
- Create: `multi-agent-research/backend/app/__init__.py`
- Create: `multi-agent-research/backend/app/config.py`
- Create: `multi-agent-research/backend/app/database.py`
- Create: `multi-agent-research/backend/tests/__init__.py`
- Test: `multi-agent-research/backend/tests/test_config.py`

- [ ] **Step 1: 建目录与依赖文件**

`backend/requirements.txt`：

```
fastapi==0.141.1
uvicorn==0.52.4
sqlalchemy==2.0.52
aiosqlite==0.20.0
pydantic-settings==2.15.0
httpx==0.28.1
pypdf==5.9.0
python-multipart==0.0.20
pytest==9.1.1
pytest-asyncio==1.3.0
```

`backend/pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
testpaths = tests
pythonpath = .
```

`backend/.env.example`：

```
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
CHUNK_SIZE=800
CHUNK_OVERLAP=100
RESEARCH_TOP_K=5
MAX_UPLOAD_MB=20
LLM_TIMEOUT=120
```

`backend/.gitignore`：

```
venv/
__pycache__/
.pytest_cache/
.env
data/
```

- [ ] **Step 2: 写失败测试**

`backend/tests/test_config.py`：

```python
from app.config import settings


def test_settings_defaults():
    assert settings.CHUNK_SIZE == 800
    assert settings.CHUNK_OVERLAP == 100
    assert settings.RESEARCH_TOP_K == 5
    assert settings.MAX_UPLOAD_MB == 20
    assert settings.DEEPSEEK_MODEL == "deepseek-chat"


def test_database_url_is_async_sqlite():
    assert settings.DATABASE_URL.startswith("sqlite+aiosqlite:///")
    assert settings.DATABASE_URL.endswith("app.db")
```

- [ ] **Step 3: 运行测试确认失败**

```powershell
cd multi-agent-research/backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\venv\Scripts\python -m pytest tests\test_config.py -v
```

预期：`ModuleNotFoundError: No module named 'app'`。

- [ ] **Step 4: 写实现**

`backend/app/__init__.py`：空文件（用 `New-Item -ItemType File -Force -Path app\__init__.py` 创建）。

`backend/app/config.py`：

```python
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """运行时配置；显式声明 env_file，避免 pydantic-settings 不自动加载 .env。"""

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    RESEARCH_TOP_K: int = 5
    MAX_UPLOAD_MB: int = 20
    LLM_TIMEOUT: float = 120.0
    DATABASE_URL: str = f"sqlite+aiosqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
```

`backend/app/database.py`：

```python
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _set_sqlite_pragma(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.DATABASE_URL)
        event.listen(_engine.sync_engine, "connect", _set_sqlite_pragma)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_db():
    async with get_sessionmaker()() as session:
        yield session


def reset_engine() -> None:
    global _engine, _session_factory
    _engine = None
    _session_factory = None


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
    reset_engine()
```

`backend/tests/__init__.py`：空文件。

- [ ] **Step 5: 运行测试确认通过**

```powershell
.\venv\Scripts\python -m pytest tests\test_config.py -v
```

预期：`2 passed`。

- [ ] **Step 6: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/backend/requirements.txt multi-agent-research/backend/pytest.ini multi-agent-research/backend/.env.example multi-agent-research/backend/.gitignore multi-agent-research/backend/app/__init__.py multi-agent-research/backend/app/config.py multi-agent-research/backend/app/database.py multi-agent-research/backend/tests/__init__.py multi-agent-research/backend/tests/test_config.py
git commit -m "feat(multi-agent-research): 后端骨架与配置"
```

---

### Task 2: 数据模型

**Files:**
- Create: `multi-agent-research/backend/app/models/__init__.py`
- Create: `multi-agent-research/backend/app/models/content.py`
- Create: `multi-agent-research/backend/tests/conftest.py`
- Test: `multi-agent-research/backend/tests/test_models.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/conftest.py`：

```python
import pytest_asyncio

from app import database
from app.config import settings


@pytest_asyncio.fixture
async def session_factory(tmp_path, monkeypatch):
    url = f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    await database.dispose_engine()
    database.reset_engine()
    async with database.get_engine().begin() as conn:
        await conn.run_sync(database.Base.metadata.create_all)
    yield database.get_sessionmaker()
    await database.dispose_engine()
    database.reset_engine()


@pytest_asyncio.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session
```

`backend/tests/test_models.py`：

```python
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Chunk, Document, Evidence, Run, Step, SubQuestion


async def _seed_document(session):
    doc = Document(filename="a.txt", ext="txt", size_bytes=10, char_count=10, chunk_count=1)
    session.add(doc)
    await session.flush()
    session.add(Chunk(document_id=doc.id, position=0, page=None, start=0, end=10, text="hello world"))
    await session.commit()
    return doc


async def test_document_chunks_roundtrip(db_session):
    doc = await _seed_document(db_session)
    chunks = (await db_session.execute(select(Chunk).where(Chunk.document_id == doc.id))).scalars().all()
    assert len(chunks) == 1
    assert chunks[0].text == "hello world"


async def test_delete_document_cascades_chunks(db_session):
    doc = await _seed_document(db_session)
    await db_session.delete(doc)
    await db_session.commit()
    chunks = (await db_session.execute(select(Chunk))).scalars().all()
    assert chunks == []


async def test_chunk_position_unique(db_session):
    doc = await _seed_document(db_session)
    db_session.add(Chunk(document_id=doc.id, position=0, page=None, start=0, end=1, text="dup"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_run_relations_and_evidence_snapshot(db_session):
    doc = await _seed_document(db_session)
    chunk = (await db_session.execute(select(Chunk))).scalar_one()
    run = Run(topic="RAG 趋势", status="done", review_issues=[{"severity": "low"}])
    db_session.add(run)
    await db_session.flush()
    question = SubQuestion(run_id=run.id, position=0, text="什么是 RAG", origin="auto")
    db_session.add(question)
    await db_session.flush()
    db_session.add(Evidence(
        run_id=run.id, sub_question_id=question.id, chunk_id=chunk.id,
        filename="a.txt", page=None, rank=1, score=1.5, snippet="hello",
    ))
    db_session.add(Step(run_id=run.id, agent="planner", position=0, status="succeeded"))
    await db_session.commit()

    await db_session.delete(doc)
    await db_session.commit()

    saved = (await db_session.execute(select(Evidence))).scalar_one()
    assert saved.chunk_id is None
    assert saved.filename == "a.txt"
    assert saved.rank == 1
    assert run.review_issues == [{"severity": "low"}]
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
.\venv\Scripts\python -m pytest tests\test_models.py -v
```

预期：`ModuleNotFoundError: No module named 'app.models'`。

- [ ] **Step 3: 写实现**

`backend/app/models/__init__.py`：

```python
from app.models.content import Chunk, Document, Evidence, Run, Step, SubQuestion

__all__ = ["Chunk", "Document", "Evidence", "Run", "Step", "SubQuestion"]
```

`backend/app/models/content.py`：

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    filename: Mapped[str] = mapped_column(String(255))
    ext: Mapped[str] = mapped_column(String(8))
    size_bytes: Mapped[int] = mapped_column(Integer)
    char_count: Mapped[int] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "position", name="uq_chunk_position"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    topic: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_issues: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sub_questions: Mapped[list["SubQuestion"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    steps: Mapped[list["Step"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class SubQuestion(Base):
    __tablename__ = "sub_questions"
    __table_args__ = (UniqueConstraint("run_id", "position", name="uq_question_position"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(8), default="auto")

    run: Mapped["Run"] = relationship(back_populates="sub_questions")


class Step(Base):
    __tablename__ = "steps"
    __table_args__ = (UniqueConstraint("run_id", "position", name="uq_step_position"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    agent: Mapped[str] = mapped_column(String(16))
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped["Run"] = relationship(back_populates="steps")


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("run_id", "rank", name="uq_evidence_rank"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    sub_question_id: Mapped[str] = mapped_column(
        ForeignKey("sub_questions.id", ondelete="CASCADE"), index=True
    )
    chunk_id: Mapped[str | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(default=0.0)
    snippet: Mapped[str] = mapped_column(Text)

    run: Mapped["Run"] = relationship(back_populates="evidence")
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
.\venv\Scripts\python -m pytest tests\test_models.py -v
```

预期：`4 passed`。

- [ ] **Step 5: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/backend/app/models multi-agent-research/backend/tests/conftest.py multi-agent-research/backend/tests/test_models.py
git commit -m "feat(multi-agent-research): 六张数据表与级联约束"
```

---

### Task 3: 切分器与中文分词

**Files:**
- Create: `multi-agent-research/backend/app/retrieval/__init__.py`
- Create: `multi-agent-research/backend/app/retrieval/chunker.py`
- Create: `multi-agent-research/backend/app/retrieval/tokenizer.py`
- Test: `multi-agent-research/backend/tests/test_chunker.py`
- Test: `multi-agent-research/backend/tests/test_tokenizer.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_chunker.py`：

```python
import pytest

from app.retrieval.chunker import TextChunker


def test_split_uses_800_with_100_overlap():
    text = "字" * 1000
    pieces = TextChunker(size=800, overlap=100).split(text)
    assert [len(p.text) for p in pieces] == [800, 300]
    assert pieces[0].start == 0 and pieces[0].end == 800
    assert pieces[1].start == 700 and pieces[1].end == 1000


def test_short_text_single_piece():
    pieces = TextChunker().split("你好世界")
    assert len(pieces) == 1
    assert pieces[0].text == "你好世界"


def test_blank_text_yields_nothing():
    assert TextChunker().split("   \n\t ") == []


def test_invalid_parameters():
    with pytest.raises(ValueError):
        TextChunker(size=0)
    with pytest.raises(ValueError):
        TextChunker(size=100, overlap=100)
    with pytest.raises(ValueError):
        TextChunker(size=100, overlap=-1)
```

`backend/tests/test_tokenizer.py`：

```python
from app.retrieval.tokenizer import tokenize


def test_chinese_bigram():
    assert tokenize("多智能体") == ["多智", "智能", "能体"]


def test_single_char_kept():
    assert tokenize("A") == ["a"]


def test_punctuation_and_space_removed():
    assert tokenize("RAG，是 检索！") == ["ra", "ag", "是检", "检索"]


def test_empty_text():
    assert tokenize("！！ ") == []
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
.\venv\Scripts\python -m pytest tests\test_chunker.py tests\test_tokenizer.py -v
```

预期：`ModuleNotFoundError: No module named 'app.retrieval'`。

- [ ] **Step 3: 写实现**

`backend/app/retrieval/__init__.py`：空文件。

`backend/app/retrieval/chunker.py`：

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Piece:
    text: str
    start: int
    end: int


class TextChunker:
    def __init__(self, size: int = 800, overlap: int = 100):
        if size <= 0:
            raise ValueError("size must be positive")
        if overlap < 0 or overlap >= size:
            raise ValueError("overlap must satisfy 0 <= overlap < size")
        self.size = size
        self.overlap = overlap

    def split(self, text: str) -> list[Piece]:
        step = self.size - self.overlap
        pieces: list[Piece] = []
        start = 0
        length = len(text)
        while start < length:
            end = min(start + self.size, length)
            chunk = text[start:end].strip()
            if chunk:
                pieces.append(Piece(text=chunk, start=start, end=end))
            start += step
        return pieces
```

`backend/app/retrieval/tokenizer.py`：

```python
import re

_SEGMENT = re.compile(r"[0-9a-z\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """按非字母数字汉字切段，段内取相邻 2-gram；单字段保留自身。"""
    tokens: list[str] = []
    for segment in _SEGMENT.findall(text.lower()):
        if len(segment) == 1:
            tokens.append(segment)
        else:
            tokens.extend(segment[i : i + 2] for i in range(len(segment) - 1))
    return tokens
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
.\venv\Scripts\python -m pytest tests\test_chunker.py tests\test_tokenizer.py -v
```

预期：`8 passed`。

- [ ] **Step 5: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/backend/app/retrieval/__init__.py multi-agent-research/backend/app/retrieval/chunker.py multi-agent-research/backend/app/retrieval/tokenizer.py multi-agent-research/backend/tests/test_chunker.py multi-agent-research/backend/tests/test_tokenizer.py
git commit -m "feat(multi-agent-research): 滑窗切分与中文 2-gram 分词"
```

---

### Task 4: BM25 检索与 Retriever

**Files:**
- Create: `multi-agent-research/backend/app/retrieval/base.py`
- Create: `multi-agent-research/backend/app/retrieval/bm25.py`
- Test: `multi-agent-research/backend/tests/test_bm25.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_bm25.py`：

```python
from app.models import Chunk, Document
from app.retrieval.bm25 import BM25Index, IndexedChunk, SqlBM25Retriever


def _chunk(chunk_id: str, text: str, page: int | None = None) -> IndexedChunk:
    return IndexedChunk(chunk_id=chunk_id, document_id="doc", filename="f.txt", page=page, text=text)


def test_ranking_prefers_more_term_hits():
    index = BM25Index()
    index.build([
        _chunk("c1", "检索增强生成把检索与大模型生成结合起来"),
        _chunk("c2", "本文讨论天气预报"),
        _chunk("c3", "检索增强生成需要向量检索"),
    ])
    results = index.search("检索增强生成", 5)
    assert [hit.chunk_id for hit, _ in results][:2] == ["c1", "c3"]
    assert results[0][1] > results[1][1]


def test_empty_index_returns_empty():
    assert BM25Index().search("检索", 5) == []


def test_empty_query_returns_empty():
    index = BM25Index()
    index.build([_chunk("c1", "检索增强生成")])
    assert index.search("！？", 5) == []


def test_tie_breaks_by_chunk_id():
    index = BM25Index()
    index.build([_chunk("b", "检索增强"), _chunk("a", "检索增强")])
    results = index.search("检索", 5)
    assert [hit.chunk_id for hit, _ in results] == ["a", "b"]


def test_top_k_truncates():
    index = BM25Index()
    index.build([_chunk(f"c{i}", "检索增强生成") for i in range(6)])
    assert len(index.search("检索", 2)) == 2


async def test_sql_retriever_reads_database(session_factory):
    async with session_factory() as session:
        doc = Document(filename="guide.txt", ext="txt", size_bytes=10, char_count=10, chunk_count=2)
        session.add(doc)
        await session.flush()
        session.add(Chunk(document_id=doc.id, position=0, page=None, start=0, end=20, text="检索增强生成是一种常见方案"))
        session.add(Chunk(document_id=doc.id, position=1, page=2, start=20, end=40, text="天气预报与股票行情"))
        await session.commit()

    retriever = SqlBM25Retriever(session_factory)
    hits = await retriever.search("检索增强", 5)
    assert len(hits) == 1
    assert hits[0].filename == "guide.txt"
    assert hits[0].snippet.startswith("检索增强生成")
    assert hits[0].score > 0
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
.\venv\Scripts\python -m pytest tests\test_bm25.py -v
```

预期：`ImportError: cannot import name 'BM25Index' from 'app.retrieval.bm25'`。

- [ ] **Step 3: 写实现**

`backend/app/retrieval/base.py`：

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EvidenceHit:
    chunk_id: str
    document_id: str
    filename: str
    page: int | None
    score: float
    snippet: str


class Retriever(Protocol):
    async def search(self, question: str, top_k: int) -> list[EvidenceHit]: ...
```

`backend/app/retrieval/bm25.py`：

```python
import math
from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Chunk, Document
from app.retrieval.base import EvidenceHit
from app.retrieval.tokenizer import tokenize


@dataclass(frozen=True)
class IndexedChunk:
    chunk_id: str
    document_id: str
    filename: str
    page: int | None
    text: str


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._chunks: list[IndexedChunk] = []
        self._tokens: list[list[str]] = []
        self._df: Counter[str] = Counter()
        self._avgdl = 0.0

    def build(self, chunks: Sequence[IndexedChunk]) -> None:
        self._chunks = list(chunks)
        self._tokens = [tokenize(chunk.text) for chunk in self._chunks]
        df: Counter[str] = Counter()
        for tokens in self._tokens:
            df.update(set(tokens))
        self._df = df
        total = sum(len(tokens) for tokens in self._tokens)
        self._avgdl = total / len(self._tokens) if self._tokens else 0.0

    @property
    def size(self) -> int:
        return len(self._chunks)

    def search(self, query: str, top_k: int) -> list[tuple[IndexedChunk, float]]:
        query_terms = list(dict.fromkeys(tokenize(query)))
        if not query_terms or not self._chunks:
            return []
        total_docs = len(self._chunks)
        scored: list[tuple[int, float]] = []
        for index, tokens in enumerate(self._tokens):
            counts = Counter(tokens)
            length = len(tokens)
            score = 0.0
            for term in query_terms:
                freq = counts.get(term, 0)
                if freq == 0:
                    continue
                df = self._df.get(term, 0)
                idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
                denom = freq + self.k1 * (1 - self.b + self.b * length / (self._avgdl or 1.0))
                score += idf * freq * (self.k1 + 1) / denom
            if score > 0:
                scored.append((index, round(score, 4)))
        scored.sort(key=lambda item: (-item[1], self._chunks[item[0]].chunk_id))
        return [(self._chunks[index], score) for index, score in scored[:top_k]]


class SqlBM25Retriever:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def search(self, question: str, top_k: int) -> list[EvidenceHit]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(Chunk, Document.filename)
                    .join(Document, Chunk.document_id == Document.id)
                    .order_by(Chunk.id)
                )
            ).all()
        index = BM25Index()
        index.build(
            [
                IndexedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    filename=filename,
                    page=chunk.page,
                    text=chunk.text,
                )
                for chunk, filename in rows
            ]
        )
        return [
            EvidenceHit(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                filename=hit.filename,
                page=hit.page,
                score=score,
                snippet=hit.text[:120],
            )
            for hit, score in index.search(question, top_k)
        ]
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
.\venv\Scripts\python -m pytest tests\test_bm25.py -v
```

预期：`6 passed`。

- [ ] **Step 5: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/backend/app/retrieval/base.py multi-agent-research/backend/app/retrieval/bm25.py multi-agent-research/backend/tests/test_bm25.py
git commit -m "feat(multi-agent-research): BM25 索引与数据库检索器"
```

---

### Task 5: 文档解析与入库

**Files:**
- Create: `multi-agent-research/backend/app/retrieval/ingest.py`
- Create: `multi-agent-research/backend/tests/fixtures/sample.pdf`（从 local-pdf-rag 复制）
- Test: `multi-agent-research/backend/tests/test_ingest.py`

- [ ] **Step 1: 准备 PDF 夹具**

```powershell
cd D:\StudyProjects\ai-practice\multi-agent-research\backend
New-Item -ItemType Directory -Force -Path tests\fixtures | Out-Null
Copy-Item ..\..\local-pdf-rag\backend\tests\fixtures\sample.pdf tests\fixtures\sample.pdf
```

- [ ] **Step 2: 写失败测试**

`backend/tests/test_ingest.py`：

```python
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import Chunk
from app.retrieval.chunker import TextChunker
from app.retrieval.ingest import IngestError, extract_pages, ingest_document

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


def test_extract_txt_has_no_page():
    pages = extract_pages("notes.txt", "你好，检索增强生成".encode("utf-8"))
    assert len(pages) == 1
    assert pages[0].page is None
    assert "检索增强生成" in pages[0].text


def test_extract_markdown():
    pages = extract_pages("readme.md", b"# Title\n\nbody")
    assert pages[0].text.startswith("# Title")


def test_pdf_pages_keep_page_numbers():
    pages = extract_pages("sample.pdf", FIXTURE.read_bytes())
    assert pages and pages[0].page == 1
    assert "Retrieval" in pages[0].text


def test_unsupported_extension():
    with pytest.raises(IngestError) as error:
        extract_pages("a.docx", b"x")
    assert error.value.code == "unsupported_file"


def test_broken_pdf():
    with pytest.raises(IngestError) as error:
        extract_pages("a.pdf", b"not a pdf")
    assert error.value.code == "parse_failed"


async def test_ingest_document_creates_chunks(db_session):
    data = ("检索增强生成" * 100).encode("utf-8")
    document = await ingest_document(db_session, "big.txt", data, TextChunker(size=100, overlap=20))
    assert document.filename == "big.txt"
    assert document.ext == "txt"
    assert document.chunk_count > 1
    stored = (
        await db_session.execute(
            select(func.count(Chunk.id)).where(Chunk.document_id == document.id)
        )
    ).scalar_one()
    assert stored == document.chunk_count


async def test_empty_document_rejected(db_session):
    with pytest.raises(IngestError) as error:
        await ingest_document(db_session, "blank.txt", b"   \n", TextChunker())
    assert error.value.code == "empty_document"
```

- [ ] **Step 3: 运行测试确认失败**

```powershell
.\venv\Scripts\python -m pytest tests\test_ingest.py -v
```

预期：`ModuleNotFoundError: No module named 'app.retrieval.ingest'`。

- [ ] **Step 4: 写实现**

`backend/app/retrieval/ingest.py`：

```python
import io
from dataclasses import dataclass

from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document
from app.retrieval.chunker import TextChunker


@dataclass(frozen=True)
class ParsedPage:
    page: int | None
    text: str


class IngestError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


ALLOWED_EXTENSIONS = frozenset({"pdf", "txt", "md"})


def file_ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def extract_pages(filename: str, data: bytes) -> list[ParsedPage]:
    ext = file_ext(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise IngestError("unsupported_file", f"不支持的格式：{ext or '未知'}")
    if ext == "pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted and not reader.decrypt(""):
                raise IngestError("parse_failed", "PDF 已加密")
            return [
                ParsedPage(page=index + 1, text=(page.extract_text() or ""))
                for index, page in enumerate(reader.pages)
            ]
        except IngestError:
            raise
        except Exception as exc:
            raise IngestError("parse_failed", f"PDF 解析失败：{exc}") from exc
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("gb18030")
        except UnicodeDecodeError as exc:
            raise IngestError("parse_failed", "文本编码无法识别") from exc
    return [ParsedPage(page=None, text=text)]


async def ingest_document(
    session: AsyncSession, filename: str, data: bytes, chunker: TextChunker
) -> Document:
    pages = extract_pages(filename, data)
    rows: list[Chunk] = []
    position = 0
    for page in pages:
        for piece in chunker.split(page.text):
            rows.append(
                Chunk(position=position, page=page.page, start=piece.start, end=piece.end, text=piece.text)
            )
            position += 1
    if not rows:
        raise IngestError("empty_document", "没有可提取的文本")
    document = Document(
        filename=filename,
        ext=file_ext(filename),
        size_bytes=len(data),
        char_count=sum(len(page.text) for page in pages),
        chunk_count=len(rows),
    )
    session.add(document)
    await session.flush()
    for row in rows:
        row.document_id = document.id
        session.add(row)
    await session.commit()
    await session.refresh(document)
    return document
```

- [ ] **Step 5: 运行测试确认通过**

```powershell
.\venv\Scripts\python -m pytest tests\test_ingest.py -v
```

预期：`7 passed`。

- [ ] **Step 6: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/backend/app/retrieval/ingest.py multi-agent-research/backend/tests/test_ingest.py multi-agent-research/backend/tests/fixtures/sample.pdf
git commit -m "feat(multi-agent-research): PDF/TXT/MD 解析入库"
```

---

### Task 6: LLM 客户端与 FakeLLM

**Files:**
- Create: `multi-agent-research/backend/app/services/__init__.py`
- Create: `multi-agent-research/backend/app/services/llm.py`
- Test: `multi-agent-research/backend/tests/test_llm.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_llm.py`：

```python
import json

import httpx
import pytest

from app.services.llm import DeepSeekClient, FakeLLM, LLMError


def _client(handler):
    return DeepSeekClient(
        api_key="test-key",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        timeout=5,
        transport=httpx.MockTransport(handler),
    )


async def test_complete_returns_content():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "deepseek-chat"
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})

    assert await _client(handler).complete("system", "user") == "hello"


async def test_json_mode_sets_response_format():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    await _client(handler).complete("system", "user", json_mode=True)
    assert captured["response_format"] == {"type": "json_object"}


async def test_network_error_maps_to_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(LLMError) as error:
        await _client(handler).complete("s", "u")
    assert error.value.code == "llm_unreachable"


async def test_non_200_maps_to_bad_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(LLMError) as error:
        await _client(handler).complete("s", "u")
    assert error.value.code == "llm_bad_response"


async def test_broken_structure_maps_to_bad_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    with pytest.raises(LLMError) as error:
        await _client(handler).complete("s", "u")
    assert error.value.code == "llm_bad_response"


async def test_fake_llm_routes_by_marker():
    llm = FakeLLM({"ROLE=planner": '{"sub_questions": ["q1"]}'}, default="{}")
    assert await llm.complete("你是规划助手（ROLE=planner）", "主题") == '{"sub_questions": ["q1"]}'
    assert await llm.complete("其他", "其他") == "{}"
    assert len(llm.calls) == 2
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
.\venv\Scripts\python -m pytest tests\test_llm.py -v
```

预期：`ModuleNotFoundError: No module named 'app.services'`。

- [ ] **Step 3: 写实现**

`backend/app/services/__init__.py`：空文件。

`backend/app/services/llm.py`：

```python
import asyncio
from typing import Protocol

import httpx

from app.config import settings


class LLMError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class LLMClient(Protocol):
    async def complete(self, system: str, user: str, *, json_mode: bool = False) -> str: ...


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.transport = transport

    async def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
        except httpx.HTTPError as exc:
            raise LLMError("llm_unreachable", f"DeepSeek 请求失败：{exc}") from exc
        if response.status_code != 200:
            raise LLMError("llm_bad_response", f"DeepSeek 返回 {response.status_code}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("llm_bad_response", "DeepSeek 响应结构异常") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("llm_bad_response", "DeepSeek 返回空内容")
        return content


class FakeLLM:
    def __init__(self, responses: dict[str, str] | None = None, default: str = "{}", delay: float = 0.0):
        self.responses = responses or {}
        self.default = default
        self.delay = delay
        self.calls: list[dict] = []

    async def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        if self.delay:
            await asyncio.sleep(self.delay)
        self.calls.append({"system": system, "user": user, "json_mode": json_mode})
        for marker, response in self.responses.items():
            if marker in system or marker in user:
                return response
        return self.default


def llm_configured() -> bool:
    return bool(settings.DEEPSEEK_API_KEY.strip())


def get_llm() -> LLMClient:
    return DeepSeekClient(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model=settings.DEEPSEEK_MODEL,
        timeout=settings.LLM_TIMEOUT,
    )
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
.\venv\Scripts\python -m pytest tests\test_llm.py -v
```

预期：`6 passed`。

- [ ] **Step 5: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/backend/app/services/__init__.py multi-agent-research/backend/app/services/llm.py multi-agent-research/backend/tests/test_llm.py
git commit -m "feat(multi-agent-research): DeepSeek 客户端与可注入 FakeLLM"
```

---

### Task 7: Agent 基类与 Planner

**Files:**
- Create: `multi-agent-research/backend/app/agents/__init__.py`
- Create: `multi-agent-research/backend/app/agents/base.py`
- Create: `multi-agent-research/backend/app/agents/prompts.py`
- Create: `multi-agent-research/backend/app/agents/planner.py`
- Test: `multi-agent-research/backend/tests/test_agents.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_agents.py`：

```python
import pytest

from app.agents.base import AgentOutputError, parse_json, strip_fence
from app.agents.planner import Planner
from app.services.llm import FakeLLM


class SequenceLLM:
    """按顺序返回预设内容，用于验证重试。"""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = 0

    async def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        self.calls += 1
        return self.responses.pop(0)


def test_strip_fence_removes_json_block():
    assert strip_fence('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_fence('{"a": 1}') == '{"a": 1}'


def test_parse_json_rejects_plain_text():
    with pytest.raises(AgentOutputError):
        parse_json("这不是 JSON")


async def test_planner_dedupes_and_trims():
    llm = FakeLLM({
        "ROLE=planner": '{"sub_questions": [" 什么是 RAG ", "什么是 RAG", "", "BM25 怎么算"], "rationale": "先定义再比较"}'
    })
    result = await Planner(llm).plan("RAG 调研", [{"filename": "a.pdf", "chunks": 3}])
    assert result.sub_questions == ["什么是 RAG", "BM25 怎么算"]
    assert result.rationale == "先定义再比较"


async def test_planner_rejects_empty_questions():
    llm = FakeLLM({"ROLE=planner": '{"sub_questions": ["  ", ""]}'})
    with pytest.raises(AgentOutputError):
        await Planner(llm).plan("主题", [])


async def test_planner_retries_once_on_bad_json():
    llm = SequenceLLM(["not json", '{"sub_questions": ["q1"]}'])
    result = await Planner(llm).plan("主题", [])
    assert result.sub_questions == ["q1"]
    assert llm.calls == 2


async def test_planner_gives_up_after_retry():
    llm = SequenceLLM(["bad", "still bad"])
    with pytest.raises(AgentOutputError):
        await Planner(llm).plan("主题", [])
    assert llm.calls == 2
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
.\venv\Scripts\python -m pytest tests\test_agents.py -v
```

预期：`ModuleNotFoundError: No module named 'app.agents'`。

- [ ] **Step 3: 写实现**

`backend/app/agents/__init__.py`：空文件。

`backend/app/agents/base.py`：

```python
import json
import re
from typing import Any, Callable

from app.services.llm import LLMClient


class AgentOutputError(ValueError):
    pass


def strip_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_json(raw: str) -> Any:
    try:
        return json.loads(strip_fence(raw))
    except json.JSONDecodeError as exc:
        raise AgentOutputError(f"模型输出不是合法 JSON：{exc}") from exc


Validator = Callable[[Any], Any]


class JsonAgent:
    def __init__(self, llm: LLMClient, prompt: str, validator: Validator):
        self._llm = llm
        self._prompt = prompt
        self._validator = validator

    async def run(self, payload: dict) -> Any:
        last_error: Exception | None = None
        for _ in range(2):
            raw = await self._llm.complete(
                system=self._prompt,
                user=json.dumps(payload, ensure_ascii=False),
                json_mode=True,
            )
            try:
                return self._validator(parse_json(raw))
            except AgentOutputError as exc:
                last_error = exc
        raise AgentOutputError(f"重试后仍无效：{last_error}")
```

`backend/app/agents/prompts.py`：

```python
PLANNER_PROMPT = """你是调研规划助手（ROLE=planner）。根据主题与资料库概览，把调研拆成 3-6 个可独立检索的子问题。
只输出 JSON：{"sub_questions": ["..."], "rationale": "一句话说明拆解思路"}。
子问题必须具体、可被本地资料库回答，不要写“了解背景”这类无法检索的表述。"""

ANALYST_PROMPT = """你是资料分析助手（ROLE=analyst）。根据子问题与给定证据，提炼 2-6 条要点。
只输出 JSON：{"points": [{"text": "要点正文", "evidence": [1, 3]}]}。
evidence 只能使用证据列表中出现的编号；没有证据支持的结论不要输出。"""

WRITER_PROMPT = """你是调研报告撰写助手（ROLE=writer）。根据主题、要点与证据表，写一份 Markdown 调研报告。
要求：
1. 结构包含：标题、概述、按子问题分节的分析、结论。
2. 每个事实性结论后用 [n] 标注证据编号，编号只能来自证据表。
3. 不要编造证据表之外的事实；资料不足处写明“资料未覆盖”。
只输出报告正文，不要输出解释或代码围栏。"""

REVIEWER_PROMPT = """你是事实核查助手（ROLE=reviewer）。核对报告中每条带编号的结论是否被对应证据支持。
只输出 JSON：{"issues": [{"severity": "high|medium|low", "claim": "报告原句", "problem": "问题", "suggestion": "建议"}], "summary": "总体结论"}。
没有问题时 issues 输出空数组。"""
```

`backend/app/agents/planner.py`：

```python
from dataclasses import dataclass
from typing import Any

from app.agents.base import AgentOutputError, JsonAgent
from app.agents.prompts import PLANNER_PROMPT
from app.services.llm import LLMClient


@dataclass(frozen=True)
class PlanResult:
    sub_questions: list[str]
    rationale: str


def _validate(data: Any) -> PlanResult:
    if not isinstance(data, dict):
        raise AgentOutputError("顶层必须是对象")
    raw = data.get("sub_questions")
    if not isinstance(raw, list):
        raise AgentOutputError("sub_questions 必须是数组")
    questions: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise AgentOutputError("子问题必须是字符串")
        text = item.strip()
        if text and text not in questions:
            questions.append(text)
    if not 1 <= len(questions) <= 8:
        raise AgentOutputError("子问题数量必须在 1-8 之间")
    rationale = data.get("rationale", "")
    return PlanResult(sub_questions=questions, rationale=rationale if isinstance(rationale, str) else "")


class Planner:
    def __init__(self, llm: LLMClient):
        self._agent = JsonAgent(llm, PLANNER_PROMPT, _validate)

    async def plan(self, topic: str, library: list[dict]) -> PlanResult:
        return await self._agent.run({"topic": topic, "library": library})
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
.\venv\Scripts\python -m pytest tests\test_agents.py -v
```

预期：`6 passed`。

- [ ] **Step 5: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/backend/app/agents/__init__.py multi-agent-research/backend/app/agents/base.py multi-agent-research/backend/app/agents/prompts.py multi-agent-research/backend/app/agents/planner.py multi-agent-research/backend/tests/test_agents.py
git commit -m "feat(multi-agent-research): Agent 基类、prompt 与 Planner"
```

---

### Task 8: Researcher 与 Analyst

**Files:**
- Create: `multi-agent-research/backend/app/agents/researcher.py`
- Create: `multi-agent-research/backend/app/agents/analyst.py`
- Modify: `multi-agent-research/backend/tests/test_agents.py`（追加用例）

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/test_agents.py` 末尾追加：

```python
from app.agents.analyst import Analyst
from app.agents.researcher import Researcher
from app.retrieval.base import EvidenceHit


class StaticRetriever:
    def __init__(self, hits: list[EvidenceHit]):
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    async def search(self, question: str, top_k: int) -> list[EvidenceHit]:
        self.calls.append((question, top_k))
        return self.hits[:top_k]


def _hit(chunk_id: str, score: float) -> EvidenceHit:
    return EvidenceHit(chunk_id=chunk_id, document_id="d", filename="f.txt", page=1, score=score, snippet="snippet")


async def test_researcher_passes_top_k():
    retriever = StaticRetriever([_hit("c1", 1.0), _hit("c2", 0.5)])
    hits = await Researcher(retriever, top_k=2).research("什么是 RAG")
    assert [hit.chunk_id for hit in hits] == ["c1", "c2"]
    assert retriever.calls == [("什么是 RAG", 2)]


async def test_analyst_flags_out_of_range_evidence():
    llm = FakeLLM({
        "ROLE=analyst": '{"points": [{"text": "RAG 结合检索与生成", "evidence": [1, 9]}]}'
    })
    result = await Analyst(llm).analyze("什么是 RAG", [{"rank": 1, "text": "证据"}])
    assert result.points[0].text == "RAG 结合检索与生成"
    assert result.points[0].evidence == [1, 9]
    assert result.out_of_range == [9]


async def test_analyst_requires_points():
    llm = FakeLLM({"ROLE=analyst": '{"points": []}'})
    with pytest.raises(AgentOutputError):
        await Analyst(llm).analyze("q", [{"rank": 1, "text": "证据"}])
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
.\venv\Scripts\python -m pytest tests\test_agents.py -v
```

预期：`ModuleNotFoundError: No module named 'app.agents.analyst'`。

- [ ] **Step 3: 写实现**

`backend/app/agents/researcher.py`：

```python
from app.retrieval.base import EvidenceHit, Retriever


class Researcher:
    def __init__(self, retriever: Retriever, top_k: int = 5):
        self._retriever = retriever
        self._top_k = top_k

    async def research(self, question: str) -> list[EvidenceHit]:
        return await self._retriever.search(question, self._top_k)
```

`backend/app/agents/analyst.py`：

```python
from dataclasses import dataclass
from typing import Any

from app.agents.base import AgentOutputError, JsonAgent
from app.agents.prompts import ANALYST_PROMPT
from app.services.llm import LLMClient


@dataclass(frozen=True)
class Point:
    text: str
    evidence: list[int]


@dataclass(frozen=True)
class AnalysisResult:
    points: list[Point]
    out_of_range: list[int]


def _validate(data: Any) -> list[Point]:
    if not isinstance(data, dict):
        raise AgentOutputError("顶层必须是对象")
    raw = data.get("points")
    if not isinstance(raw, list) or not raw:
        raise AgentOutputError("points 必须是非空数组")
    points: list[Point] = []
    for item in raw:
        if not isinstance(item, dict):
            raise AgentOutputError("要点必须是对象")
        text = item.get("text")
        evidence = item.get("evidence")
        if not isinstance(text, str) or not text.strip():
            raise AgentOutputError("要点正文不能为空")
        if not isinstance(evidence, list) or not evidence:
            raise AgentOutputError("要点必须带证据编号")
        if any(not isinstance(rank, int) for rank in evidence):
            raise AgentOutputError("证据编号必须是整数")
        points.append(Point(text=text.strip(), evidence=list(evidence)))
    return points


class Analyst:
    def __init__(self, llm: LLMClient):
        self._agent = JsonAgent(llm, ANALYST_PROMPT, _validate)

    async def analyze(self, question: str, evidence: list[dict]) -> AnalysisResult:
        points = await self._agent.run({"question": question, "evidence": evidence})
        allowed = {item["rank"] for item in evidence}
        out_of_range = sorted({rank for point in points for rank in point.evidence if rank not in allowed})
        return AnalysisResult(points=points, out_of_range=out_of_range)
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
.\venv\Scripts\python -m pytest tests\test_agents.py -v
```

预期：`9 passed`。

- [ ] **Step 5: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/backend/app/agents/researcher.py multi-agent-research/backend/app/agents/analyst.py multi-agent-research/backend/tests/test_agents.py
git commit -m "feat(multi-agent-research): Researcher 与 Analyst"
```

---

### Task 9: Writer 与 Reviewer

**Files:**
- Create: `multi-agent-research/backend/app/agents/writer.py`
- Create: `multi-agent-research/backend/app/agents/reviewer.py`
- Modify: `multi-agent-research/backend/tests/test_agents.py`（追加用例）

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/test_agents.py` 末尾追加：

```python
from app.agents.reviewer import Reviewer
from app.agents.writer import Writer


async def test_writer_requires_citation():
    llm = FakeLLM({"ROLE=writer": "这是一篇没有任何引用的报告。"})
    with pytest.raises(AgentOutputError):
        await Writer(llm).write("主题", [{"text": "要点"}], [{"rank": 1, "filename": "a.txt"}])


async def test_writer_returns_markdown():
    llm = FakeLLM({"ROLE=writer": "# 报告\n\nRAG 结合检索与生成 [1]。"})
    report = await Writer(llm).write("主题", [{"text": "要点"}], [{"rank": 1, "filename": "a.txt"}])
    assert report.startswith("# 报告")


async def test_reviewer_accepts_empty_issues():
    llm = FakeLLM({"ROLE=reviewer": '{"issues": [], "summary": "未发现问题"}'})
    result = await Reviewer(llm).review("报告 [1]", [{"rank": 1, "filename": "a.txt"}])
    assert result.issues == []
    assert result.summary == "未发现问题"


async def test_reviewer_rejects_unknown_severity():
    llm = FakeLLM({
        "ROLE=reviewer": '{"issues": [{"severity": "fatal", "claim": "x", "problem": "y", "suggestion": "z"}], "summary": ""}'
    })
    with pytest.raises(AgentOutputError):
        await Reviewer(llm).review("报告 [1]", [{"rank": 1, "filename": "a.txt"}])
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
.\venv\Scripts\python -m pytest tests\test_agents.py -v
```

预期：`ModuleNotFoundError: No module named 'app.agents.reviewer'`。

- [ ] **Step 3: 写实现**

`backend/app/agents/writer.py`：

```python
import json
import re

from app.agents.base import AgentOutputError
from app.agents.prompts import WRITER_PROMPT
from app.services.llm import LLMClient


class Writer:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    async def write(self, topic: str, points: list[dict], evidence: list[dict]) -> str:
        raw = await self._llm.complete(
            system=WRITER_PROMPT,
            user=json.dumps({"topic": topic, "points": points, "evidence": evidence}, ensure_ascii=False),
            json_mode=False,
        )
        report = raw.strip()
        if not report:
            raise AgentOutputError("报告为空")
        if not re.search(r"\[\d+\]", report):
            raise AgentOutputError("报告缺少引用编号")
        return report
```

`backend/app/agents/reviewer.py`：

```python
from dataclasses import dataclass
from typing import Any

from app.agents.base import AgentOutputError, JsonAgent
from app.agents.prompts import REVIEWER_PROMPT
from app.services.llm import LLMClient

SEVERITIES = frozenset({"high", "medium", "low"})


@dataclass(frozen=True)
class ReviewIssue:
    severity: str
    claim: str
    problem: str
    suggestion: str


@dataclass(frozen=True)
class ReviewResult:
    issues: list[ReviewIssue]
    summary: str


def _validate(data: Any) -> ReviewResult:
    if not isinstance(data, dict):
        raise AgentOutputError("顶层必须是对象")
    raw = data.get("issues")
    if not isinstance(raw, list):
        raise AgentOutputError("issues 必须是数组")
    issues: list[ReviewIssue] = []
    for item in raw:
        if not isinstance(item, dict):
            raise AgentOutputError("问题项必须是对象")
        severity = item.get("severity")
        if severity not in SEVERITIES:
            raise AgentOutputError("severity 必须是 high/medium/low")
        issues.append(
            ReviewIssue(
                severity=severity,
                claim=str(item.get("claim", "")),
                problem=str(item.get("problem", "")),
                suggestion=str(item.get("suggestion", "")),
            )
        )
    summary = data.get("summary", "")
    return ReviewResult(issues=issues, summary=summary if isinstance(summary, str) else "")


class Reviewer:
    def __init__(self, llm: LLMClient):
        self._agent = JsonAgent(llm, REVIEWER_PROMPT, _validate)

    async def review(self, report: str, evidence: list[dict]) -> ReviewResult:
        return await self._agent.run({"report": report, "evidence": evidence})
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
.\venv\Scripts\python -m pytest tests\test_agents.py -v
```

预期：`13 passed`。

- [ ] **Step 5: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/backend/app/agents/writer.py multi-agent-research/backend/app/agents/reviewer.py multi-agent-research/backend/tests/test_agents.py
git commit -m "feat(multi-agent-research): Writer 与 Reviewer"
```

---

### Task 10: 状态机与事件总线

**Files:**
- Create: `multi-agent-research/backend/app/orchestrator/__init__.py`
- Create: `multi-agent-research/backend/app/orchestrator/state.py`
- Create: `multi-agent-research/backend/app/orchestrator/events.py`
- Test: `multi-agent-research/backend/tests/test_state.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_state.py`：

```python
import pytest

from app.orchestrator.events import EventBus
from app.orchestrator.state import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    InvalidTransition,
    RunStatus,
    can_transition,
    ensure_transition,
)


def test_happy_path_transitions():
    path = [
        RunStatus.PENDING, RunStatus.PLANNING, RunStatus.AWAITING_OUTLINE,
        RunStatus.RESEARCHING, RunStatus.ANALYZING, RunStatus.WRITING,
        RunStatus.REVIEWING, RunStatus.DONE,
    ]
    for source, target in zip(path, path[1:]):
        assert can_transition(source, target)


def test_outline_can_be_resaved():
    assert can_transition(RunStatus.AWAITING_OUTLINE, RunStatus.AWAITING_OUTLINE)


def test_active_cannot_jump_to_done():
    assert not can_transition(RunStatus.RESEARCHING, RunStatus.DONE)
    with pytest.raises(InvalidTransition):
        ensure_transition(RunStatus.RESEARCHING, RunStatus.DONE)


def test_terminal_is_final():
    for status in TERMINAL_STATUSES:
        for target in RunStatus:
            assert not can_transition(status, target)


def test_active_and_terminal_sets():
    assert RunStatus.PLANNING in ACTIVE_STATUSES
    assert RunStatus.AWAITING_OUTLINE not in ACTIVE_STATUSES
    assert RunStatus.FAILED in TERMINAL_STATUSES


async def test_event_bus_fanout_and_unsubscribe():
    bus = EventBus()
    first = bus.subscribe("run-1")
    second = bus.subscribe("run-1")
    await bus.publish("run-1", "step", {"id": "s1"})
    assert (await first.get()).name == "step"
    assert (await second.get()).data == {"id": "s1"}
    bus.unsubscribe("run-1", first)
    bus.unsubscribe("run-1", second)
    assert bus.subscriber_count("run-1") == 0


async def test_publish_without_subscriber_is_noop():
    await EventBus().publish("nobody", "run", {"status": "done"})
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
.\venv\Scripts\python -m pytest tests\test_state.py -v
```

预期：`ModuleNotFoundError: No module named 'app.orchestrator'`。

- [ ] **Step 3: 写实现**

`backend/app/orchestrator/__init__.py`：空文件。

`backend/app/orchestrator/state.py`：

```python
from enum import StrEnum


class RunStatus(StrEnum):
    PENDING = "pending"
    PLANNING = "planning"
    AWAITING_OUTLINE = "awaiting_outline"
    RESEARCHING = "researching"
    ANALYZING = "analyzing"
    WRITING = "writing"
    REVIEWING = "reviewing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_STATUSES = frozenset(
    {
        RunStatus.PLANNING,
        RunStatus.RESEARCHING,
        RunStatus.ANALYZING,
        RunStatus.WRITING,
        RunStatus.REVIEWING,
    }
)

TERMINAL_STATUSES = frozenset({RunStatus.DONE, RunStatus.FAILED, RunStatus.CANCELLED})

_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.PENDING: frozenset({RunStatus.PLANNING}),
    RunStatus.PLANNING: frozenset({RunStatus.AWAITING_OUTLINE, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.AWAITING_OUTLINE: frozenset(
        {RunStatus.AWAITING_OUTLINE, RunStatus.RESEARCHING, RunStatus.CANCELLED}
    ),
    RunStatus.RESEARCHING: frozenset({RunStatus.ANALYZING, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.ANALYZING: frozenset({RunStatus.WRITING, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.WRITING: frozenset({RunStatus.REVIEWING, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.REVIEWING: frozenset({RunStatus.DONE, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.DONE: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}


class InvalidTransition(RuntimeError):
    pass


def can_transition(source: RunStatus, target: RunStatus) -> bool:
    return target in _TRANSITIONS.get(source, frozenset())


def ensure_transition(source: RunStatus, target: RunStatus) -> None:
    if not can_transition(source, target):
        raise InvalidTransition(f"不允许的状态转移：{source} -> {target}")
```

`backend/app/orchestrator/events.py`：

```python
import asyncio
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    name: str
    data: dict


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, set[asyncio.Queue[Event]]] = defaultdict(set)

    def subscribe(self, run_id: str) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers[run_id].add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[Event]) -> None:
        self._subscribers[run_id].discard(queue)
        if not self._subscribers[run_id]:
            self._subscribers.pop(run_id, None)

    async def publish(self, run_id: str, name: str, data: dict) -> None:
        event = Event(name=name, data=data)
        for queue in list(self._subscribers.get(run_id, ())):
            queue.put_nowait(event)

    def subscriber_count(self, run_id: str) -> int:
        return len(self._subscribers.get(run_id, ()))
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
.\venv\Scripts\python -m pytest tests\test_state.py -v
```

预期：`7 passed`。

- [ ] **Step 5: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/backend/app/orchestrator/__init__.py multi-agent-research/backend/app/orchestrator/state.py multi-agent-research/backend/app/orchestrator/events.py multi-agent-research/backend/tests/test_state.py
git commit -m "feat(multi-agent-research): 状态机与事件总线"
```

---

### Task 11: 编排器 Runner

**Files:**
- Create: `multi-agent-research/backend/app/orchestrator/runner.py`
- Test: `multi-agent-research/backend/tests/test_orchestrator.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_orchestrator.py`：

```python
import asyncio

from sqlalchemy import select

from app.models import Chunk, Document, Evidence, Run, Step, SubQuestion
from app.orchestrator.events import EventBus
from app.orchestrator.runner import Runner
from app.retrieval.base import EvidenceHit
from app.services.llm import FakeLLM

RESPONSES = {
    "ROLE=planner": '{"sub_questions": ["什么是 RAG", "BM25 如何工作"], "rationale": "先定义再方法"}',
    "ROLE=analyst": '{"points": [{"text": "RAG 结合检索与生成", "evidence": [1]}]}',
    "ROLE=writer": "# 调研报告\n\nRAG 结合检索与生成 [1]。",
    "ROLE=reviewer": '{"issues": [], "summary": "未发现问题"}',
}


class StaticRetriever:
    def __init__(self, hits_by_question: dict[str, list[EvidenceHit]]):
        self.hits_by_question = hits_by_question

    async def search(self, question: str, top_k: int) -> list[EvidenceHit]:
        return self.hits_by_question.get(question, [])[:top_k]


def _hit(chunk_id: str, score: float = 1.0) -> EvidenceHit:
    return EvidenceHit(chunk_id=chunk_id, document_id="d", filename="guide.txt", page=1, score=score, snippet="snippet")


def _runner(session_factory, llm=None, retriever=None) -> Runner:
    return Runner(
        session_factory=session_factory,
        bus=EventBus(),
        retriever=retriever or StaticRetriever({}),
        llm=llm or FakeLLM(RESPONSES),
    )


async def _wait_idle(runner: Runner) -> None:
    for _ in range(200):
        if not runner.is_busy():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("orchestrator did not finish in time")


async def _create_run(session_factory, topic: str = "RAG 调研") -> str:
    async with session_factory() as session:
        run = Run(topic=topic, status="pending")
        session.add(run)
        await session.commit()
        return run.id


async def test_planning_stops_at_awaiting_outline(session_factory):
    run_id = await _create_run(session_factory)
    runner = _runner(session_factory)
    runner.start_planning(run_id)
    await _wait_idle(runner)

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        questions = (await session.execute(select(SubQuestion).order_by(SubQuestion.position))).scalars().all()
        steps = (await session.execute(select(Step).order_by(Step.position))).scalars().all()
    assert run.status == "awaiting_outline"
    assert [q.text for q in questions] == ["什么是 RAG", "BM25 如何工作"]
    assert len(steps) == 1 and steps[0].agent == "planner" and steps[0].status == "succeeded"


async def test_pipeline_produces_report_and_ranked_evidence(session_factory):
    async with session_factory() as session:
        document = Document(filename="guide.txt", ext="txt", size_bytes=1, char_count=1, chunk_count=2)
        session.add(document)
        await session.flush()
        session.add(Chunk(document_id=document.id, position=0, page=None, start=0, end=5, text="检索增强生成"))
        session.add(Chunk(document_id=document.id, position=1, page=None, start=5, end=10, text="BM25 打分"))
        await session.commit()
        chunk_ids = [row.id for row in (await session.execute(select(Chunk).order_by(Chunk.position))).scalars().all()]

    run_id = await _create_run(session_factory)
    retriever = StaticRetriever(
        {
            "什么是 RAG": [_hit(chunk_ids[0], 1.9), _hit(chunk_ids[1], 1.2)],
            "BM25 如何工作": [_hit(chunk_ids[1], 2.5)],
        }
    )
    runner = _runner(session_factory, retriever=retriever)
    runner.start_planning(run_id)
    await _wait_idle(runner)
    runner.start_pipeline(run_id)
    await _wait_idle(runner)

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        evidence = (await session.execute(select(Evidence).order_by(Evidence.rank))).scalars().all()
        steps = (await session.execute(select(Step).order_by(Step.position))).scalars().all()
    assert run.status == "done"
    assert [item.rank for item in evidence] == [1, 2, 3]
    assert evidence[2].filename == "guide.txt"
    assert run.report_markdown.startswith("# 调研报告")
    assert run.review_issues == []
    assert [step.agent for step in steps] == [
        "planner", "researcher", "researcher", "analyst", "analyst", "writer", "reviewer",
    ]


async def test_cancel_marks_running_step_skipped(session_factory):
    run_id = await _create_run(session_factory)
    slow = FakeLLM(RESPONSES, delay=0.3)
    runner = _runner(session_factory, llm=slow)
    runner.start_planning(run_id)
    await asyncio.sleep(0.05)
    assert runner.cancel(run_id) is True
    await _wait_idle(runner)

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        steps = (await session.execute(select(Step))).scalars().all()
    assert run.status == "cancelled"
    assert steps[0].status == "skipped"


async def test_bad_json_marks_run_failed(session_factory):
    run_id = await _create_run(session_factory)
    runner = _runner(session_factory, llm=FakeLLM({"ROLE=planner": "not json"}))
    runner.start_planning(run_id)
    await _wait_idle(runner)

    async with session_factory() as session:
        run = await session.get(Run, run_id)
    assert run.status == "failed"
    assert run.error_code == "llm_bad_json"
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
.\venv\Scripts\python -m pytest tests\test_orchestrator.py -v
```

预期：`ModuleNotFoundError: No module named 'app.orchestrator.runner'`。

- [ ] **Step 3: 写实现**

`backend/app/orchestrator/runner.py`：

```python
import asyncio
from dataclasses import asdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.analyst import Analyst
from app.agents.base import AgentOutputError
from app.agents.planner import Planner
from app.agents.researcher import Researcher
from app.agents.reviewer import Reviewer
from app.agents.writer import Writer
from app.config import settings
from app.models import Chunk, Document, Evidence, Run, Step, SubQuestion
from app.models.content import utcnow
from app.orchestrator.events import EventBus
from app.orchestrator.state import (
    TERMINAL_STATUSES,
    InvalidTransition,
    RunStatus,
    ensure_transition,
)
from app.retrieval.base import Retriever
from app.services.llm import LLMClient, LLMError


class Runner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        bus: EventBus,
        retriever: Retriever,
        llm: LLMClient,
    ):
        self._session_factory = session_factory
        self._bus = bus
        self._retriever = retriever
        self._planner = Planner(llm)
        self._researcher = Researcher(retriever, settings.RESEARCH_TOP_K)
        self._analyst = Analyst(llm)
        self._writer = Writer(llm)
        self._reviewer = Reviewer(llm)
        self._tasks: dict[str, asyncio.Task] = {}

    # ---------- 任务生命周期 ----------

    def is_busy(self) -> bool:
        return any(not task.done() for task in self._tasks.values())

    def start_planning(self, run_id: str) -> None:
        self._spawn(run_id, self._planning(run_id))

    def start_pipeline(self, run_id: str) -> None:
        self._spawn(run_id, self._pipeline(run_id))

    def cancel(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def cancel_idle(self, run_id: str) -> None:
        await self._set_status(run_id, RunStatus.CANCELLED)
        await self._bus.publish(run_id, "done", {"status": "cancelled"})

    def _spawn(self, run_id: str, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks[run_id] = task

        def _cleanup(done: asyncio.Task) -> None:
            if self._tasks.get(run_id) is done:
                self._tasks.pop(run_id, None)

        task.add_done_callback(_cleanup)

    # ---------- 阶段 ----------

    async def _planning(self, run_id: str) -> None:
        try:
            await self._set_status(run_id, RunStatus.PLANNING)
            step_id = await self._start_step(run_id, "planner")
            async with self._session_factory() as session:
                run = await session.get(Run, run_id)
                if run is None:
                    return
                topic = run.topic
                rows = (await session.execute(select(Document.filename, Document.chunk_count))).all()
            library = [{"filename": name, "chunks": count} for name, count in rows]
            result = await self._planner.plan(topic, library)
            async with self._session_factory() as session:
                for position, text in enumerate(result.sub_questions):
                    session.add(SubQuestion(run_id=run_id, position=position, text=text, origin="auto"))
                await session.commit()
            await self._finish_step(run_id, step_id, "succeeded", detail=f"生成 {len(result.sub_questions)} 个子问题")
            await self._set_status(run_id, RunStatus.AWAITING_OUTLINE)
        except asyncio.CancelledError:
            await asyncio.shield(self._mark_cancelled(run_id))
            raise
        except Exception as exc:
            await asyncio.shield(self._mark_failed(run_id, exc))

    async def _pipeline(self, run_id: str) -> None:
        try:
            async with self._session_factory() as session:
                run = await session.get(Run, run_id)
                if run is None:
                    return
                topic = run.topic
                questions = (
                    await session.execute(
                        select(SubQuestion)
                        .where(SubQuestion.run_id == run_id)
                        .order_by(SubQuestion.position)
                    )
                ).scalars().all()
                question_rows = [(q.id, q.text) for q in questions]
            if not question_rows:
                raise AgentOutputError("没有可执行的子问题")

            await self._set_status(run_id, RunStatus.RESEARCHING)
            evidence_payload: list[dict] = []
            rank = 0
            for question_id, question_text in question_rows:
                step_id = await self._start_step(run_id, "researcher")
                hits = await self._researcher.research(question_text)
                first_rank = rank + 1
                async with self._session_factory() as session:
                    for hit in hits:
                        rank += 1
                        session.add(
                            Evidence(
                                run_id=run_id,
                                sub_question_id=question_id,
                                chunk_id=hit.chunk_id,
                                filename=hit.filename,
                                page=hit.page,
                                rank=rank,
                                score=hit.score,
                                snippet=hit.snippet,
                            )
                        )
                        evidence_payload.append(
                            {
                                "rank": rank,
                                "filename": hit.filename,
                                "page": hit.page,
                                "snippet": hit.snippet,
                                "sub_question_id": question_id,
                            }
                        )
                    await session.commit()
                detail = f"命中 {len(hits)} 条证据"
                if hits:
                    detail += f"（编号 {first_rank}-{rank}）"
                await self._finish_step(run_id, step_id, "succeeded", detail=detail)

            await self._set_status(run_id, RunStatus.ANALYZING)
            all_points: list[dict] = []
            for question_id, question_text in question_rows:
                step_id = await self._start_step(run_id, "analyst")
                scoped = [item for item in evidence_payload if item["sub_question_id"] == question_id]
                result = await self._analyst.analyze(question_text, scoped)
                all_points.append(
                    {
                        "question": question_text,
                        "points": [{"text": p.text, "evidence": p.evidence} for p in result.points],
                    }
                )
                detail = f"提炼 {len(result.points)} 条要点"
                if result.out_of_range:
                    detail += f"；越界编号 {result.out_of_range}"
                await self._finish_step(run_id, step_id, "succeeded", detail=detail)

            await self._set_status(run_id, RunStatus.WRITING)
            step_id = await self._start_step(run_id, "writer")
            report = await self._writer.write(topic, all_points, evidence_payload)
            async with self._session_factory() as session:
                run = await session.get(Run, run_id)
                run.report_markdown = report
                await session.commit()
            await self._finish_step(run_id, step_id, "succeeded", detail=f"报告 {len(report)} 字符")

            await self._set_status(run_id, RunStatus.REVIEWING)
            step_id = await self._start_step(run_id, "reviewer")
            review = await self._reviewer.review(report, evidence_payload)
            async with self._session_factory() as session:
                run = await session.get(Run, run_id)
                run.review_issues = [asdict(issue) for issue in review.issues]
                await session.commit()
            await self._finish_step(
                run_id, step_id, "succeeded", detail=f"发现 {len(review.issues)} 个问题：{review.summary}"
            )

            await self._set_status(run_id, RunStatus.DONE)
            await self._bus.publish(run_id, "done", {"status": "done"})
        except asyncio.CancelledError:
            await asyncio.shield(self._mark_cancelled(run_id))
            raise
        except Exception as exc:
            await asyncio.shield(self._mark_failed(run_id, exc))

    # ---------- 状态与步骤 ----------

    async def _set_status(self, run_id: str, target: RunStatus, **fields) -> None:
        async with self._session_factory() as session:
            run = await session.get(Run, run_id)
            if run is None:
                return
            ensure_transition(RunStatus(run.status), target)
            run.status = target.value
            for key, value in fields.items():
                setattr(run, key, value)
            if target in TERMINAL_STATUSES:
                run.finished_at = utcnow()
            await session.commit()
        await self._bus.publish(
            run_id, "run", {"status": target.value, "error_code": fields.get("error_code")}
        )

    async def _start_step(self, run_id: str, agent: str) -> str:
        async with self._session_factory() as session:
            position = (
                await session.execute(select(func.count(Step.id)).where(Step.run_id == run_id))
            ).scalar_one()
            step = Step(run_id=run_id, agent=agent, position=position, status="running")
            session.add(step)
            await session.commit()
            payload = {
                "id": step.id,
                "agent": step.agent,
                "position": step.position,
                "status": step.status,
                "detail": None,
                "started_at": step.started_at.isoformat(),
                "finished_at": None,
            }
        await self._bus.publish(run_id, "step", payload)
        return payload["id"]

    async def _finish_step(
        self, run_id: str, step_id: str, status: str, detail: str | None = None, error: str | None = None
    ) -> None:
        async with self._session_factory() as session:
            step = await session.get(Step, step_id)
            step.status = status
            step.detail = detail
            step.error = error
            step.finished_at = utcnow()
            await session.commit()
            payload = {
                "id": step.id,
                "agent": step.agent,
                "position": step.position,
                "status": step.status,
                "detail": step.detail,
                "started_at": step.started_at.isoformat(),
                "finished_at": step.finished_at.isoformat(),
            }
        await self._bus.publish(run_id, "step", payload)

    async def _mark_cancelled(self, run_id: str) -> None:
        async with self._session_factory() as session:
            run = await session.get(Run, run_id)
            if run is None or RunStatus(run.status) in TERMINAL_STATUSES:
                return
            running = (
                await session.execute(
                    select(Step).where(Step.run_id == run_id, Step.status == "running")
                )
            ).scalars().all()
            for step in running:
                step.status = "skipped"
                step.finished_at = utcnow()
            run.status = RunStatus.CANCELLED.value
            run.finished_at = utcnow()
            await session.commit()
        await self._bus.publish(run_id, "run", {"status": "cancelled", "error_code": None})
        await self._bus.publish(run_id, "done", {"status": "cancelled"})

    async def _mark_failed(self, run_id: str, exc: Exception) -> None:
        code = getattr(exc, "code", None)
        if code is None:
            code = "llm_bad_json" if isinstance(exc, AgentOutputError) else "internal"
        message = str(exc)[:500]
        async with self._session_factory() as session:
            run = await session.get(Run, run_id)
            if run is None or RunStatus(run.status) in TERMINAL_STATUSES:
                return
            running = (
                await session.execute(
                    select(Step).where(Step.run_id == run_id, Step.status == "running")
                )
            ).scalars().all()
            for step in running:
                step.status = "failed"
                step.error = message
                step.finished_at = utcnow()
            run.status = RunStatus.FAILED.value
            run.error_code = code
            run.error_message = message
            run.finished_at = utcnow()
            await session.commit()
        await self._bus.publish(run_id, "run", {"status": "failed", "error_code": code})
        await self._bus.publish(run_id, "done", {"status": "failed"})
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
.\venv\Scripts\python -m pytest tests\test_orchestrator.py -v
```

预期：`4 passed`。

- [ ] **Step 5: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/backend/app/orchestrator/runner.py multi-agent-research/backend/tests/test_orchestrator.py
git commit -m "feat(multi-agent-research): 编排器阶段执行与暂停恢复"
```

---

### Task 12: API（文档与运行）

**Files:**
- Create: `multi-agent-research/backend/app/api/__init__.py`
- Create: `multi-agent-research/backend/app/api/errors.py`
- Create: `multi-agent-research/backend/app/api/documents.py`
- Create: `multi-agent-research/backend/app/api/runs.py`
- Create: `multi-agent-research/backend/app/api/router.py`
- Create: `multi-agent-research/backend/app/schemas.py`
- Create: `multi-agent-research/backend/app/main.py`
- Modify: `multi-agent-research/backend/tests/conftest.py`（追加 `client` fixture）
- Test: `multi-agent-research/backend/tests/test_api.py`

- [ ] **Step 1: 追加 client fixture**

在 `backend/tests/conftest.py` 末尾追加：

```python
from contextlib import asynccontextmanager

import httpx
import pytest_asyncio

from app.main import create_app
from app.services.llm import FakeLLM

DEFAULT_RESPONSES = {
    "ROLE=planner": '{"sub_questions": ["什么是 RAG", "BM25 如何工作"], "rationale": "先定义再方法"}',
    "ROLE=analyst": '{"points": [{"text": "RAG 结合检索与生成", "evidence": [1]}]}',
    "ROLE=writer": "# 调研报告\n\nRAG 结合检索与生成 [1]。",
    "ROLE=reviewer": '{"issues": [], "summary": "未发现问题"}',
}


def _make_app(delay: float = 0.0):
    return create_app(llm=FakeLLM(DEFAULT_RESPONSES, delay=delay))


@asynccontextmanager
async def _make_client(app):
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


@pytest_asyncio.fixture
async def client(session_factory):
    """默认 client：FakeLLM 无延迟，用于终态断言与 CRUD。"""
    async with _make_client(_make_app()) as http:
        yield http


@pytest_asyncio.fixture
async def slow_client(session_factory):
    """慢速 client：用于「执行中」守卫断言。"""
    async with _make_client(_make_app(delay=0.2)) as http:
        yield http
```

`slow_client` 给 `FakeLLM` 加 0.2s 延迟：断言「执行中」守卫的用例（busy、删除执行中的 run）必须在 run 仍处于 ACTIVE 状态时发请求；FakeLLM 瞬时完成会让 run 立刻进入 `awaiting_outline`，测试变成竞态。

- [ ] **Step 2: 写失败测试**

`backend/tests/test_api.py`：

```python
import pytest
from sqlalchemy import select

from app.models import Chunk, Document, Run


def _pdf_bytes():
    from pathlib import Path

    return (Path(__file__).parent / "fixtures" / "sample.pdf").read_bytes()


async def _upload(client, filename="guide.txt", content="RAG 是一种检索增强生成方案，把检索与大模型生成结合起来。".encode("utf-8")):
    return await client.post("/api/documents", files={"file": (filename, content)})


async def _wait_status(client, run_id, expected, tries=200):
    import asyncio

    for _ in range(tries):
        response = await client.get(f"/api/runs/{run_id}")
        if response.json()["status"] == expected:
            return response.json()
        await asyncio.sleep(0.02)
    raise AssertionError(f"run did not reach {expected}")


async def test_upload_and_list_documents(client):
    response = await _upload(client)
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "guide.txt" and body["chunk_count"] >= 1

    listing = await client.get("/api/documents")
    assert listing.status_code == 200 and len(listing.json()) == 1


async def test_upload_pdf_keeps_page(client):
    response = await _upload(client, "sample.pdf", _pdf_bytes())
    assert response.status_code == 201
    assert response.json()["chunk_count"] >= 1


async def test_upload_rejects_unsupported_extension(client):
    response = await _upload(client, "a.docx", b"x")
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "unsupported_file"


async def test_upload_rejects_empty_text(client):
    response = await _upload(client, "blank.txt", b"   \n")
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "empty_document"


async def test_delete_document(client):
    created = (await _upload(client)).json()
    response = await client.delete(f"/api/documents/{created['id']}")
    assert response.status_code == 204
    assert (await client.get("/api/documents")).json() == []
    assert (await client.delete(f"/api/documents/{created['id']}")).status_code == 404


async def test_create_run_requires_library(client):
    response = await client.post("/api/runs", json={"topic": "RAG 调研"})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "empty_library"


async def test_create_run_requires_topic(client):
    await _upload(client)
    response = await client.post("/api/runs", json={"topic": "   "})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "empty_topic"


async def test_create_run_and_reach_outline(client):
    await _upload(client)
    created = await client.post("/api/runs", json={"topic": "RAG 调研"})
    assert created.status_code == 201
    run_id = created.json()["id"]

    detail = await _wait_status(client, run_id, "awaiting_outline")
    assert [q["text"] for q in detail["sub_questions"]] == ["什么是 RAG", "BM25 如何工作"]
    assert detail["steps"][0]["agent"] == "planner"


async def test_update_outline_and_resume_to_done(client, session_factory):
    await _upload(client)
    run_id = (await client.post("/api/runs", json={"topic": "RAG 调研"})).json()["id"]
    await _wait_status(client, run_id, "awaiting_outline")

    updated = await client.put(f"/api/runs/{run_id}/outline", json={"sub_questions": ["什么是 RAG"]})
    assert updated.status_code == 200
    assert [q["text"] for q in updated.json()] == ["什么是 RAG"]

    resumed = await client.post(f"/api/runs/{run_id}/resume")
    assert resumed.status_code == 202
    detail = await _wait_status(client, run_id, "done")
    assert detail["report_markdown"].startswith("# 调研报告")
    assert detail["review_issues"] == []
    assert detail["evidence"][0]["rank"] == 1

    report = await client.get(f"/api/runs/{run_id}/report.md")
    assert report.status_code == 200
    assert report.text.startswith("# 调研报告")


async def test_resume_rejected_before_outline(client):
    await _upload(client)
    run_id = (await client.post("/api/runs", json={"topic": "RAG 调研"})).json()["id"]
    response = await client.post(f"/api/runs/{run_id}/resume")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_state"


async def test_invalid_outline_rejected(client):
    await _upload(client)
    run_id = (await client.post("/api/runs", json={"topic": "RAG 调研"})).json()["id"]
    await _wait_status(client, run_id, "awaiting_outline")
    response = await client.put(f"/api/runs/{run_id}/outline", json={"sub_questions": ["  ", ""]})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_outline"


async def test_busy_when_another_run_is_active(slow_client):
    await _upload(slow_client)
    first = await slow_client.post("/api/runs", json={"topic": "RAG 调研"})
    assert first.status_code == 201
    second = await slow_client.post("/api/runs", json={"topic": "第二个主题"})
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "busy"
    await _wait_status(slow_client, first.json()["id"], "awaiting_outline")


async def test_cancel_awaiting_outline(client):
    await _upload(client)
    run_id = (await client.post("/api/runs", json={"topic": "RAG 调研"})).json()["id"]
    await _wait_status(client, run_id, "awaiting_outline")
    response = await client.post(f"/api/runs/{run_id}/cancel")
    assert response.status_code == 202
    detail = await _wait_status(client, run_id, "cancelled")
    assert detail["status"] == "cancelled"


async def test_delete_run_rejects_active(slow_client):
    await _upload(slow_client)
    run_id = (await slow_client.post("/api/runs", json={"topic": "RAG 调研"})).json()["id"]
    await _wait_status(slow_client, run_id, "planning")
    response = await slow_client.delete(f"/api/runs/{run_id}")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_state"
    await _wait_status(slow_client, run_id, "awaiting_outline")
    assert (await slow_client.delete(f"/api/runs/{run_id}")).status_code == 204


async def test_missing_run_returns_404(client):
    response = await client.get("/api/runs/not-exist")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "run_not_found"


async def test_restart_marks_only_running_runs_interrupted(session_factory):
    from app.main import _mark_interrupted

    async with session_factory() as session:
        session.add(Run(topic="执行中", status="researching"))
        session.add(Run(topic="待确认", status="awaiting_outline"))
        await session.commit()

    await _mark_interrupted()

    async with session_factory() as session:
        runs = {row.topic: row for row in (await session.execute(select(Run))).scalars().all()}
    assert runs["执行中"].status == "failed"
    assert runs["执行中"].error_code == "interrupted"
    assert runs["待确认"].status == "awaiting_outline"
```

- [ ] **Step 3: 运行测试确认失败**

```powershell
.\venv\Scripts\python -m pytest tests\test_api.py -v
```

预期：`ModuleNotFoundError: No module named 'app.main'`。

- [ ] **Step 4: 写实现**

`backend/app/api/__init__.py`：空文件。

`backend/app/api/errors.py`：

```python
from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
```

`backend/app/schemas.py`：

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    ext: str
    size_bytes: int
    char_count: int
    chunk_count: int
    created_at: datetime


class RunCreate(BaseModel):
    topic: str


class OutlineUpdate(BaseModel):
    sub_questions: list[str] = Field(default_factory=list)


class SubQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    position: int
    text: str
    origin: str


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent: str
    position: int
    status: str
    detail: str | None
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rank: int
    filename: str
    page: int | None
    score: float
    snippet: str
    sub_question_id: str


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    topic: str
    status: str
    error_code: str | None
    created_at: datetime


class RunDetail(RunSummary):
    error_message: str | None
    report_markdown: str | None
    review_issues: list | None
    sub_questions: list[SubQuestionOut]
    steps: list[StepOut]
    evidence: list[EvidenceOut]
```

`backend/app/api/documents.py`：

```python
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import api_error
from app.config import settings
from app.database import get_db
from app.models import Document
from app.retrieval.chunker import TextChunker
from app.retrieval.ingest import IngestError, ingest_document
from app.schemas import DocumentOut

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", status_code=201, response_model=DocumentOut)
async def upload_document(file: UploadFile = File(...), session: AsyncSession = Depends(get_db)):
    if not file.filename:
        raise api_error(400, "unsupported_file", "缺少文件名")
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise api_error(400, "file_too_large", f"文件超过 {settings.MAX_UPLOAD_MB}MB")
    try:
        document = await ingest_document(
            session,
            file.filename,
            data,
            TextChunker(settings.CHUNK_SIZE, settings.CHUNK_OVERLAP),
        )
    except IngestError as exc:
        raise api_error(400, exc.code, str(exc)) from exc
    return DocumentOut.model_validate(document)


@router.get("", response_model=list[DocumentOut])
async def list_documents(session: AsyncSession = Depends(get_db)):
    rows = (
        await session.execute(select(Document).order_by(Document.created_at.desc()))
    ).scalars().all()
    return [DocumentOut.model_validate(row) for row in rows]


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: str, session: AsyncSession = Depends(get_db)):
    document = await session.get(Document, document_id)
    if document is None:
        raise api_error(404, "document_not_found", "文档不存在")
    await session.delete(document)
    await session.commit()
```

`backend/app/api/runs.py`：

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import api_error
from app.database import get_db
from app.models import Chunk, Evidence, Run, Step, SubQuestion
from app.orchestrator.runner import Runner
from app.orchestrator.state import ACTIVE_STATUSES, RunStatus
from app.schemas import (
    EvidenceOut,
    OutlineUpdate,
    RunCreate,
    RunDetail,
    RunSummary,
    StepOut,
    SubQuestionOut,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])


def get_runner(request: Request) -> Runner:
    return request.app.state.runner


def llm_ready(request: Request) -> bool:
    return bool(request.app.state.llm_ready)


async def _load_run(session: AsyncSession, run_id: str) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise api_error(404, "run_not_found", "运行不存在")
    return run


@router.post("", status_code=201, response_model=RunSummary)
async def create_run(
    payload: RunCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    runner: Runner = Depends(get_runner),
):
    topic = payload.topic.strip()
    if not topic:
        raise api_error(400, "empty_topic", "主题不能为空")
    if not llm_ready(request):
        raise api_error(500, "llm_not_configured", "未配置 DEEPSEEK_API_KEY")
    chunk_count = (await session.execute(select(func.count(Chunk.id)))).scalar_one()
    if chunk_count == 0:
        raise api_error(400, "empty_library", "资料库为空，请先上传文档")
    if runner.is_busy():
        raise api_error(409, "busy", "已有执行中的调研")
    run = Run(topic=topic, status=RunStatus.PENDING.value)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    runner.start_planning(run.id)
    return RunSummary.model_validate(run)


@router.get("", response_model=list[RunSummary])
async def list_runs(session: AsyncSession = Depends(get_db)):
    rows = (
        await session.execute(select(Run).order_by(Run.created_at.desc()))
    ).scalars().all()
    return [RunSummary.model_validate(row) for row in rows]


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, session: AsyncSession = Depends(get_db)):
    run = await _load_run(session, run_id)
    questions = (
        await session.execute(
            select(SubQuestion).where(SubQuestion.run_id == run_id).order_by(SubQuestion.position)
        )
    ).scalars().all()
    steps = (
        await session.execute(select(Step).where(Step.run_id == run_id).order_by(Step.position))
    ).scalars().all()
    evidence = (
        await session.execute(select(Evidence).where(Evidence.run_id == run_id).order_by(Evidence.rank))
    ).scalars().all()
    summary = RunSummary.model_validate(run)
    return RunDetail(
        **summary.model_dump(),
        error_message=run.error_message,
        report_markdown=run.report_markdown,
        review_issues=run.review_issues,
        sub_questions=[SubQuestionOut.model_validate(row) for row in questions],
        steps=[StepOut.model_validate(row) for row in steps],
        evidence=[EvidenceOut.model_validate(row) for row in evidence],
    )


@router.put("/{run_id}/outline", response_model=list[SubQuestionOut])
async def update_outline(
    run_id: str, payload: OutlineUpdate, session: AsyncSession = Depends(get_db)
):
    run = await _load_run(session, run_id)
    if run.status != RunStatus.AWAITING_OUTLINE.value:
        raise api_error(409, "invalid_state", "只有待确认大纲的运行可以修改")
    cleaned: list[str] = []
    for item in payload.sub_questions:
        text = item.strip()
        if text and text not in cleaned:
            cleaned.append(text)
    if not 1 <= len(cleaned) <= 8:
        raise api_error(400, "invalid_outline", "子问题数量必须在 1-8 之间")
    await session.execute(delete(SubQuestion).where(SubQuestion.run_id == run_id))
    rows = [
        SubQuestion(run_id=run_id, position=index, text=text, origin="user")
        for index, text in enumerate(cleaned)
    ]
    session.add_all(rows)
    await session.commit()
    return [SubQuestionOut.model_validate(row) for row in rows]


@router.post("/{run_id}/resume", status_code=202)
async def resume_run(
    run_id: str,
    session: AsyncSession = Depends(get_db),
    runner: Runner = Depends(get_runner),
):
    run = await _load_run(session, run_id)
    if run.status != RunStatus.AWAITING_OUTLINE.value:
        raise api_error(409, "invalid_state", "当前状态不允许继续执行")
    runner.start_pipeline(run_id)
    return {"status": RunStatus.RESEARCHING.value}


@router.post("/{run_id}/cancel", status_code=202)
async def cancel_run(
    run_id: str,
    session: AsyncSession = Depends(get_db),
    runner: Runner = Depends(get_runner),
):
    run = await _load_run(session, run_id)
    status = RunStatus(run.status)
    if status == RunStatus.AWAITING_OUTLINE:
        await runner.cancel_idle(run_id)
    elif status in ACTIVE_STATUSES:
        runner.cancel(run_id)
    else:
        raise api_error(409, "invalid_state", "当前状态不允许取消")
    return {"status": "cancelling"}


@router.delete("/{run_id}", status_code=204)
async def delete_run(
    run_id: str,
    session: AsyncSession = Depends(get_db),
    runner: Runner = Depends(get_runner),
):
    run = await _load_run(session, run_id)
    if RunStatus(run.status) in ACTIVE_STATUSES:
        raise api_error(409, "invalid_state", "执行中的调研不能删除")
    await session.delete(run)
    await session.commit()


@router.get("/{run_id}/report.md", response_class=PlainTextResponse)
async def download_report(run_id: str, session: AsyncSession = Depends(get_db)):
    run = await _load_run(session, run_id)
    if run.status != RunStatus.DONE.value or not run.report_markdown:
        raise api_error(409, "invalid_state", "报告尚未生成")
    return PlainTextResponse(
        run.report_markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="report-{run_id}.md"'},
    )
```

`backend/app/api/router.py`：

```python
from fastapi import APIRouter

from app.api import documents, runs

router = APIRouter()
router.include_router(documents.router)
router.include_router(runs.router)
```

`backend/app/main.py`：

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.api.router import router
from app.database import Base, dispose_engine, get_engine, get_sessionmaker
from app.models import Run
from app.orchestrator.events import EventBus
from app.orchestrator.runner import Runner
from app.orchestrator.state import TERMINAL_STATUSES, RunStatus
from app.retrieval.bm25 import SqlBM25Retriever
from app.services.llm import LLMClient, get_llm, llm_configured


async def _create_tables() -> None:
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _mark_interrupted() -> None:
    """重启时把“进程内执行中”的 run 置 failed；awaiting_outline 不占执行位，保持可恢复。"""
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        runs = (await session.execute(select(Run))).scalars().all()
        for run in runs:
            status = RunStatus(run.status)
            if status == RunStatus.AWAITING_OUTLINE or status in TERMINAL_STATUSES:
                continue
            run.status = RunStatus.FAILED.value
            run.error_code = "interrupted"
            run.error_message = "服务重启中断"
        await session.commit()


def create_app(llm: LLMClient | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await _create_tables()
        await _mark_interrupted()
        session_factory = get_sessionmaker()
        app.state.session_factory = session_factory
        app.state.bus = EventBus()
        app.state.llm = llm or get_llm()
        app.state.llm_ready = llm is not None or llm_configured()
        app.state.runner = Runner(
            session_factory=session_factory,
            bus=app.state.bus,
            retriever=SqlBM25Retriever(session_factory),
            llm=app.state.llm,
        )
        yield
        await dispose_engine()

    app = FastAPI(title="multi-agent-research", lifespan=lifespan)
    app.include_router(router)
    return app


app = create_app()
```

- [ ] **Step 5: 运行测试确认通过**

```powershell
.\venv\Scripts\python -m pytest tests\test_api.py -v
```

预期：`16 passed`。

- [ ] **Step 6: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/backend/app/api multi-agent-research/backend/app/schemas.py multi-agent-research/backend/app/main.py multi-agent-research/backend/tests/conftest.py multi-agent-research/backend/tests/test_api.py
git commit -m "feat(multi-agent-research): 文档与运行 API"
```

---

### Task 13: SSE 实时推送

**Files:**
- Create: `multi-agent-research/backend/app/api/events.py`
- Modify: `multi-agent-research/backend/app/api/runs.py`（抽出 `build_run_detail`）
- Modify: `multi-agent-research/backend/app/api/router.py`
- Modify: `multi-agent-research/backend/app/orchestrator/runner.py`（失败时补发 `error` 事件）
- Modify: `multi-agent-research/backend/tests/test_orchestrator.py`（补 `error` 事件用例）
- Test: `multi-agent-research/backend/tests/test_sse.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_sse.py`：

```python
import asyncio
import json

import pytest

from app.api.events import event_stream
from app.models import Run
from app.orchestrator.events import EventBus


class FakeRequest:
    """替代 Starlette Request，只提供 event_stream 需要的方法。"""

    async def is_disconnected(self) -> bool:
        return False


async def _upload(client, filename="guide.txt", content="RAG 是一种检索增强生成方案，把检索与大模型生成结合起来。".encode("utf-8")):
    return await client.post("/api/documents", files={"file": (filename, content)})


async def _wait_status(client, run_id, expected, tries=200):
    for _ in range(tries):
        response = await client.get(f"/api/runs/{run_id}")
        if response.json()["status"] == expected:
            return response.json()
        await asyncio.sleep(0.02)
    raise AssertionError(f"run did not reach {expected}")


async def _create_cancelled_run(client) -> str:
    await _upload(client)
    run_id = (await client.post("/api/runs", json={"topic": "RAG 调研"})).json()["id"]
    await _wait_status(client, run_id, "awaiting_outline")
    await client.post(f"/api/runs/{run_id}/cancel")
    await _wait_status(client, run_id, "cancelled")
    return run_id


async def _new_run(session_factory, status: str) -> str:
    async with session_factory() as session:
        run = Run(topic="RAG 调研", status=status)
        session.add(run)
        await session.commit()
        return run.id


def _snapshot_data(text: str) -> dict:
    return json.loads(text.split("data: ", 1)[1].split("\n\n", 1)[0])


async def test_events_unknown_run_returns_404(client):
    response = await client.get("/api/runs/not-exist/events")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "run_not_found"


async def test_terminal_run_streams_only_snapshot(client):
    run_id = await _create_cancelled_run(client)
    response = await client.get(f"/api/runs/{run_id}/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.count("event: ") == 1
    assert response.text.startswith("event: snapshot")


async def test_snapshot_carries_run_detail(client):
    run_id = await _create_cancelled_run(client)
    response = await client.get(f"/api/runs/{run_id}/events")
    payload = _snapshot_data(response.text)
    assert payload["status"] == "cancelled"
    assert [item["text"] for item in payload["sub_questions"]] == ["什么是 RAG", "BM25 如何工作"]
    assert payload["steps"][0]["agent"] == "planner"
    assert payload["review_issues"] is None


async def test_event_stream_forwards_bus_events(session_factory):
    run_id = await _new_run(session_factory, "researching")
    bus = EventBus()
    stream = event_stream(run_id, session_factory, bus, FakeRequest())

    assert (await stream.__anext__()).startswith("event: snapshot")

    await bus.publish(run_id, "step", {"id": "s1", "agent": "researcher", "position": 1})
    step_chunk = await stream.__anext__()
    assert step_chunk.startswith("event: step")
    assert json.loads(step_chunk.split("data: ", 1)[1].strip()) == {
        "id": "s1",
        "agent": "researcher",
        "position": 1,
    }

    await bus.publish(run_id, "done", {"status": "done"})
    assert (await stream.__anext__()).startswith("event: done")
    with pytest.raises(StopAsyncIteration):
        await stream.__anext__()


async def test_event_stream_sends_heartbeat(session_factory, monkeypatch):
    monkeypatch.setattr("app.api.events.HEARTBEAT_SECONDS", 0.01)
    run_id = await _new_run(session_factory, "researching")
    stream = event_stream(run_id, session_factory, EventBus(), FakeRequest())

    assert (await stream.__anext__()).startswith("event: snapshot")
    assert await stream.__anext__() == ": ping\n\n"
    await stream.aclose()


async def test_event_stream_unsubscribes_on_close(session_factory):
    run_id = await _new_run(session_factory, "planning")
    bus = EventBus()
    stream = event_stream(run_id, session_factory, bus, FakeRequest())

    await stream.__anext__()
    assert bus.subscriber_count(run_id) == 1
    await stream.aclose()
    assert bus.subscriber_count(run_id) == 0
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
.\venv\Scripts\python -m pytest tests\test_sse.py -v
```

预期：`ModuleNotFoundError: No module named 'app.api.events'`。

- [ ] **Step 3: 写实现**

**3.1 抽出 `build_run_detail`**

把 `backend/app/api/runs.py` 中的 `get_run` 处理函数整体替换为下面两个定义（查询逻辑不变，只是抽出公共函数，供 `events.py` 复用）：

```python
async def build_run_detail(session: AsyncSession, run: Run) -> RunDetail:
    questions = (
        await session.execute(
            select(SubQuestion).where(SubQuestion.run_id == run.id).order_by(SubQuestion.position)
        )
    ).scalars().all()
    steps = (
        await session.execute(select(Step).where(Step.run_id == run.id).order_by(Step.position))
    ).scalars().all()
    evidence = (
        await session.execute(select(Evidence).where(Evidence.run_id == run.id).order_by(Evidence.rank))
    ).scalars().all()
    summary = RunSummary.model_validate(run)
    return RunDetail(
        **summary.model_dump(),
        error_message=run.error_message,
        report_markdown=run.report_markdown,
        review_issues=run.review_issues,
        sub_questions=[SubQuestionOut.model_validate(row) for row in questions],
        steps=[StepOut.model_validate(row) for row in steps],
        evidence=[EvidenceOut.model_validate(row) for row in evidence],
    )


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, session: AsyncSession = Depends(get_db)):
    run = await _load_run(session, run_id)
    return await build_run_detail(session, run)
```

**3.2 `backend/app/api/events.py`**

```python
import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.errors import api_error
from app.api.runs import build_run_detail
from app.database import get_db
from app.models import Run
from app.orchestrator.events import EventBus
from app.orchestrator.state import ACTIVE_STATUSES, RunStatus

router = APIRouter(prefix="/api/runs", tags=["events"])

HEARTBEAT_SECONDS = 15.0


def sse_format(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def event_stream(
    run_id: str,
    session_factory: async_sessionmaker[AsyncSession],
    bus: EventBus,
    request: Request,
):
    """先订阅再取快照，避免快照查询期间的事件丢失；非执行态发完快照即结束。"""
    queue = bus.subscribe(run_id)
    try:
        async with session_factory() as session:
            run = await session.get(Run, run_id)
            if run is None:
                yield sse_format("error", {"code": "run_not_found", "message": "运行不存在"})
                return
            snapshot = (await build_run_detail(session, run)).model_dump(mode="json")
        yield sse_format("snapshot", snapshot)

        if RunStatus(snapshot["status"]) not in ACTIVE_STATUSES:
            return

        while True:
            if await request.is_disconnected():
                return
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue
            yield sse_format(event.name, event.data)
            if event.name == "done":
                return
    finally:
        bus.unsubscribe(run_id, queue)


@router.get("/{run_id}/events")
async def stream_run_events(
    run_id: str, request: Request, session: AsyncSession = Depends(get_db)
):
    run = await session.get(Run, run_id)
    if run is None:
        raise api_error(404, "run_not_found", "运行不存在")
    return StreamingResponse(
        event_stream(run_id, request.app.state.session_factory, request.app.state.bus, request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

注意：`event_stream` 内的 DB 访问一律走 `session_factory`，不能用 `Depends(get_db)` 的会话——流式响应期间依赖会话的关闭时机不受控。

**3.3 `backend/app/api/router.py`**（整体替换）

```python
from fastapi import APIRouter

from app.api import documents, events, runs

router = APIRouter()
router.include_router(documents.router)
router.include_router(runs.router)
router.include_router(events.router)
```

**3.4 `backend/app/orchestrator/runner.py`**

把 `_mark_failed` 末尾的三行发布语句改为四行（新增 `error` 事件）：

```python
        await self._bus.publish(run_id, "run", {"status": "failed", "error_code": code})
        await self._bus.publish(run_id, "error", {"code": code, "message": message})
        await self._bus.publish(run_id, "done", {"status": "failed"})
```

**3.5 在 `backend/tests/test_orchestrator.py` 末尾追加**

```python
async def test_failure_publishes_error_event(session_factory):
    run_id = await _create_run(session_factory)
    bus = EventBus()
    queue = bus.subscribe(run_id)
    runner = Runner(
        session_factory=session_factory,
        bus=bus,
        retriever=StaticRetriever({}),
        llm=FakeLLM({"ROLE=planner": "not json"}),
    )
    runner.start_planning(run_id)
    await _wait_idle(runner)

    names = []
    while not queue.empty():
        names.append(queue.get_nowait().name)
    assert names[-2:] == ["error", "done"]
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
.\venv\Scripts\python -m pytest tests\test_sse.py tests\test_orchestrator.py -v
```

预期：`test_sse.py` 6 passed、`test_orchestrator.py` 5 passed。

再跑全量：

```powershell
.\venv\Scripts\python -m pytest -q
```

预期：无失败。

- [ ] **Step 5: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/backend/app/api/events.py multi-agent-research/backend/app/api/runs.py multi-agent-research/backend/app/api/router.py multi-agent-research/backend/app/orchestrator/runner.py multi-agent-research/backend/tests/test_sse.py multi-agent-research/backend/tests/test_orchestrator.py
git commit -m "feat(multi-agent-research): SSE 快照与增量事件推送"
```

---

### Task 14: 前端骨架与资料库 / 任务列

**Files:**
- Create: `multi-agent-research/frontend/package.json`
- Create: `multi-agent-research/frontend/vite.config.ts`
- Create: `multi-agent-research/frontend/tsconfig.json`
- Create: `multi-agent-research/frontend/tsconfig.node.json`
- Create: `multi-agent-research/frontend/index.html`
- Create: `multi-agent-research/frontend/env.d.ts`
- Create: `multi-agent-research/frontend/.gitignore`
- Create: `multi-agent-research/frontend/src/main.ts`
- Create: `multi-agent-research/frontend/src/App.vue`
- Create: `multi-agent-research/frontend/src/types.ts`
- Create: `multi-agent-research/frontend/src/api.ts`
- Create: `multi-agent-research/frontend/src/status.ts`
- Create: `multi-agent-research/frontend/src/stores/documents.ts`
- Create: `multi-agent-research/frontend/src/stores/runs.ts`
- Create: `multi-agent-research/frontend/src/components/DocumentPanel.vue`
- Create: `multi-agent-research/frontend/src/components/RunListPanel.vue`
- Create: `multi-agent-research/frontend/src/styles.css`

- [ ] **Step 1: 建工程骨架**

`frontend/package.json`：

```json
{
  "name": "multi-agent-research-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build"
  },
  "dependencies": {
    "dompurify": "^3.2.4",
    "element-plus": "^2.14.7",
    "marked": "^15.0.6",
    "pinia": "^2.2.6",
    "vue": "^3.5.13"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.4",
    "typescript": "^5.6.3",
    "vite": "^5.4.11",
    "vue-tsc": "^2.2.0"
  }
}
```

`frontend/vite.config.ts`：

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5174,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } }
  }
})
```

`frontend/tsconfig.json`：

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "preserve",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "src/**/*.vue"]
}
```

`frontend/tsconfig.node.json`：

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

`frontend/index.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>多 Agent 调研工作台</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

`frontend/env.d.ts`：

```ts
/// <reference types="vite/client" />
```

`frontend/.gitignore`：

```
node_modules/
dist/
.vite/
```

- [ ] **Step 2: 写类型与 API 封装**

`frontend/src/types.ts`：

```ts
export interface DocumentItem {
  id: string
  filename: string
  ext: string
  size_bytes: number
  char_count: number
  chunk_count: number
  created_at: string
}

export interface RunSummary {
  id: string
  topic: string
  status: string
  error_code: string | null
  created_at: string
}

export interface SubQuestion {
  id: string
  position: number
  text: string
  origin: string
}

export interface StepItem {
  id: string
  agent: string
  position: number
  status: string
  detail: string | null
  error: string | null
  started_at: string
  finished_at: string | null
}

export interface EvidenceItem {
  id: string
  rank: number
  filename: string
  page: number | null
  score: number
  snippet: string
  sub_question_id: string
}

export interface ReviewIssue {
  severity: 'high' | 'medium' | 'low'
  claim: string
  problem: string
  suggestion: string
}

export interface RunDetail extends RunSummary {
  error_message: string | null
  report_markdown: string | null
  review_issues: ReviewIssue[] | null
  sub_questions: SubQuestion[]
  steps: StepItem[]
  evidence: EvidenceItem[]
}
```

`frontend/src/api.ts`：

```ts
export class ApiError extends Error {
  constructor(public readonly code: string, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, init)
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail = payload?.detail
    throw new ApiError(detail?.code ?? 'http_error', detail?.message ?? `请求失败（${response.status}）`)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}：${error.message}`
  if (error instanceof Error) return error.message
  return '未知错误'
}
```

`frontend/src/status.ts`：

```ts
export const ACTIVE_STATUSES = ['planning', 'researching', 'analyzing', 'writing', 'reviewing'] as const

const STATUS_LABELS: Record<string, string> = {
  pending: '排队中',
  planning: '拆解中',
  awaiting_outline: '待确认大纲',
  researching: '检索中',
  analyzing: '分析中',
  writing: '撰写中',
  reviewing: '核查中',
  done: '已完成',
  failed: '失败',
  cancelled: '已取消',
  running: '执行中',
  succeeded: '成功',
  skipped: '已跳过'
}

export type TagType = 'primary' | 'success' | 'warning' | 'danger' | 'info'

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status
}

export function statusTagType(status: string): TagType {
  if (status === 'awaiting_outline') return 'warning'
  if (status === 'done' || status === 'succeeded') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'cancelled' || status === 'skipped') return 'info'
  return 'primary'
}

export function isActive(status: string): boolean {
  return (ACTIVE_STATUSES as readonly string[]).includes(status)
}

export function formatTime(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

export function formatDuration(start: string, end: string | null): string {
  const from = new Date(start).getTime()
  const to = end ? new Date(end).getTime() : Date.now()
  const seconds = Math.max(0, Math.round((to - from) / 1000))
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m${seconds % 60}s`
}
```

- [ ] **Step 3: 写两个 store**

`frontend/src/stores/documents.ts`：

```ts
import { defineStore } from 'pinia'
import { api } from '../api'
import type { DocumentItem } from '../types'

export const useDocumentsStore = defineStore('documents', {
  state: () => ({
    items: [] as DocumentItem[],
    loading: false,
    uploading: false
  }),
  actions: {
    async load() {
      this.loading = true
      try {
        this.items = await api<DocumentItem[]>('/documents')
      } finally {
        this.loading = false
      }
    },
    async upload(file: File) {
      this.uploading = true
      try {
        const form = new FormData()
        form.append('file', file)
        await api<DocumentItem>('/documents', { method: 'POST', body: form })
        await this.load()
      } finally {
        this.uploading = false
      }
    },
    async remove(id: string) {
      await api<void>(`/documents/${id}`, { method: 'DELETE' })
      await this.load()
    }
  }
})
```

`frontend/src/stores/runs.ts`：

```ts
import { defineStore } from 'pinia'
import { api } from '../api'
import type { RunDetail, RunSummary } from '../types'

export const useRunsStore = defineStore('runs', {
  state: () => ({
    items: [] as RunSummary[],
    detail: null as RunDetail | null,
    selectedId: null as string | null,
    loading: false
  }),
  getters: {
    selected(state): RunDetail | null {
      return state.detail && state.detail.id === state.selectedId ? state.detail : null
    }
  },
  actions: {
    async load() {
      this.loading = true
      try {
        this.items = await api<RunSummary[]>('/runs')
      } finally {
        this.loading = false
      }
    },
    async create(topic: string) {
      const run = await api<RunSummary>('/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic })
      })
      await this.load()
      await this.select(run.id)
    },
    async select(id: string) {
      this.selectedId = id
      this.detail = null
      await this.refresh()
    },
    async refresh() {
      if (!this.selectedId) return
      this.detail = await api<RunDetail>(`/runs/${this.selectedId}`)
      this.syncSummary(this.detail)
    },
    syncSummary(detail: RunDetail) {
      const item = this.items.find((entry) => entry.id === detail.id)
      if (item) {
        item.status = detail.status
        item.error_code = detail.error_code
      }
    },
    async cancel() {
      if (!this.selectedId) return
      await api(`/runs/${this.selectedId}/cancel`, { method: 'POST' })
      await this.refresh()
      await this.load()
    },
    async remove(id: string) {
      await api<void>(`/runs/${id}`, { method: 'DELETE' })
      if (this.selectedId === id) {
        this.selectedId = null
        this.detail = null
      }
      await this.load()
    }
  }
})
```

- [ ] **Step 4: 写入口与三列骨架**

`frontend/src/main.ts`：

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import './styles.css'

createApp(App).use(createPinia()).use(ElementPlus).mount('#app')
```

`frontend/src/App.vue`（第三列先留空位，Task 15 再替换为详情面板）：

```vue
<template>
  <div class="workbench">
    <header class="workbench__header">
      <h1>多 Agent 调研工作台</h1>
      <span class="workbench__subtitle">本地资料库 · 大纲确认 · 带引用报告</span>
    </header>
    <main class="workbench__body">
      <DocumentPanel />
      <RunListPanel />
      <section class="column column--detail">
        <el-empty description="在中间栏选择或新建一个调研" />
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import DocumentPanel from './components/DocumentPanel.vue'
import RunListPanel from './components/RunListPanel.vue'
</script>
```

- [ ] **Step 5: 写左列与中列组件**

`frontend/src/components/DocumentPanel.vue`：

```vue
<template>
  <section class="column">
    <header class="column__header">
      <h2>资料库</h2>
      <span class="column__count">{{ store.items.length }} 份</span>
    </header>

    <el-upload
      :show-file-list="false"
      accept=".pdf,.txt,.md"
      :disabled="store.uploading"
      :http-request="handleUpload"
    >
      <el-button type="primary" :loading="store.uploading">上传 PDF / TXT / MD</el-button>
    </el-upload>

    <el-scrollbar class="column__scroll">
      <ul v-if="store.items.length" class="doc-list">
        <li v-for="doc in store.items" :key="doc.id" class="doc-list__item">
          <div class="doc-list__main">
            <span class="doc-list__name" :title="doc.filename">{{ doc.filename }}</span>
            <span class="doc-list__meta">{{ doc.ext.toUpperCase() }} · {{ doc.chunk_count }} 片段</span>
          </div>
          <el-popconfirm
            title="删除后该文档的片段与检索结果都会失效"
            confirm-button-text="删除"
            cancel-button-text="取消"
            @confirm="remove(doc.id)"
          >
            <template #reference>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </li>
      </ul>
      <el-empty v-else description="还没有资料，先上传 PDF / TXT / MD" :image-size="60" />
    </el-scrollbar>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadRequestOptions } from 'element-plus'
import { errorMessage } from '../api'
import { useDocumentsStore } from '../stores/documents'

const store = useDocumentsStore()

onMounted(() => {
  void store.load()
})

async function handleUpload(options: UploadRequestOptions) {
  try {
    await store.upload(options.file)
    ElMessage.success('上传成功')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function remove(id: string) {
  try {
    await store.remove(id)
    ElMessage.success('已删除')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}
</script>
```

`frontend/src/components/RunListPanel.vue`：

```vue
<template>
  <section class="column">
    <header class="column__header">
      <h2>调研任务</h2>
      <span class="column__count">{{ store.items.length }} 个</span>
    </header>

    <div class="run-create">
      <el-input
        v-model="topic"
        placeholder="输入调研主题，例如「检索增强生成的最新进展」"
        @keyup.enter="create"
      />
      <el-button
        type="primary"
        :disabled="!topic.trim()"
        :loading="creating"
        @click="create"
      >
        新建调研
      </el-button>
      <p v-if="documents.items.length === 0" class="run-create__hint">资料库为空，先上传文档再新建调研</p>
    </div>

    <el-scrollbar class="column__scroll">
      <ul v-if="store.items.length" class="run-list">
        <li
          v-for="run in store.items"
          :key="run.id"
          :class="['run-list__item', { 'run-list__item--active': run.id === store.selectedId }]"
          @click="select(run.id)"
        >
          <div class="run-list__topic">{{ run.topic }}</div>
          <div class="run-list__meta">
            <el-tag size="small" :type="statusTagType(run.status)">{{ statusLabel(run.status) }}</el-tag>
            <span>{{ formatTime(run.created_at) }}</span>
          </div>
        </li>
      </ul>
      <el-empty v-else description="还没有调研任务" :image-size="60" />
    </el-scrollbar>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { errorMessage } from '../api'
import { formatTime, statusLabel, statusTagType } from '../status'
import { useDocumentsStore } from '../stores/documents'
import { useRunsStore } from '../stores/runs'

const documents = useDocumentsStore()
const store = useRunsStore()
const topic = ref('')
const creating = ref(false)

onMounted(() => {
  void store.load()
})

async function create() {
  const value = topic.value.trim()
  if (!value) return
  creating.value = true
  try {
    await store.create(value)
    topic.value = ''
    ElMessage.success('已创建调研')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    creating.value = false
  }
}

async function select(id: string) {
  try {
    await store.select(id)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}
</script>
```

- [ ] **Step 6: 写布局样式**

`frontend/src/styles.css`：

```css
:root {
  --panel-bg: #f7f8fa;
  --border: #e4e7ed;
  --muted: #909399;
}

* {
  box-sizing: border-box;
}

html,
body,
#app {
  height: 100%;
  margin: 0;
}

body {
  font-family: 'Segoe UI', 'Microsoft YaHei', system-ui, sans-serif;
  color: #303133;
  background: #fff;
}

.workbench {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 1280px;
}

.workbench__header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
}

.workbench__header h1 {
  margin: 0;
  font-size: 18px;
}

.workbench__subtitle {
  font-size: 12px;
  color: var(--muted);
}

.workbench__body {
  display: grid;
  grid-template-columns: 320px 360px minmax(0, 1fr);
  flex: 1;
  min-height: 0;
}

.column {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  padding: 14px 16px;
  border-right: 1px solid var(--border);
  overflow: hidden;
}

.column--detail {
  padding: 0;
  border-right: none;
}

.column__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.column__header h2 {
  margin: 0;
  font-size: 15px;
}

.column__count {
  font-size: 12px;
  color: var(--muted);
}

.column__scroll {
  flex: 1;
  min-height: 0;
}

.doc-list,
.run-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.doc-list__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
}

.doc-list__item:hover {
  background: var(--panel-bg);
}

.doc-list__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.doc-list__name {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-list__meta {
  font-size: 12px;
  color: var(--muted);
}

.run-create {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.run-create__hint {
  margin: 0;
  font-size: 12px;
  color: #e6a23c;
}

.run-list__item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
}

.run-list__item:hover {
  background: var(--panel-bg);
}

.run-list__item--active {
  border-color: #409eff;
  background: #ecf5ff;
}

.run-list__topic {
  font-size: 13px;
  line-height: 1.4;
}

.run-list__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--muted);
}
```

- [ ] **Step 7: 安装依赖并构建**

```powershell
cd multi-agent-research/frontend
npm install
npm run build
```

预期：`vue-tsc --noEmit` 无类型错误，`vite build` 在 `frontend/dist/` 下产物成功。

- [ ] **Step 8: 手动冒烟（左列 + 中列）**

后端：

```powershell
cd multi-agent-research/backend
.\venv\Scripts\python -m uvicorn app.main:app --port 8000
```

前端：

```powershell
cd multi-agent-research/frontend
npm run dev
```

打开 `http://localhost:5174`，按顺序验证：

1. 上传一个 `.txt`，左列出现文件名与片段数。
2. 上传一个 `.docx`，弹出 `unsupported_file：...` 提示，列表不变。
3. 中列输入主题并回车，任务出现在列表，状态标签从「拆解中」变为「待确认大纲」（未配置 `DEEPSEEK_API_KEY` 时应提示 `llm_not_configured：未配置 DEEPSEEK_API_KEY`，此时后端会返回 500，属预期）。
4. 点击任务条目，中列高亮选中。

- [ ] **Step 9: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/frontend/package.json multi-agent-research/frontend/package-lock.json multi-agent-research/frontend/vite.config.ts multi-agent-research/frontend/tsconfig.json multi-agent-research/frontend/tsconfig.node.json multi-agent-research/frontend/index.html multi-agent-research/frontend/env.d.ts multi-agent-research/frontend/.gitignore multi-agent-research/frontend/src
git commit -m "feat(multi-agent-research): 前端骨架与资料库/任务列"
```

---

### Task 15: 详情面板与 SSE 联动

**Files:**
- Create: `multi-agent-research/frontend/src/components/RunDetailPanel.vue`
- Modify: `multi-agent-research/frontend/src/stores/runs.ts`（SSE 生命周期、大纲保存、恢复）
- Modify: `multi-agent-research/frontend/src/App.vue`
- Modify: `multi-agent-research/frontend/src/styles.css`（追加详情样式）

- [ ] **Step 1: 扩展 runs store**

`backend` 侧无需改动；本步把 `frontend/src/stores/runs.ts` 整体替换为下面内容（新增 SSE 与大纲/恢复动作）：

```ts
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { isActive } from '../status'
import type { RunDetail, RunSummary, StepItem, SubQuestion } from '../types'

let source: EventSource | null = null

function closeSource() {
  source?.close()
  source = null
}

interface StatusEvent {
  status: string
  error_code: string | null
}

export const useRunsStore = defineStore('runs', {
  state: () => ({
    items: [] as RunSummary[],
    detail: null as RunDetail | null,
    selectedId: null as string | null,
    loading: false
  }),
  getters: {
    selected(state): RunDetail | null {
      return state.detail && state.detail.id === state.selectedId ? state.detail : null
    }
  },
  actions: {
    async load() {
      this.loading = true
      try {
        this.items = await api<RunSummary[]>('/runs')
      } finally {
        this.loading = false
      }
    },
    async create(topic: string) {
      const run = await api<RunSummary>('/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic })
      })
      await this.load()
      await this.select(run.id)
    },
    async select(id: string) {
      if (this.selectedId === id) {
        await this.refresh()
        return
      }
      this.selectedId = id
      this.detail = null
      closeSource()
      await this.refresh()
      this.connect()
    },
    async refresh() {
      if (!this.selectedId) return
      const detail = await api<RunDetail>(`/runs/${this.selectedId}`)
      this.detail = detail
      this.syncSummary(detail)
    },
    syncSummary(detail: RunDetail) {
      const item = this.items.find((entry) => entry.id === detail.id)
      if (item) {
        item.status = detail.status
        item.error_code = detail.error_code
      }
    },
    applyStatus(status: string, errorCode: string | null | undefined) {
      const item = this.items.find((entry) => entry.id === this.selectedId)
      if (item) {
        item.status = status
        item.error_code = errorCode ?? null
      }
      if (this.detail && this.detail.id === this.selectedId) {
        this.detail.status = status
        this.detail.error_code = errorCode ?? this.detail.error_code
      }
    },
    connect() {
      closeSource()
      const runId = this.selectedId
      if (!runId) return
      const events = new EventSource(`/api/runs/${runId}/events`)
      source = events

      events.addEventListener('snapshot', (event) => {
        if (this.selectedId !== runId) return
        const payload = JSON.parse((event as MessageEvent).data) as RunDetail
        this.detail = payload
        this.syncSummary(payload)
        if (!isActive(payload.status)) events.close()
      })

      events.addEventListener('run', (event) => {
        if (this.selectedId !== runId) return
        const payload = JSON.parse((event as MessageEvent).data) as StatusEvent
        this.applyStatus(payload.status, payload.error_code)
        if (!isActive(payload.status)) void this.refresh()
      })

      events.addEventListener('step', (event) => {
        if (this.selectedId !== runId || !this.detail) return
        const step = JSON.parse((event as MessageEvent).data) as StepItem
        const index = this.detail.steps.findIndex((entry) => entry.id === step.id)
        if (index >= 0) this.detail.steps[index] = step
        else this.detail.steps.push(step)
      })

      // 名为 error 的业务事件与 EventSource 原生连接错误共用同一个事件名：
      // 原生错误没有 data，直接返回，交给浏览器自动重连。
      events.addEventListener('error', (event) => {
        const data = (event as MessageEvent).data
        if (!data) return
        const payload = JSON.parse(data) as { code: string; message: string }
        ElMessage.error(`${payload.code}：${payload.message}`)
      })

      events.addEventListener('done', (event) => {
        const payload = JSON.parse((event as MessageEvent).data) as StatusEvent
        this.applyStatus(payload.status, payload.error_code)
        events.close()
        if (this.selectedId === runId) void this.refresh()
      })
    },
    disconnect() {
      closeSource()
    },
    async saveOutline(texts: string[]) {
      if (!this.selectedId) return
      await api<SubQuestion[]>(`/runs/${this.selectedId}/outline`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sub_questions: texts })
      })
      await this.refresh()
    },
    async resume() {
      if (!this.selectedId) return
      await api(`/runs/${this.selectedId}/resume`, { method: 'POST' })
      await this.refresh()
      this.connect()
    },
    async cancel() {
      if (!this.selectedId) return
      await api(`/runs/${this.selectedId}/cancel`, { method: 'POST' })
      await this.refresh()
      await this.load()
    },
    async remove(id: string) {
      await api<void>(`/runs/${id}`, { method: 'DELETE' })
      if (this.selectedId === id) {
        closeSource()
        this.selectedId = null
        this.detail = null
      }
      await this.load()
    }
  }
})
```

- [ ] **Step 2: 接入详情面板**

`frontend/src/App.vue` 整体替换：

```vue
<template>
  <div class="workbench">
    <header class="workbench__header">
      <h1>多 Agent 调研工作台</h1>
      <span class="workbench__subtitle">本地资料库 · 大纲确认 · 带引用报告</span>
    </header>
    <main class="workbench__body">
      <DocumentPanel />
      <RunListPanel />
      <RunDetailPanel />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount } from 'vue'
import DocumentPanel from './components/DocumentPanel.vue'
import RunListPanel from './components/RunListPanel.vue'
import RunDetailPanel from './components/RunDetailPanel.vue'
import { useRunsStore } from './stores/runs'

const runs = useRunsStore()

onBeforeUnmount(() => {
  runs.disconnect()
})
</script>
```

- [ ] **Step 3: 写详情面板**

`frontend/src/components/RunDetailPanel.vue`：

```vue
<template>
  <section class="column column--detail">
    <el-empty v-if="!store.selectedId" description="在中间栏选择或新建一个调研" />
    <el-skeleton v-else-if="!detail" :rows="8" animated style="padding: 20px" />
    <template v-else>
      <header class="detail__header">
        <div class="detail__titles">
          <h2>{{ detail.topic }}</h2>
          <p class="detail__meta">
            <el-tag size="small" :type="statusTagType(detail.status)">{{ statusLabel(detail.status) }}</el-tag>
            <span>创建于 {{ formatTime(detail.created_at) }}</span>
          </p>
        </div>
        <div class="detail__actions">
          <el-button v-if="isActive(detail.status)" type="danger" plain @click="cancel">取消</el-button>
          <el-button v-if="detail.status === 'failed'" @click="retry">以同主题新建</el-button>
          <el-popconfirm
            v-if="!isActive(detail.status)"
            title="删除后该调研的步骤、证据与报告都会丢失"
            confirm-button-text="删除"
            cancel-button-text="取消"
            @confirm="removeRun"
          >
            <template #reference>
              <el-button type="danger" link>删除</el-button>
            </template>
          </el-popconfirm>
          <a v-if="detail.status === 'done'" :href="reportUrl" download>
            <el-button type="primary">下载 .md</el-button>
          </a>
        </div>
      </header>

      <el-alert
        v-if="detail.status === 'failed'"
        class="detail__alert"
        type="error"
        :closable="false"
        show-icon
        :title="`${detail.error_code ?? 'failed'}：${detail.error_message ?? '执行失败'}`"
      />

      <el-scrollbar class="detail__scroll">
        <div class="detail__body">
          <section v-if="detail.status === 'awaiting_outline'" class="detail__block">
            <h3>子问题大纲（{{ outline.length }} / 8）</h3>
            <ul class="outline">
              <li v-for="(item, index) in outline" :key="index" class="outline__row">
                <span class="outline__index">{{ index + 1 }}</span>
                <el-input v-model="outline[index]" maxlength="200" />
                <el-button link :disabled="index === 0" @click="move(index, -1)">上移</el-button>
                <el-button link :disabled="index === outline.length - 1" @click="move(index, 1)">下移</el-button>
                <el-button link type="danger" @click="removeRow(index)">删除</el-button>
              </li>
            </ul>
            <div class="outline__actions">
              <el-button :disabled="outline.length >= 8" @click="addRow">添加子问题</el-button>
              <el-button type="primary" :loading="saving" :disabled="!canSubmit" @click="save">保存大纲</el-button>
              <el-button type="success" :loading="resuming" :disabled="!canSubmit" @click="saveAndResume">
                保存并继续执行
              </el-button>
            </div>
          </section>

          <section class="detail__block">
            <h3>执行轨迹</h3>
            <el-timeline v-if="detail.steps.length">
              <el-timeline-item
                v-for="step in detail.steps"
                :key="step.id"
                :timestamp="formatTime(step.started_at)"
                :type="statusTagType(step.status)"
                :hollow="step.status === 'running'"
              >
                <div class="step">
                  <strong>{{ AGENT_LABELS[step.agent] ?? step.agent }}</strong>
                  <el-tag size="small" :type="statusTagType(step.status)">{{ statusLabel(step.status) }}</el-tag>
                  <span class="step__time">{{ formatDuration(step.started_at, step.finished_at) }}</span>
                </div>
                <p v-if="step.detail" class="step__detail">{{ step.detail }}</p>
                <p v-if="step.error" class="step__error">{{ step.error }}</p>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="还没有执行记录" :image-size="60" />
          </section>

          <section v-if="detail.report_markdown" class="detail__block">
            <h3>调研报告</h3>
            <div class="report" v-html="reportHtml" />
          </section>

          <section v-if="detail.evidence.length" class="detail__block">
            <h3>证据（{{ detail.evidence.length }} 条）</h3>
            <el-table :data="detail.evidence" size="small" border>
              <el-table-column prop="rank" label="#" width="56" />
              <el-table-column prop="filename" label="文档" min-width="160" show-overflow-tooltip />
              <el-table-column label="页码" width="72">
                <template #default="{ row }">{{ row.page ?? '—' }}</template>
              </el-table-column>
              <el-table-column label="分数" width="88">
                <template #default="{ row }">{{ row.score.toFixed(3) }}</template>
              </el-table-column>
              <el-table-column prop="snippet" label="摘要" min-width="240" show-overflow-tooltip />
            </el-table>
          </section>

          <section v-if="detail.status === 'done'" class="detail__block">
            <h3>审阅问题（{{ (detail.review_issues ?? []).length }}）</h3>
            <template v-if="(detail.review_issues ?? []).length">
              <el-alert
                v-for="(issue, index) in detail.review_issues ?? []"
                :key="index"
                class="review"
                :type="severityType(issue.severity)"
                :closable="false"
                :title="issue.claim"
                :description="`${issue.problem}｜建议：${issue.suggestion}`"
              />
            </template>
            <p v-else class="review__empty">未发现问题</p>
          </section>
        </div>
      </el-scrollbar>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { errorMessage } from '../api'
import { formatDuration, formatTime, isActive, statusLabel, statusTagType } from '../status'
import { useRunsStore } from '../stores/runs'
import type { ReviewIssue } from '../types'

const AGENT_LABELS: Record<string, string> = {
  planner: 'Planner · 拆解',
  researcher: 'Researcher · 检索',
  analyst: 'Analyst · 分析',
  writer: 'Writer · 撰写',
  reviewer: 'Reviewer · 核查'
}

const store = useRunsStore()
const detail = computed(() => store.selected)
const outline = ref<string[]>([])
const saving = ref(false)
const resuming = ref(false)

const canSubmit = computed(
  () => outline.value.length > 0 && outline.value.every((item) => item.trim().length > 0)
)
const reportUrl = computed(() => `/api/runs/${store.selectedId ?? ''}/report.md`)
const reportHtml = computed(() =>
  DOMPurify.sanitize(marked.parse(detail.value?.report_markdown ?? '') as string)
)

watch(
  () => [store.selectedId, detail.value?.status] as const,
  () => {
    outline.value =
      detail.value?.status === 'awaiting_outline'
        ? detail.value.sub_questions.map((item) => item.text)
        : []
  },
  { immediate: true }
)

function addRow() {
  if (outline.value.length >= 8) return
  outline.value.push('')
}

function removeRow(index: number) {
  outline.value.splice(index, 1)
}

function move(index: number, delta: number) {
  const target = index + delta
  if (target < 0 || target >= outline.value.length) return
  const [item] = outline.value.splice(index, 1)
  outline.value.splice(target, 0, item)
}

async function save() {
  saving.value = true
  try {
    await store.saveOutline(outline.value.map((item) => item.trim()))
    ElMessage.success('大纲已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

async function saveAndResume() {
  resuming.value = true
  try {
    await store.saveOutline(outline.value.map((item) => item.trim()))
    await store.resume()
    ElMessage.success('已开始执行')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    resuming.value = false
  }
}

async function cancel() {
  try {
    await store.cancel()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function retry() {
  if (!detail.value) return
  try {
    await store.create(detail.value.topic)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function removeRun() {
  if (!detail.value) return
  try {
    await store.remove(detail.value.id)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function severityType(severity: ReviewIssue['severity']): 'error' | 'warning' | 'info' {
  if (severity === 'high') return 'error'
  if (severity === 'medium') return 'warning'
  return 'info'
}
</script>
```

- [ ] **Step 4: 追加详情样式**

在 `frontend/src/styles.css` 末尾追加：

```css
.detail__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
}

.detail__titles h2 {
  margin: 0 0 6px;
  font-size: 16px;
}

.detail__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}

.detail__actions {
  display: flex;
  gap: 8px;
}

.detail__alert {
  margin: 12px 20px 0;
}

.detail__scroll {
  flex: 1;
  min-height: 0;
}

.detail__body {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 16px 20px 32px;
}

.detail__block h3 {
  margin: 0 0 10px;
  font-size: 14px;
}

.outline {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.outline__row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.outline__index {
  width: 20px;
  font-size: 12px;
  color: var(--muted);
  text-align: right;
}

.outline__actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.step__time {
  font-size: 12px;
  color: var(--muted);
}

.step__detail {
  margin: 4px 0 0;
  font-size: 12px;
  color: #606266;
}

.step__error {
  margin: 4px 0 0;
  font-size: 12px;
  color: #f56c6c;
}

.report {
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.75;
}

.report h1,
.report h2,
.report h3 {
  margin: 16px 0 8px;
}

.report h1:first-child {
  margin-top: 0;
}

.report p {
  margin: 8px 0;
}

.report code {
  padding: 1px 4px;
  background: var(--panel-bg);
  border-radius: 3px;
}

.report blockquote {
  margin: 8px 0;
  padding-left: 12px;
  border-left: 2px solid var(--border);
  color: #606266;
}

.review {
  margin-bottom: 8px;
}

.review__empty {
  margin: 0;
  font-size: 13px;
  color: #67c23a;
}
```

- [ ] **Step 5: 构建验证**

```powershell
cd multi-agent-research/frontend
npm run build
```

预期：无类型错误，`dist/` 生成成功。

- [ ] **Step 6: 手动冒烟（全链路）**

前后端均启动（同 Task 14 Step 8），并在 `multi-agent-research/backend/.env` 配置真实 `DEEPSEEK_API_KEY`：

1. 上传 2–3 份相关 `.txt`/`.md`。
2. 新建主题 → 右列出现大纲编辑区，可增删改与上下移。
3. 点「保存并继续执行」→ 时间线依次出现 Researcher / Analyst / Writer / Reviewer，状态标签随 SSE 变化，无需刷新。
4. 完成后右列出现报告 Markdown 预览、证据表格（编号 1..M）与审阅问题清单；点「下载 .md」能拿到文件。
5. 新建第二个主题并在执行中点「取消」→ 状态变「已取消」，时间线当前步为「已跳过」。
6. 执行中刷新页面 → 重进详情能拉回已完成的 steps（快照重建）。

- [ ] **Step 7: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/frontend/src/components/RunDetailPanel.vue multi-agent-research/frontend/src/stores/runs.ts multi-agent-research/frontend/src/App.vue multi-agent-research/frontend/src/styles.css
git commit -m "feat(multi-agent-research): 三列详情面板与 SSE 联动"
```

---

### Task 16: 文档、索引与交付收尾

**Files:**
- Create: `multi-agent-research/README.md`
- Modify: `README.md`（根：总览表、第 11 节、目录树、学习路径）
- Modify: `.qoder/docs/README.md`（确认实施计划已登记）

- [ ] **Step 1: 写子项目 README**

`multi-agent-research/README.md`：

```markdown
# multi-agent-research

> 本地资料库驱动的多 Agent 调研报告系统：Planner 拆解 → 人工确认大纲 → 检索 / 分析 / 写作 / 核查 → 带引用 Markdown 报告，全过程 SSE 实时推送。

## 核心能力

- **五个固定角色**：Planner 动态拆解 1–8 个子问题，Researcher / Analyst / Writer / Reviewer 顺序执行，每步落库可审计
- **唯一人工暂停点**：`awaiting_outline` 可改子问题（增删改、上下移）后再恢复，其余状态全自动
- **可恢复状态机**：自研 `pending → planning → awaiting_outline → researching → analyzing → writing → reviewing → done`；重启把非终态置 `failed`（`interrupted`）
- **离线可测的检索**：中文 2-gram + BM25（k1=1.5, b=0.75），Top-5，同分按 chunk id 稳定排序
- **可溯源报告**：run 内证据全局编号 1..M，Writer 只允许 `[n]` 引用，Reviewer 检出越界引用与无据断言
- **实时轨迹**：SSE 推 `snapshot` / `run` / `step` / `error` / `done`，15s 心跳，非执行态仅发快照

## 目录结构

```
multi-agent-research/
├── backend/     # FastAPI + SQLAlchemy async + SQLite + BM25 + DeepSeek
│   ├── app/
│   │   ├── agents/        # planner / researcher / analyst / writer / reviewer
│   │   ├── api/           # documents / runs / events(SSE)
│   │   ├── orchestrator/  # 状态机、事件总线、Runner
│   │   ├── retrieval/     # chunker / tokenizer / bm25 / ingest
│   │   └── services/      # LLMClient / DeepSeekClient / FakeLLM
│   └── tests/             # pytest，全程离线
└── frontend/    # Vue 3 + TS + Vite + Element Plus + Pinia（三列工作台）
```

## 启动

后端：

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # 填入 DEEPSEEK_API_KEY
.\venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

前端（另一个终端）：

```powershell
cd frontend
npm install
npm run dev   # http://localhost:5174，/api 代理到 127.0.0.1:8000
```

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 空 | 未配置时创建 run 返回 500 `llm_not_configured` |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容端点 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名 |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 800 / 100 | 滑窗切分口径 |
| `RESEARCH_TOP_K` | 5 | 每个子问题检索条数 |
| `MAX_UPLOAD_MB` | 20 | 上传上限 |
| `LLM_TIMEOUT` | 120 | 单次调用超时（秒） |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/app.db` | 数据库地址 |

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/documents` | 上传 PDF / TXT / MD |
| GET / DELETE | `/api/documents`、`/api/documents/{id}` | 列表 / 删除 |
| POST / GET | `/api/runs` | 新建 / 列表 |
| GET / DELETE | `/api/runs/{id}` | 详情 / 删除（非执行态） |
| PUT | `/api/runs/{id}/outline` | 仅 `awaiting_outline` |
| POST | `/api/runs/{id}/resume` | 仅 `awaiting_outline`，202 |
| POST | `/api/runs/{id}/cancel` | 执行态与 `awaiting_outline` |
| GET | `/api/runs/{id}/report.md` | 仅 `done`，下载 Markdown |
| GET | `/api/runs/{id}/events` | SSE 轨迹 |

错误统一返回 `{"detail": {"code": "...", "message": "..."}}`。

## 测试

```powershell
cd backend
.\venv\Scripts\python -m pytest -q   # 全部离线，FakeLLM 按角色返回固定输出
```

## 已知限制

- 全局单执行位，同一时刻只能跑一个调研
- 检索为纯关键词（BM25），无向量 / 语义改写
- 前端不做移动端适配（≥1280px 三列固定布局）
- `failed` / `cancelled` 为终态，只能同主题新建 run
```

- [ ] **Step 2: 更新根 README**

**2.1 总览表**：在 `| [local-pdf-rag](#10-local-pdf-rag) | ... |` 一行下方插入：

```markdown
| [multi-agent-research](#11-multi-agent-research) | 多 Agent 调研报告编排 | 自研状态机 + 大纲人工确认 + BM25 检索 + SSE 轨迹 |
```

**2.2 新增章节**：在 `## 10. local-pdf-rag` 小节结束的 `---` 之后、`## 快速开始` 之前插入：

```markdown
## 11. multi-agent-research

> 本地资料库驱动的多 Agent 调研报告系统：Planner 拆解子问题 → 人工确认大纲 → 检索/分析/写作/核查四阶段执行 → 带引用 Markdown 报告，全过程 SSE 实时推送。

**核心能力：**
- **五个固定角色**：Planner 输出 1–8 个子问题，Researcher 逐题 BM25 检索，Analyst 提炼带证据编号的要点，Writer 产出带 `[n]` 引用的报告，Reviewer 核查引用与断言
- **唯一人工暂停点**：`awaiting_outline` 状态下可增删改子问题再恢复，其余阶段全自动
- **可恢复状态机**：十个状态 + 转移守卫，全局单执行位，重启把未完成的 run 置 `failed(interrupted)`，刷新页面靠快照重建
- **离线可测检索**：中文 2-gram 分词 + BM25，零外部依赖，测试不触网
- **可溯源报告**：run 内证据全局编号 1..M，下载 Markdown 并附证据表（文档 / 页码 / 分数 / 摘要）

```
multi-agent-research/
├── backend/     # FastAPI + SQLAlchemy async + SQLite + BM25 + DeepSeek
└── frontend/    # Vue 3 + Element Plus 三列工作台（资料库 / 任务 / 详情）
```
```

**2.3 项目架构树**：在 `local-pdf-rag/` 两行之后插入：

```markdown
├── multi-agent-research/    # ⑪ 多 Agent 调研报告编排
│   ├── backend/             #   自研状态机 + BM25 检索 + DeepSeek + SSE
│   └── frontend/            #   Vue 3 + Element Plus 三列工作台
```

**2.4 学习路径**：在 `10. **local-pdf-rag**：...` 一行之后追加：

```markdown
11. **multi-agent-research**：把单链 RAG 拆成多角色协作，掌握状态机编排、人工暂停点、证据编号与 SSE 轨迹推送
```

- [ ] **Step 3: 确认文档索引**

打开 `.qoder/docs/README.md`，确认已有 `multi-agent-research` 两行（设计说明与实施计划）。若实施计划一行缺失，按现有表格格式补上：

```markdown
| multi-agent-research | [实施计划](./multi-agent-research-实施计划.md) | 16 个 TDD 任务：骨架/配置 → 六表 → 切分分词 → BM25 → 入库 → LLM 客户端 → 五个 Agent → 状态机 → Runner → API → SSE → 前端三列 → 文档收尾 |
```

- [ ] **Step 4: 终检**

```powershell
cd multi-agent-research/backend
.\venv\Scripts\python -m pytest -q

cd ..\frontend
npm run build

cd D:\StudyProjects\ai-practice
git status --short
```

预期：后端全绿；前端构建成功；`git status` 只剩本次文档改动，无 `data/`、`.env`、`venv/`、`node_modules/`、`dist/`。

- [ ] **Step 5: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add multi-agent-research/README.md README.md .qoder/docs/README.md
git commit -m "docs(multi-agent-research): 项目说明与索引"
```

---

## 验收清单

设计说明与任务的对应关系（实现完毕后逐项打勾）：

| 设计章节 | 任务 |
| --- | --- |
| 2. 范围边界 | Task 4（无向量）、Task 6（单一提供方）、Task 11（单执行位） |
| 4–5. 目录与配置 | Task 1、Task 14 |
| 6. 数据模型与状态机 | Task 2、Task 10 |
| 7. 切分 / 分词 / BM25 / 证据编号 | Task 3、Task 4、Task 5、Task 11 |
| 8. Prompt 契约与 JSON 重试 | Task 6、Task 7、Task 8、Task 9 |
| 9. API 与 SSE | Task 12、Task 13 |
| 10. 前端交互 | Task 14、Task 15 |
| 11. 错误码与守卫 | Task 5、Task 6、Task 11、Task 12 |
| 12. 测试策略 | Task 1–13 的每步 pytest |
| 交付物 | Task 16 |

**已知取舍（实现时不要擅自扩展）：** 不做认证、不做多 run 并发、不做向量检索、不做多节点审批、不做前端 E2E。

