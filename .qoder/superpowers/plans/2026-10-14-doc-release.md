# 释文 DocRelease 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `demo-app.html` 的交互演示实现为真实全栈系统：读取本地 git 仓库变更（内置示例仓 + 任意仓），经 5 步流水线（定位范围 → 收集变更 → tree-sitter AST 解析 → 星语 LLM 业务化改写 → 产物生成归档），通过 SSE 实时推送进度，产出功能点清单 CSV / 产品文档 MD / 溯源文件 JSON 三类产物，前端复刻 demo 的三栏工作台并新增发布历史页。

**Architecture:** FastAPI 后端（异步 SQLAlchemy + SQLite）+ Vue 3 前端。运行以 asyncio 后台任务执行，进程内 RunEventBus 广播事件，SSE 端点推送；LLM 输出结构化 JSON（业务/技术双写），三类产物由确定性渲染器从同一结构化结果生成（预览前端渲染、导出与归档走后端渲染器，内容同源）。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy 2.0 Async · SQLite(aiosqlite) · tree-sitter + tree-sitter-language-pack · requests（星语网关）· pytest + pytest-asyncio + httpx ｜ Vue 3 + TypeScript + Vite + Pinia + Vue Router + Element Plus + Axios

**规格文档:** `docs/superpowers/specs/2026-10-14-doc-release-design.md`（实现中如遇歧义，以规格为准）

**依赖版本基线（沿用工作区已验证版本）:**
- 后端 `requirements.txt`: fastapi==0.141.1 · uvicorn==0.52.4 · httpx==0.28.1 · requests==2.34.2 · pydantic-settings==2.15.0 · pytest==9.1.1 · pytest-asyncio==1.3.0 · sqlalchemy[asyncio]==2.0.40 · aiosqlite==0.21.0 · tree-sitter==0.26.0 · tree-sitter-language-pack==1.22.1
- 前端 `package.json` 关键版本: vue ^3.5.13 · element-plus ^2.9.7 · pinia ^3.0.1 · vue-router ^4.5.0 · axios ^1.8.4 · vite ^6.2.4 · typescript ~5.7.3 · vue-tsc ^2.2.8 · @vitejs/plugin-vue ^5.2.3

**全局约定（每一步都适用）:**
- 工作目录 `D:\StudyProjects\ai-practice`；后端命令一律在 `doc-release/backend` 下用 venv 执行（`.\venv\Scripts\python.exe -m pytest ...`），前端命令在 `doc-release/frontend` 下执行
- PowerShell 不支持 `&&` 作语句分隔符，命令链用 `;`
- `git commit -m` 的消息一律用**单引号**包裹（含括号时双引号会被 PowerShell 剥离导致命令替换错误）
- 提交前用 `git status --short`（不带路径过滤）核对完整暂存区，提交后用 `git show --stat HEAD` 复核
- 后端测试全程不打真实星语（conftest 全局打桩），保持离线可跑

---

## 文件结构地图（先锁定边界，再实施）

```
doc-release/
├── backend/
│   ├── app/
│   │   ├── __init__.py                  # 空包标记
│   │   ├── config.py                    # Settings（显式 env_file）+ 单例 settings
│   │   ├── database.py                  # Base / engine / AsyncSessionLocal / get_db
│   │   ├── main.py                      # FastAPI 装配、lifespan（建表+种子自检）、CORS、日志中间件、路由注册
│   │   ├── models/                      # repo.py / run.py / artifact.py / __init__.py
│   │   ├── schemas/                     # repo.py / run.py（请求体与响应体）
│   │   ├── api/                         # meta.py / repos.py / runs.py / __init__.py
│   │   ├── prompts/
│   │   │   ├── __init__.py
│   │   │   └── docrelease_v1.py         # SYSTEM_PROMPT_TEMPLATE / PROMPT_VERSION
│   │   ├── glossary.json                # 内置术语表（20+ 条）
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── errors.py                # ServiceError / GitError / RunCancelled
│   │       ├── git_service.py           # git CLI 封装（只读）
│   │       ├── parser_service.py        # tree-sitter 符号解析与契约信号
│   │       ├── glossary.py              # 术语表加载与命中匹配
│   │       ├── xingyu_api.py            # 星语网关同步封装
│   │       ├── llm_service.py           # provider 路由 / 分块 / JSON 修复 / 合并降级
│   │       ├── renderers.py             # 三类产物确定性渲染（纯函数）
│   │       ├── archive_service.py       # 归档写入与删除保护
│   │       └── pipeline_service.py      # 五步编排 / 状态机 / RunEventBus / 取消
│   ├── tests/
│   │   ├── conftest.py                  # 测试引擎/会话/客户端 fixture + LLM 全局打桩 + pipeline 注入
│   │   ├── gitfix.py                    # 真实 git 仓库测试助手（init/write/commit/tag）
│   │   ├── test_health.py
│   │   ├── test_models.py
│   │   ├── test_git_service.py
│   │   ├── test_seed_data.py
│   │   ├── test_seed_sample_repo.py
│   │   ├── test_parser_service.py
│   │   ├── test_glossary.py
│   │   ├── test_llm_service.py
│   │   ├── test_renderers.py
│   │   ├── test_pipeline.py
│   │   ├── test_api_repos.py
│   │   └── test_api_runs.py
│   ├── seed_data.py                     # 示例仓库的提交序列与文件内容（纯数据）
│   ├── seed_sample_repo.py              # 用 git CLI 生成示例仓库（幂等）
│   ├── e2e_smoke.py                     # 进程内起服务 + 打桩 LLM 的端到端冒烟
│   ├── requirements.txt / pytest.ini / .env.example / .gitignore / README.md
│   ├── sample_repo/                     # 由种子脚本生成（gitignore）
│   └── archive/                         # 产物归档（gitignore）
└── frontend/
    ├── src/
    │   ├── main.ts / App.vue / env.d.ts
    │   ├── api/client.ts / sse.ts
    │   ├── stores/repo.ts / run.ts
    │   ├── router/index.ts
    │   ├── types/index.ts
    │   ├── data/steps.ts                # 五步静态说明（读/写/失败）
    │   ├── styles/theme.css             # 复刻 demo 设计语言
    │   ├── views/ConsoleView.vue / HistoryView.vue / HistoryDetailView.vue
    │   └── components/TopBar.vue / ControlBar.vue / DiffPanel.vue / PipelinePanel.vue
    │                   / StepList.vue / TerminalLog.vue / OutputPanel.vue
    │                   / ChecklistView.vue / DocView.vue / TraceView.vue
    │                   / StatusBadge.vue / RunTable.vue
    ├── index.html / vite.config.ts / tsconfig.json / tsconfig.app.json / tsconfig.node.json
    ├── package.json / .gitignore / README.md
```

---

## Task 1: 后端骨架与测试基建

**Files:**
- Create: `doc-release/backend/requirements.txt`
- Create: `doc-release/backend/pytest.ini`
- Create: `doc-release/backend/.env.example`
- Create: `doc-release/backend/.gitignore`
- Create: `doc-release/backend/app/__init__.py`（空文件）
- Create: `doc-release/backend/app/config.py`
- Create: `doc-release/backend/app/database.py`
- Create: `doc-release/backend/app/main.py`
- Create: `doc-release/backend/tests/__init__.py`（空文件）
- Create: `doc-release/backend/tests/conftest.py`
- Create: `doc-release/backend/tests/test_health.py`

- [ ] **Step 1: 创建目录与基础文件**

在 `D:\StudyProjects\ai-practice\doc-release\backend` 下创建目录树 `app/`、`tests/`；用 PowerShell 创建空包标记文件：

```powershell
New-Item -ItemType File -Force -Path app\__init__.py, tests\__init__.py | Out-Null
```

`requirements.txt`：

```
fastapi==0.141.1
uvicorn==0.52.4
httpx==0.28.1
requests==2.34.2
pydantic-settings==2.15.0
pytest==9.1.1
pytest-asyncio==1.3.0
sqlalchemy[asyncio]==2.0.40
aiosqlite==0.21.0
tree-sitter==0.26.0
tree-sitter-language-pack==1.22.1
```

`pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

`.env.example`：

```
# 星语大模型网关（内网地址，脱离内网时 LLM 步骤会失败/降级）
XINGYU_URL=http://10.130.13.74:8060/api/chat/chat
ROBOT_CODE=ROBOT_00000149
# xingyu（默认）/ deepseek（回退）
LLM_PROVIDER=xingyu
# DeepSeek 回退密钥（可选，仅 LLM_PROVIDER=deepseek 时需要）
DEEPSEEK_API_KEY=
LLM_TIMEOUT=120
LLM_MAX_CONCURRENCY=3
```

`.gitignore`：

```
venv/
__pycache__/
*.pyc
.pytest_cache/
.env
docrelease.db
sample_repo/
archive/
```

- [ ] **Step 2: 写 config.py**

`app/config.py`：

```python
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 工作区已验证：pydantic-settings v2 不显式声明 env_file 时不会读取 .env
    model_config = SettingsConfigDict(
        env_file=".env" if Path(".env").exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    xingyu_url: str = "http://10.130.13.74:8060/api/chat/chat"
    robot_code: str = "ROBOT_00000149"
    llm_provider: str = "xingyu"
    deepseek_api_key: str = ""
    llm_timeout: int = 120
    llm_max_concurrency: int = 3
    db_url: str = "sqlite+aiosqlite:///./docrelease.db"
    archive_dir: str = "archive"
    sample_repo_dir: str = "sample_repo/order-center"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
```

- [ ] **Step 3: 写 database.py 与 main.py（仅健康检查）**

`app/database.py`：

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.db_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

`app/main.py`：

```python
from fastapi import FastAPI

app = FastAPI(title="释文 DocRelease")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 4: 写 tests/conftest.py 与 test_health.py**

`tests/conftest.py`：

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

（Task 2 会在此文件上扩充测试引擎/会话 fixture 与依赖覆盖；`get_db` 的 import 在此先备好。）

`tests/test_health.py`：

```python
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 5: 创建 venv、安装依赖、跑测试**

```powershell
cd doc-release\backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m pytest tests -q
```

Expected: `1 passed`（test_health）。

- [ ] **Step 6: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short   # 核对暂存区仅包含本次新增文件
git add doc-release/backend
git commit -m 'feat(doc-release): Task 1 后端骨架与测试基建'
```

---

## Task 2: 数据模型与建表

**Files:**
- Create: `doc-release/backend/app/models/__init__.py`
- Create: `doc-release/backend/app/models/repo.py`
- Create: `doc-release/backend/app/models/run.py`
- Create: `doc-release/backend/app/models/artifact.py`
- Modify: `doc-release/backend/app/main.py`（增加 lifespan 建表）
- Modify: `doc-release/backend/tests/conftest.py`（增加测试引擎/会话 fixture 与 get_db 覆盖）
- Create: `doc-release/backend/tests/test_models.py`

- [ ] **Step 1: 写失败测试 test_models.py**

`tests/test_models.py`：

```python
from sqlalchemy import func, select

from app.models import Artifact, Repo, Run


async def test_create_repo_run_artifact(db_session):
    repo = Repo(name="order-center", path=r"D:\tmp\order-center", is_sample=True)
    db_session.add(repo)
    await db_session.commit()

    run = Run(repo_id=repo.id, base_ref="v2.13.3", head_ref="v2.13.4", version_label="v2.13.4")
    run.steps = [{"index": 0, "name": "定位仓库与变更范围", "status": "pending"}]
    run.stats = {"commits": 3}
    db_session.add(run)
    await db_session.commit()

    art = Artifact(run_id=run.id, kind="checklist", filename="checklist.csv",
                   path=r"D:\tmp\archive\checklist.csv", bytes=123)
    db_session.add(art)
    await db_session.commit()

    assert len(run.id) == 36
    assert run.status == "pending"
    assert run.tone == "business"
    assert run.mask is False
    assert run.result is None

    got = (await db_session.execute(select(func.count()).select_from(Artifact))).scalar_one()
    assert got == 1
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests/test_models.py -q
```

Expected: FAIL —— `ModuleNotFoundError: No module named 'app.models'`。

- [ ] **Step 3: 写 models**

`app/models/repo.py`：

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    path: Mapped[str] = mapped_column(String(1000), unique=True)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "is_sample": self.is_sample,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

`app/models/run.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

STEP_NAMES = [
    "定位仓库与变更范围",
    "收集变更（diff 与统计）",
    "AST 解析变更结构",
    "LLM 业务化语义改写",
    "产物生成并归档",
]


def blank_steps() -> list[dict]:
    return [{"index": i, "name": name, "status": "pending"} for i, name in enumerate(STEP_NAMES)]


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey("repos.id"))
    base_ref: Mapped[str] = mapped_column(String(200))
    head_ref: Mapped[str] = mapped_column(String(200))
    version_label: Mapped[str] = mapped_column(String(200))
    tone: Mapped[str] = mapped_column(String(20), default="business")
    mask: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    current_step: Mapped[int] = mapped_column(Integer, default=-1)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    logs: Mapped[list] = mapped_column(JSON, default=list)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "repo_id": self.repo_id,
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "version_label": self.version_label,
            "tone": self.tone,
            "mask": self.mask,
            "status": self.status,
            "current_step": self.current_step,
            "steps": self.steps or [],
            "logs": self.logs or [],
            "stats": self.stats or {},
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
```

`app/models/artifact.py`：

```python
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # checklist / document / trace
    filename: Mapped[str] = mapped_column(String(200))
    path: Mapped[str] = mapped_column(String(1000))
    bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "filename": self.filename, "bytes": self.bytes}
```

`app/models/__init__.py`：

```python
from app.models.artifact import Artifact
from app.models.repo import Repo
from app.models.run import Run

__all__ = ["Artifact", "Repo", "Run"]
```

- [ ] **Step 4: main.py 增加 lifespan 建表**

`app/main.py` 整体替换为：

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  确保模型在 metadata 中注册
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="释文 DocRelease", lifespan=lifespan)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 5: conftest.py 扩充测试引擎与会话**

`tests/conftest.py` 整体替换为：

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import models  # noqa: F401
from app.database import Base, get_db
from app.main import app


@pytest.fixture
async def engine(tmp_path):
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session_maker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(session_maker):
    async with session_maker() as s:
        yield s


@pytest.fixture
async def client(session_maker):
    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 6: 运行测试确认通过**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

Expected: `2 passed`。

- [ ] **Step 7: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/backend
git commit -m 'feat(doc-release): Task 2 数据模型与建表'
```

---

## Task 3: git_service（只读 git 封装）

**Files:**
- Create: `doc-release/backend/app/services/__init__.py`（空文件）
- Create: `doc-release/backend/app/services/errors.py`
- Create: `doc-release/backend/app/services/git_service.py`
- Create: `doc-release/backend/tests/gitfix.py`
- Create: `doc-release/backend/tests/test_git_service.py`

- [ ] **Step 1: 创建 errors.py 与空包文件**

```powershell
New-Item -ItemType File -Force -Path app\services\__init__.py | Out-Null
```

`app/services/errors.py`：

```python
class ServiceError(Exception):
    """业务服务异常基类，API 层据此映射 HTTP 状态码。"""


class GitError(ServiceError):
    """git 相关错误（仓库不可读、引用无效、范围为空等）。"""


class RunCancelled(ServiceError):
    """运行被用户取消。"""
```

- [ ] **Step 2: 写 git 仓库测试助手 gitfix.py**

`tests/gitfix.py`：

```python
import os
import subprocess
from pathlib import Path


def git(cwd: Path, *args: str, env: dict | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env or os.environ, check=True,
    )
    return proc.stdout


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Tester")
    git(repo, "config", "user.email", "tester@example.com")
    return repo


def write_files(repo: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def commit(repo: Path, message: str, date: str = "2026-08-20 10:00:00 +0800") -> None:
    env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message, env=env)


def tag(repo: Path, name: str) -> None:
    git(repo, "tag", name)
```

- [ ] **Step 3: 写失败测试 test_git_service.py**

`tests/test_git_service.py`：

```python
import pytest

from app.services import git_service
from app.services.errors import GitError
from tests.gitfix import commit, init_repo, tag, write_files


@pytest.fixture
def repo(tmp_path):
    r = init_repo(tmp_path)
    write_files(r, {"src/a.ts": "export const A = 1;\n", "README.md": "# demo\n"})
    commit(r, "init")
    tag(r, "v1.0.0")
    write_files(r, {"src/a.ts": "export const A = 2;\nexport function run() {\n  return A;\n}\n"})
    commit(r, "feat: update a", date="2026-08-22 09:00:00 +0800")
    tag(r, "v1.1.0")
    return r


def test_list_refs_and_default_branch(repo):
    refs = git_service.list_refs(str(repo))
    assert [t["name"] for t in refs["tags"]] == ["v1.0.0", "v1.1.0"]
    assert refs["default_branch"] == "main"
    assert refs["branches"][0]["name"] == "main"


def test_resolve_ref(repo):
    sha = git_service.resolve_ref(str(repo), "v1.1.0")
    assert len(sha) == 40


def test_resolve_ref_rejects_option_like(repo):
    with pytest.raises(GitError):
        git_service.resolve_ref(str(repo), "--all")


def test_validate_repo_rejects_non_git_dir(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(GitError):
        git_service.validate_repo(str(plain))


def test_collect_diff_basic(repo):
    data = git_service.collect_diff(str(repo), "v1.0.0", "v1.1.0")
    assert data["stats"] == {"commits": 1, "files": 1, "modules": 1, "added": 3, "removed": 1, "days": 1}
    f = data["files"][0]
    assert f["path"] == "src/a.ts" and f["status"] == "m"
    assert any(l["t"] == "add" and "export function run" in l["s"] for l in f["lines"])
    assert data["modules"][0]["name"] == "src"


def test_collect_diff_empty_range_raises(repo):
    with pytest.raises(GitError, match="没有变更提交"):
        git_service.collect_diff(str(repo), "v1.1.0", "v1.1.0")


def test_collect_diff_truncates(repo):
    data = git_service.collect_diff(str(repo), "v1.0.0", "v1.1.0", max_lines=2)
    assert data["files"][0]["truncated"] is True
    assert len(data["files"][0]["lines"]) == 2


def test_show_file(repo):
    assert "const A = 1" in git_service.show_file(str(repo), "v1.0.0", "src/a.ts")
    assert git_service.show_file(str(repo), "v1.0.0", "src/missing.ts") == ""
```

- [ ] **Step 4: 运行测试确认失败**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests/test_git_service.py -q
```

Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.git_service'`。

- [ ] **Step 5: 实现 git_service.py**

`app/services/git_service.py`：

```python
"""只读封装 git CLI：引用枚举、提交列表、diff 收集、模块聚类。

所有对外函数在出错时抛 GitError；绝不写入被检查的仓库。
"""

import os
import subprocess
from datetime import date
from pathlib import Path

from app.services.errors import GitError

_MAX_FILES = 200
_PATCH_HEADER_PREFIXES = (
    "diff --git", "index ", "--- ", "+++ ", "@@", "new file mode",
    "deleted file mode", "similarity index", "rename from", "rename to",
)


def _run_git(repo_path: str, args: list[str], timeout: int = 60) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", repo_path, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except FileNotFoundError as exc:
        raise GitError("未找到 git 可执行文件") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("git 命令超时") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise GitError(detail[-1] if detail else "git 命令执行失败")
    return proc.stdout


def _check_ref(ref: str) -> str:
    ref = (ref or "").strip()
    if not ref or ref.startswith("-"):
        raise GitError(f"非法的引用名：{ref or '(空)'}")
    return ref


def validate_repo(path: str) -> None:
    if not Path(path).is_dir():
        raise GitError(f"路径不存在或不是目录：{path}")
    _run_git(path, ["rev-parse", "--git-dir"])


def resolve_ref(repo_path: str, ref: str) -> str:
    return _run_git(repo_path, ["rev-parse", "--verify", f"{_check_ref(ref)}^{{commit}}"]).strip()


def list_refs(repo_path: str) -> dict:
    out = _run_git(repo_path, ["for-each-ref", "refs/heads", "refs/tags",
                               "--format=%(refname)|%(refname:short)|%(objectname:short)"])
    branches: list[dict] = []
    tags: list[dict] = []
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            continue
        full, short, sha = parts
        if full.startswith("refs/heads/"):
            branches.append({"name": short, "short": sha})
        elif full.startswith("refs/tags/"):
            tags.append({"name": short, "short": sha})
    branches.sort(key=lambda x: x["name"])
    tags.sort(key=lambda x: x["name"])
    try:
        default_branch = _run_git(repo_path, ["symbolic-ref", "--short", "HEAD"]).strip()
    except GitError:
        default_branch = branches[0]["name"] if branches else ""
    return {"branches": branches, "tags": tags, "default_branch": default_branch}


def list_commits(repo_path: str, base: str, head: str, limit: int = 200) -> list[dict]:
    base, head = _check_ref(base), _check_ref(head)
    out = _run_git(repo_path, ["log", f"{base}..{head}", f"--max-count={limit}",
                               "--format=%h|%an|%ad|%s", "--date=format:%Y-%m-%d"])
    commits = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({"hash": parts[0], "author": parts[1],
                            "date": parts[2], "subject": parts[3]})
    commits.reverse()  # git log 默认新→旧，翻转成最早在前
    return commits


def show_file(repo_path: str, ref: str, path: str) -> str:
    """返回指定引用下的文件内容；文件不存在时返回空串。"""
    ref = _check_ref(ref)
    try:
        return _run_git(repo_path, ["show", f"{ref}:{path}"])
    except GitError:
        return ""


def _split_patch(patch: str, max_lines: int) -> tuple[list[dict], bool]:
    lines: list[dict] = []
    truncated = False
    for raw in patch.splitlines():
        if raw.startswith(_PATCH_HEADER_PREFIXES) or raw.startswith("\\"):
            continue
        if raw.startswith("+"):
            kind, body = "add", raw[1:]
        elif raw.startswith("-"):
            kind, body = "del", raw[1:]
        else:
            kind, body = "ctx", raw[1:] if raw.startswith(" ") else raw
        lines.append({"t": kind, "s": body})
        if len(lines) >= max_lines:
            truncated = True
            break
    return lines, truncated


def cluster_modules(files: list[dict], depth: int = 2) -> list[dict]:
    groups: dict[str, list[str]] = {}
    for f in files:
        parts = Path(f["path"]).parts
        key = "/".join(parts[:depth]) if len(parts) > depth else str(Path(f["path"]).parent)
        if key in (".", ""):
            key = parts[0] if parts else f["path"]
        groups.setdefault(key, []).append(f["path"])
    return [{"name": k, "files": v} for k, v in sorted(groups.items())]


def _span_days(commits: list[dict]) -> int:
    if not commits:
        return 0
    first = date.fromisoformat(commits[0]["date"])
    last = date.fromisoformat(commits[-1]["date"])
    return max((last - first).days, 1)


def collect_diff(repo_path: str, base: str, head: str, max_lines: int = 400) -> dict:
    """收集 base..head 的提交、逐文件 diff（可截断）与统计。"""
    base, head = _check_ref(base), _check_ref(head)
    resolve_ref(repo_path, base)
    resolve_ref(repo_path, head)
    commits = list_commits(repo_path, base, head)
    if not commits:
        raise GitError(f"范围 {base}..{head} 内没有变更提交")

    numstat = _run_git(repo_path, ["diff", "--numstat", f"{base}..{head}", "--"])
    name_status = _run_git(repo_path, ["diff", "--name-status", f"{base}..{head}", "--"])
    statuses: dict[str, str] = {}
    for line in name_status.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            statuses[parts[-1]] = {"A": "a", "D": "d"}.get(parts[0][:1], "m")

    files: list[dict] = []
    total_add = total_del = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_raw, del_raw, path = parts[0], parts[1], parts[2]
        binary = added_raw == "-"
        added = 0 if binary else int(added_raw)
        removed = 0 if binary else int(del_raw)
        total_add += added
        total_del += removed
        entry = {"status": statuses.get(path, "m"), "path": path,
                 "added": added, "removed": removed, "binary": binary,
                 "truncated": False, "lines": []}
        if not binary and len(files) < _MAX_FILES:
            patch = _run_git(repo_path, ["diff", "-U3", f"{base}..{head}", "--", path])
            entry["lines"], entry["truncated"] = _split_patch(patch, max_lines)
        files.append(entry)

    modules = cluster_modules(files)
    stats = {"commits": len(commits), "files": len(files), "modules": len(modules),
             "added": total_add, "removed": total_del, "days": _span_days(commits)}
    return {"base": base, "head": head, "commits": commits, "files": files,
            "stats": stats, "modules": modules}
```

- [ ] **Step 6: 运行测试确认通过**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

Expected: `10 passed`（Task 1-3 全部）。若 `test_collect_diff_basic` 的 `added` 断言失败，说明 git 版本对空行统计不同——先用 `git diff --numstat v1.0.0..v1.1.0` 人工核对实际数字，再修正断言为真实值（不要改实现）。

- [ ] **Step 7: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/backend
git commit -m 'feat(doc-release): Task 3 git_service 只读封装'
```

---

## Task 4: seed_data.py（示例仓库数据）

**Files:**
- Create: `doc-release/backend/seed_data.py`
- Create: `doc-release/backend/tests/test_seed_data.py`

- [ ] **Step 1: 写失败测试 test_seed_data.py**

`tests/test_seed_data.py`：

```python
from seed_data import SCENARIOS, SEED_SEQUENCE


def test_sequence_structure():
    assert SEED_SEQUENCE[0]["kind"] == "commit"
    tags = [s["name"] for s in SEED_SEQUENCE if s["kind"] == "tag"]
    assert tags == ["v2.13.3", "v2.13.4", "v2.14.0", "v3.0.0"]


def test_scenarios_cover_all_tags():
    tags = {s["name"] for s in SEED_SEQUENCE if s["kind"] == "tag"}
    assert {sc["id"] for sc in SCENARIOS} == {"patch", "feature", "major"}
    for sc in SCENARIOS:
        assert sc["base"] in tags and sc["head"] in tags


def test_all_file_contents_non_empty():
    for step in SEED_SEQUENCE:
        if step["kind"] != "commit":
            continue
        assert step["files"], step["message"]
        for path, content in step["files"].items():
            assert content.strip(), f"{path} 内容为空"
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests/test_seed_data.py -q
```

Expected: FAIL —— `ModuleNotFoundError: No module named 'seed_data'`。

- [ ] **Step 3: 写 seed_data.py（全部文件内容）**

`seed_data.py`：

```python
"""示例仓库 order-center 的提交序列与文件内容（纯数据，无副作用）。

SEED_SEQUENCE 按时间顺序包含 commit 与 tag 两类步骤；
commit.files 中 relpath -> 内容，内容为空串表示删除该文件。
"""

SEED_SEQUENCE: list[dict] = [
    {
        "kind": "commit",
        "date": "2026-08-20 10:00:00 +0800",
        "message": "chore: 初始化 order-center 示例仓库",
        "files": {
            "README.md": """# order-center

电商订单中心（示例仓库，由释文 DocRelease 种子脚本生成）。

## 目录结构

- src/report/export     报表导出
- src/order             订单域（优惠券、状态机）
- src/checkout          结算页
- src/aftersale         售后政策
- src/member            会员权益
- src/goods             商品详情
- src/pay               支付
- src/seckill           秒杀库存
- src/auth              登录鉴权
- api/order             订单接口
- api/report            报表接口
- api/legacy            历史遗留接口
""",
            "package.json": """{
  "name": "order-center",
  "version": "2.13.3",
  "private": true,
  "scripts": { "test": "vitest run" }
}
""",
            "go.mod": """module order-center

go 1.23
""",
            "src/report/export/index.ts": """import { chunkToText } from "./writer";
import { loadAllOrders } from "../orders";

export async function exportOrders(query: ExportQuery): Promise<ExportResult> {
  const all = await loadAllOrders(query);
  const text = chunkToText(all);
  await writeFileSafe(text);
  return { rows: all.length };
}
""",
            "src/report/export/writer.ts": """export function chunkToText(rows: OrderRow[]): string {
  return rows.map((r) => r.join(",")).join("\\n");
}

export async function writeFileSafe(text: string): Promise<void> {
  await fs.writeFile(OUTPUT_PATH, text, "utf-8");
}
""",
            "api/report/export.go": """package report

// ExportRequest 报表导出请求
type ExportRequest struct {
	Query string `json:"query"`
}

// ExportResponse 报表导出响应
type ExportResponse struct {
	Rows int `json:"rows"`
}

// MaxExportRows 单次导出行数上限
const MaxExportRows = 50000

// HandleExport 处理导出请求：一次性装载全部行后写出
func HandleExport(req ExportRequest, w Writer) error {
	rows, err := LoadRows(req.Query)
	if err != nil {
		return err
	}
	return w.WriteAll(rows)
}
""",
            "src/order/coupon/stack.ts": """export interface Coupon {
  id: string;
  amount: number;
}

// pickBestCoupon 从单张券中挑选可用券
export function pickBestCoupon(coupon: Coupon, amount: number): Coupon {
  return coupon.amount <= amount ? coupon : { id: "", amount: 0 };
}
""",
            "src/checkout/summary.tsx": """import type { Coupon } from "../order/coupon/stack";

export function CheckoutSummary(props: { coupon: Coupon; total: number }) {
  return (
    <div className="summary">
      <div>商品总额：{props.total}</div>
      <div>优惠券抵扣：{props.coupon.amount}</div>
    </div>
  );
}
""",
            "src/aftersale/policy.ts": """// REFUND_WINDOW_DAYS 无理由退款窗口（天）
export const REFUND_WINDOW_DAYS = 7;

export function canRefund(daysSincePay: number): boolean {
  return daysSincePay <= REFUND_WINDOW_DAYS;
}
""",
            "api/order/list.go": """package order

// ListResponse 订单列表响应
type ListResponse struct {
	Items []Order `json:"items"`
	Total int     `json:"total"`
}

// HandleList 返回用户订单列表
func HandleList(uid string, page int) (*ListResponse, error) {
	items, total, err := queryOrders(uid, page)
	if err != nil {
		return nil, err
	}
	return &ListResponse{Items: items, Total: total}, nil
}
""",
            "src/member/benefit/verify.ts": """import { cache } from "../cache";
import { checkLevel } from "./level";

// verifyCached 基于本地缓存的会员等级校验
export function verifyCached(uid: string, order: Order): BenefitCheck {
  const profile = cache.get(uid);
  return checkLevel(profile.level, order.totalAmount, order.items);
}
""",
            "src/goods/detail/price.tsx": """export function PriceBlock(props: { price: number }) {
  return (
    <div className="price">
      <span className="symbol">¥</span>
      <span className="value">{props.price.toFixed(2)}</span>
    </div>
  );
}
""",
            "src/order/state/machine.ts": """export type Status = "created" | "paid" | "shipped" | "done" | "closed";
export type Action = "pay" | "ship" | "finish" | "close";

const TABLE: Record<Status, Partial<Record<Action, Status>>> = {
  created: { pay: "paid", close: "closed" },
  paid: { ship: "shipped", close: "closed" },
  shipped: { finish: "done" },
  done: {},
  closed: {},
};

// transition 同步计算状态迁移
export function transition(from: Status, action: Action): Status {
  return TABLE[from][action] ?? from;
}
""",
            "api/legacy/order.go": """package legacy

// CreateOrderV1 老版下单接口（POST /v1/order/create），仅兼容存量客户端
func CreateOrderV1(req CreateReq) (*CreateResp, error) {
	return createOrder(req, "v1")
}
""",
            "src/pay/callback/verify.ts": """import { md5 } from "../crypto";

// verifyCallback 校验支付回调签名（MD5）
export function verifyCallback(payload: PayPayload, sign: string): boolean {
  const raw = `${payload.orderId}${payload.amount}${payload.tradeNo}${SECRET}`;
  return md5(raw) === sign;
}
""",
            "src/seckill/stock/deduct.ts": """// deductStock 扣减秒杀库存：先读再写
export async function deductStock(skuId: string, count: number): Promise<boolean> {
  const stock = Number(await redis.get(`seckill:stock:${skuId}`));
  if (stock < count) {
    return false;
  }
  await redis.set(`seckill:stock:${skuId}`, String(stock - count));
  return true;
}
""",
            "src/auth/sms.ts": """// loginBySms 短信验证码登录
export async function loginBySms(phone: string, code: string): Promise<LoginResult> {
  const cached = await store.get(`sms:${phone}`);
  if (cached !== code) {
    return { ok: false };
  }
  return issueToken(phone);
}
""",
        },
    },
    {"kind": "tag", "name": "v2.13.3"},
    {
        "kind": "commit",
        "date": "2026-09-10 14:20:00 +0800",
        "message": "feat(report): 导出支持分片流式写出",
        "files": {
            "src/report/export/stream.ts": """// CHUNK_SIZE 单次写出分片大小（行）
export const CHUNK_SIZE = 2000;

// streamWrite 分片流式写出，避免一次性载入全部行
export async function streamWrite(query: ExportQuery, sink: LineSink): Promise<number> {
  let cursor = "";
  let written = 0;
  while (true) {
    const page = await fetchPage(query, cursor, CHUNK_SIZE);
    if (page.rows.length === 0) {
      break;
    }
    for (const row of page.rows) {
      await sink.write(row);
      written += 1;
    }
    cursor = page.nextCursor;
  }
  return written;
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-09-11 11:05:00 +0800",
        "message": "feat(report): 导出网络请求增加指数退避重试",
        "files": {
            "src/report/export/retry.ts": """// MAX_RETRIES 网络抖动重试次数
export const MAX_RETRIES = 3;

// withRetry 指数退避重试包装
export async function withRetry<T>(fn: () => Promise<T>, retries = MAX_RETRIES): Promise<T> {
  let lastError: unknown;
  for (let i = 0; i <= retries; i += 1) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      await sleep(200 * 2 ** i);
    }
  }
  throw lastError;
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-09-12 16:40:00 +0800",
        "message": "refactor(report): 导出接口按游标分页并走流式写出",
        "files": {
            "src/report/export/index.ts": """import { streamWrite } from "./stream";
import { withRetry } from "./retry";
import { loadAllOrders } from "../orders";

// 小数据量走内存导出，大数据量走分片流式写出
export async function exportOrders(query: ExportQuery): Promise<ExportResult> {
  const estimated = await estimateRows(query);
  if (estimated <= MEMORY_THRESHOLD) {
    const all = await withRetry(() => loadAllOrders(query));
    await writeFileSafe(chunkToText(all));
    return { rows: all.length };
  }
  const written = await withRetry(() => streamWrite(query, fileSink(OUTPUT_PATH)));
  return { rows: written };
}
""",
            "api/report/export.go": """package report

// ExportRequest 报表导出请求
type ExportRequest struct {
	Query  string `json:"query"`
	Cursor string `json:"cursor"`
}

// ExportResponse 报表导出响应
type ExportResponse struct {
	Rows       int    `json:"rows"`
	NextCursor string `json:"nextCursor"`
}

// PageSize 单页行数
const PageSize = 2000

// HandleExport 处理导出请求：按游标分片返回
func HandleExport(req ExportRequest, w Writer) error {
	page, err := LoadPage(req.Query, req.Cursor, PageSize)
	if err != nil {
		return err
	}
	return w.WritePage(page)
}
""",
        },
    },
    {"kind": "tag", "name": "v2.13.4"},
    {
        "kind": "commit",
        "date": "2026-09-24 10:30:00 +0800",
        "message": "feat(coupon): 支持优惠券叠加并求组合最优解",
        "files": {
            "src/order/coupon/stack.ts": """export interface Coupon {
  id: string;
  amount: number;
  stackable: boolean;
}

// MAX_SEARCH_COUNT 券数量上限，超过则退化为贪心
const MAX_SEARCH_COUNT = 12;

// resolveBestCombination 求券组合最优解（可叠加场景）
export function resolveBestCombination(coupons: Coupon[], amount: number): Coupon[] {
  const usable = coupons.filter((c) => c.amount <= amount);
  const single = usable.filter((c) => !c.stackable);
  const stackable = usable.filter((c) => c.stackable);
  let best = pickBestSingle(single);
  if (stackable.length <= MAX_SEARCH_COUNT) {
    const combo = searchMaxSubset(stackable, amount);
    if (sum(combo) > best.amount) {
      best = { id: "combo", amount: sum(combo), stackable: true };
    }
  } else {
    const greedy = greedyMax(stackable, amount);
    if (greedy.amount > best.amount) {
      best = greedy;
    }
  }
  return best.id ? [best] : [];
}

// pickBestCoupon 保留旧接口：仅支持单券
export function pickBestCoupon(coupon: Coupon, amount: number): Coupon {
  return coupon.amount <= amount ? coupon : { id: "", amount: 0, stackable: false };
}
""",
            "src/checkout/summary.tsx": """import type { Coupon } from "../order/coupon/stack";

export function CheckoutSummary(props: { coupons: Coupon[]; total: number }) {
  const discount = props.coupons.reduce((sum, c) => sum + c.amount, 0);
  return (
    <div className="summary">
      <div>商品总额：{props.total}</div>
      {props.coupons.map((c) => (
        <div key={c.id}>优惠券抵扣：{c.amount}</div>
      ))}
      <div className="payable">应付：{Math.max(props.total - discount, 0)}</div>
    </div>
  );
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-09-28 09:15:00 +0800",
        "message": "feat(aftersale): 无理由退款窗口由 7 天调整为 15 天",
        "files": {
            "src/aftersale/policy.ts": """// REFUND_WINDOW_DAYS 无理由退款窗口（天），v3 前调整为 15 天
export const REFUND_WINDOW_DAYS = 15;

// MAX_REFUND_AMOUNT 单笔最大退款金额（元）
export const MAX_REFUND_AMOUNT = 20000;

export function canRefund(daysSincePay: number): boolean {
  return daysSincePay <= REFUND_WINDOW_DAYS;
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-10-02 15:50:00 +0800",
        "message": "feat(order): 订单列表返回时可叠加券标记",
        "files": {
            "api/order/list.go": """package order

// ListResponse 订单列表响应
type ListResponse struct {
	Items           []Order `json:"items"`
	Total           int     `json:"total"`
	CouponStackable bool    `json:"couponStackable"`
}

// HandleList 返回用户订单列表
func HandleList(uid string, page int) (*ListResponse, error) {
	items, total, err := queryOrders(uid, page)
	if err != nil {
		return nil, err
	}
	return &ListResponse{Items: items, Total: total, CouponStackable: featureOn("coupon_stack")}, nil
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-10-08 17:25:00 +0800",
        "message": "feat(member): 会员权益改为实时校验，移除本地缓存校验",
        "files": {
            "src/member/benefit/verify.ts": """import { fetchProfile } from "../remote";
import { checkLevel } from "./level";
import { PROFILE_TTL_MS } from "./cache-policy";

// verifyRealtime 实时拉取会员档案校验权益，避免缓存过期导致误判
export async function verifyRealtime(uid: string, order: Order): Promise<BenefitCheck> {
  const profile = await fetchProfile(uid, PROFILE_TTL_MS);
  return checkLevel(profile.level, order.totalAmount, order.items);
}
""",
            "src/goods/detail/price.tsx": """import { calcAfterPromotion } from "../promotion";

export function PriceBlock(props: { price: number; couponAmount: number }) {
  const final = calcAfterPromotion(props.price, props.couponAmount);
  return (
    <div className="price">
      <span className="label">预计到手价</span>
      <span className="symbol">¥</span>
      <span className="value">{final.toFixed(2)}</span>
    </div>
  );
}
""",
        },
    },
    {"kind": "tag", "name": "v2.14.0"},
    {
        "kind": "commit",
        "date": "2026-10-09 10:05:00 +0800",
        "message": "feat(legacy)!: 下线 v1 下单接口",
        "files": {
            "api/legacy/order.go": """package legacy

// v1 下单接口已于 3.0 下线：POST /v1/order/create 不再受理流量。
// 存量客户端请迁移至 POST /v2/orders（由 order 包提供）。
// 保留本文件记录迁移说明，确认无调用后可删除。

// GoneHandler 对旧路径统一返回 410
func GoneHandler(w http.ResponseWriter, r *http.Request) {
	http.Error(w, "v1 order api removed, use POST /v2/orders", http.StatusGone)
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-10-10 16:30:00 +0800",
        "message": "refactor(order)!: 状态机改为事件溯源，新增多仓库存分配",
        "files": {
            "src/order/state/machine.ts": """export type Status = "created" | "paid" | "shipped" | "done" | "closed";
export type Action = "pay" | "ship" | "finish" | "close";

export interface OrderEvent {
  action: Action;
  at: number;
  operator: string;
}

const TABLE: Record<Status, Partial<Record<Action, Status>>> = {
  created: { pay: "paid", close: "closed" },
  paid: { ship: "shipped", close: "closed" },
  shipped: { finish: "done" },
  done: {},
  closed: {},
};

// project 依据事件序列重放得出当前状态（事件溯源）
export function project(events: OrderEvent[]): Status {
  let state: Status = "created";
  for (const e of events) {
    state = TABLE[state][e.action] ?? state;
  }
  return state;
}
""",
            "src/inventory/multi-warehouse.ts": """// allocateAcross 跨多仓分配库存：从小仓优先填满
interface Allocation {
  warehouseId: string;
  count: number;
}

// allocateAcross 跨多仓分配库存：从小仓优先填满
export async function allocateAcross(skuId: string, count: number): Promise<Allocation[]> {
  const warehouses = await listWarehouses(skuId);
  warehouses.sort((a, b) => a.available - b.available);
  const plan: Allocation[] = [];
  let remain = count;
  for (const wh of warehouses) {
    if (remain <= 0) {
      break;
    }
    const take = Math.min(wh.available, remain);
    plan.push({ warehouseId: wh.id, count: take });
    remain -= take;
  }
  if (remain > 0) {
    throw new StockShortageError(skuId, remain);
  }
  return plan;
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-10-12 11:45:00 +0800",
        "message": "feat(pay)!: 支付回调签名升级为 HMAC-SHA256；秒杀扣减改 Lua 原子脚本",
        "files": {
            "src/pay/callback/verify.ts": """import { hmacSha256 } from "../crypto";

// verifyCallback 校验支付回调签名（HMAC-SHA256，替代 MD5）
export function verifyCallback(payload: PayPayload, sign: string): boolean {
  const raw = `${payload.orderId}${payload.amount}${payload.tradeNo}`;
  const expected = hmacSha256(raw, SIGN_KEY);
  return timingSafeEqual(expected, sign);
}
""",
            "src/seckill/stock/deduct.ts": """const LUA_DEDUCT = `
local stock = tonumber(redis.call("get", KEYS[1]) or "-1")
if stock < tonumber(ARGV[1]) then
  return 0
end
redis.call("decrby", KEYS[1], ARGV[1])
return 1
`;

// deductStock 扣减秒杀库存：Lua 脚本原子执行，避免并发超卖
export async function deductStock(skuId: string, count: number): Promise<boolean> {
  const result = await redis.eval(LUA_DEDUCT, 1, `seckill:stock:${skuId}`, String(count));
  return result === 1;
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-10-13 09:30:00 +0800",
        "message": "feat(aftersale): 支持按明细部分退款",
        "files": {
            "src/aftersale/partial-refund.ts": """// refundPartial 按明细发起部分退款，支持多次退至总额上限
export async function refundPartial(orderNo: string, items: RefundItem[]): Promise<RefundResult> {
  const refunded = await sumRefunded(orderNo);
  const request = sumItems(items);
  if (refunded + request > MAX_REFUND_AMOUNT) {
    throw new RefundLimitError(orderNo);
  }
  return createRefund(orderNo, items);
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-10-14 15:10:00 +0800",
        "message": "chore(auth)!: 短信登录迁移至统一鉴权中心",
        "files": {
            "src/auth/sms.ts": """// 短信登录已于 3.0 迁移至统一鉴权中心（auth-center），本文件仅保留迁移说明。
// 新接入方式见 https://auth-center.internal/docs/sms-login
export {};
""",
        },
    },
    {"kind": "tag", "name": "v3.0.0"},
]

SCENARIOS: list[dict] = [
    {
        "id": "patch",
        "name": "补丁修复",
        "short": "hotfix",
        "version": "v2.13.4",
        "base": "v2.13.3",
        "head": "v2.13.4",
        "description": "报表导出超时与网络抖动问题的修复版本，变更集中在报表导出模块。",
    },
    {
        "id": "feature",
        "name": "功能迭代",
        "short": "feature",
        "version": "v2.14.0",
        "base": "v2.13.3",
        "head": "v2.14.0",
        "description": "优惠券叠加、退款窗口调整、会员权益实时校验等功能特性版本。",
    },
    {
        "id": "major",
        "name": "大版本升级",
        "short": "major",
        "version": "v3.0.0",
        "base": "v2.14.0",
        "head": "v3.0.0",
        "description": "含破坏性变更的大版本：v1 接口下线、状态机事件化、签名升级与登录迁移。",
    },
]
```

> 写文件时的注意：内容里出现的 `\\n`（如 writer.ts 的 `join("\\n")`）在 Python 三引号字符串中要写成 `\\n` 字面量本身，保证生成到示例仓库里的源码是合法的 TypeScript。

- [ ] **Step 4: 运行测试确认通过**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests/test_seed_data.py -q
```

Expected: `3 passed`。

- [ ] **Step 5: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/backend
git commit -m 'feat(doc-release): Task 4 示例仓库数据 seed_data'
```

---

## Task 5: 示例仓库生成脚本与启动自检

**Files:**
- Create: `doc-release/backend/seed_sample_repo.py`
- Modify: `doc-release/backend/app/main.py`（lifespan 增加种子自检与示例仓注册）
- Create: `doc-release/backend/tests/test_seed_sample_repo.py`

- [ ] **Step 1: 写失败测试 test_seed_sample_repo.py**

`tests/test_seed_sample_repo.py`：

```python
import pytest

import seed_sample_repo
from tests.gitfix import git


@pytest.fixture(scope="module")
def sample_repo(tmp_path_factory):
    target = tmp_path_factory.mktemp("seed") / "order-center"
    return seed_sample_repo.generate(target)


def _rev_count(repo, rng: str) -> int:
    return int(git(repo, "rev-list", "--count", rng).strip())


def test_tags_created(sample_repo):
    assert sorted(git(sample_repo, "tag", "--list").split()) == ["v2.13.3", "v2.13.4", "v2.14.0", "v3.0.0"]


def test_ranges_have_expected_commit_counts(sample_repo):
    assert _rev_count(sample_repo, "v2.13.3..v2.13.4") == 3
    assert _rev_count(sample_repo, "v2.13.4..v2.14.0") == 4
    assert _rev_count(sample_repo, "v2.14.0..v3.0.0") == 5


def test_patch_range_files_and_status(sample_repo):
    lines = git(sample_repo, "diff", "--name-status", "v2.13.3..v2.13.4").strip().splitlines()
    statuses = {l.split("\t")[1]: l.split("\t")[0] for l in lines}
    assert sorted(statuses) == ["api/report/export.go", "src/report/export/index.ts",
                                "src/report/export/retry.ts", "src/report/export/stream.ts"]
    assert statuses["src/report/export/stream.ts"] == "A"
    assert statuses["src/report/export/index.ts"] == "M"


def test_contract_signal_scenarios(sample_repo):
    # major 范围：v1 下单接口被删除（导出符号删除信号的依据）
    legacy_head = git(sample_repo, "show", "v3.0.0:api/legacy/order.go")
    assert "CreateOrderV1" not in legacy_head
    # feature 范围：退款窗口常量值变化（常量变更信号的依据）
    assert "REFUND_WINDOW_DAYS = 7" in git(sample_repo, "show", "v2.13.3:src/aftersale/policy.ts")
    assert "REFUND_WINDOW_DAYS = 15" in git(sample_repo, "show", "v2.14.0:src/aftersale/policy.ts")


def test_generate_is_idempotent(sample_repo):
    assert seed_sample_repo.generate(sample_repo) == sample_repo
    assert _rev_count(sample_repo, "v2.13.3..v3.0.0") == 12
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests/test_seed_sample_repo.py -q
```

Expected: FAIL —— `ModuleNotFoundError: No module named 'seed_sample_repo'`。

- [ ] **Step 3: 实现 seed_sample_repo.py**

`seed_sample_repo.py`：

```python
"""按 SEED_SEQUENCE 生成示例 git 仓库（幂等，绝不删除已有目录）。"""

import os
import subprocess
import sys
from pathlib import Path

from seed_data import SEED_SEQUENCE

REPO_DIR_NAME = "order-center"
REQUIRED_TAGS = {"v2.13.3", "v2.13.4", "v2.14.0", "v3.0.0"}


def _git(cwd: Path, *args: str, env: dict | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env or os.environ, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{(proc.stderr or '').strip()}")
    return proc.stdout


def _is_ready(target: Path) -> bool:
    if not (target / ".git").is_dir():
        return False
    try:
        tags = set(_git(target, "tag", "--list").split())
    except RuntimeError:
        return False
    return REQUIRED_TAGS.issubset(tags)


def generate(target: Path) -> Path:
    """在 target 目录生成示例仓库；已就绪时直接返回，不重复生成。"""
    target = Path(target)
    if _is_ready(target):
        return target
    if (target / ".git").exists():
        raise RuntimeError(f"{target} 存在未完成生成的 git 仓库，请手动删除后重试")

    target.mkdir(parents=True, exist_ok=True)
    _git(target, "init", "-b", "main")
    _git(target, "config", "user.name", "order-center-bot")
    _git(target, "config", "user.email", "bot@order-center.internal")

    for step in SEED_SEQUENCE:
        if step["kind"] == "commit":
            for rel, content in step["files"].items():
                path = target / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            _git(target, "add", "-A")
            env = {**os.environ, "GIT_AUTHOR_DATE": step["date"], "GIT_COMMITTER_DATE": step["date"]}
            _git(target, "commit", "-m", step["message"], env=env)
        elif step["kind"] == "tag":
            _git(target, "tag", step["name"])
    return target


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sample_repo") / REPO_DIR_NAME
    result = generate(target)
    print(f"示例仓库就绪：{result.resolve()}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: main.py 增加启动自检（lifespan）**

`app/main.py` 整体替换为：

```python
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import select

from app import models  # noqa: F401  确保模型在 metadata 中注册
from app.config import settings
from app.database import AsyncSessionLocal, Base, engine
from app.models import Repo

import seed_sample_repo


async def _ensure_sample_repo() -> None:
    """首次启动时幂等生成示例仓库并注册为 is_sample=True 的仓库记录。"""
    repo_path = await asyncio.to_thread(seed_sample_repo.generate, Path(settings.sample_repo_dir))
    resolved = str(repo_path.resolve())
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(Repo).where(Repo.path == resolved))).scalar_one_or_none()
        if existing is None:
            name = "order-center" if repo_path.name == seed_sample_repo.REPO_DIR_NAME else repo_path.name
            db.add(Repo(name=name, path=resolved, is_sample=True))
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_sample_repo()
    yield


app = FastAPI(title="释文 DocRelease", lifespan=lifespan)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 5: 运行全部测试确认通过**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

Expected: 全部通过（约 15 passed）。若 `test_ranges_have_expected_commit_counts` 失败，检查 seed_data 的 tag 插入位置是否与提交顺序一致。

- [ ] **Step 6: 手动验证种子脚本可独立运行**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe seed_sample_repo.py
.\venv\Scripts\python.exe -c "import subprocess;print(subprocess.run(['git','-C','sample_repo/order-center','tag','--list'],capture_output=True,text=True).stdout)"
```

Expected: 打印 `示例仓库就绪：...\sample_repo\order-center`，第二行列出 4 个标签。

- [ ] **Step 7: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/backend
git commit -m 'feat(doc-release): Task 5 示例仓库生成与启动自检'
```

---

## Task 6: parser_service（tree-sitter 符号解析）

**Files:**
- Create: `doc-release/backend/app/services/parser_service.py`
- Create: `doc-release/backend/tests/test_parser_service.py`

- [ ] **Step 1: 写失败测试 test_parser_service.py**

`tests/test_parser_service.py`：

```python
from app.services import parser_service as ps


def test_extract_ts_export_symbols():
    src = (
        "export const A = 7;\n"
        "export function f(a: number) { return a; }\n"
        "export interface I { x: number }\n"
        "export type T = string;\n"
    )
    syms = {s.name: s for s in ps.extract_symbols(src, "typescript")}
    assert syms["A"].kind == "const" and syms["A"].value == "7"
    assert syms["f"].kind == "function"
    assert syms["I"].kind == "interface"
    assert syms["T"].kind == "type"


def test_extract_go_exported_only():
    src = (
        "package p\n\n"
        "func Exported() {}\n"
        "func hidden() {}\n\n"
        "const MaxRows = 500\n\n"
        "func (s *S) ExportedMethod() {}\n"
    )
    names = {s.name for s in ps.extract_symbols(src, "go")}
    assert names == {"Exported", "MaxRows", "ExportedMethod"}
    by_name = {s.name: s for s in ps.extract_symbols(src, "go")}
    assert by_name["MaxRows"].kind == "const" and by_name["MaxRows"].value == "500"


def test_extract_python_symbols():
    src = "MAX_N = 5\n\n\ndef do():\n    pass\n\n\nclass Big:\n    pass\n"
    syms = {s.name: s for s in ps.extract_symbols(src, "python")}
    assert syms["MAX_N"].kind == "const" and syms["MAX_N"].value == "5"
    assert syms["do"].kind == "function" and syms["Big"].kind == "class"


def test_compare_and_const_change_signal():
    base = ps.extract_symbols("export const W = 7;\n", "typescript")
    head = ps.extract_symbols("export const W = 15;\n", "typescript")
    diff = ps.compare_symbols(base, head)
    assert len(diff["changed"]) == 1
    signals = ps.detect_contract_signals("p.ts", diff)
    assert any(s["kind"] == "const_change" and "7" in s["message"] and "15" in s["message"] for s in signals)


def test_symbol_removed_signal():
    base = ps.extract_symbols("export function gone() {}\nexport function kept() {}\n", "typescript")
    head = ps.extract_symbols("export function kept() {}\n", "typescript")
    signals = ps.detect_contract_signals("p.ts", ps.compare_symbols(base, head))
    assert any(s["kind"] == "symbol_removed" and "gone" in s["message"] for s in signals)


def test_degraded_for_unknown_language():
    result = ps.parse_file_pair("a.rb", "def x; end", "def y; end", [])
    assert result["degraded"] is True and result["language"] is None


def test_route_signals_from_diff_lines():
    lines = [
        {"t": "del", "s": "// CreateOrderV1 老版下单接口（POST /v1/order/create）"},
        {"t": "add", "s": "// 存量客户端请迁移至 POST /v2/orders"},
    ]
    signals = ps.detect_route_signals("api/legacy/order.go", lines)
    assert any(s["kind"] == "route_removed" and "/v1/order/create" in s["message"] for s in signals)
    assert any(s["kind"] == "route_added" and "/v2/orders" in s["message"] for s in signals)


def test_parse_file_pair_tsx_real_pair():
    base = "export function PriceBlock(props) {\n  return <div>{props.price}</div>;\n}\n"
    head = base + "\nexport const LABEL = \"到手价\";\n"
    result = ps.parse_file_pair("src/price.tsx", base, head, [])
    assert result["degraded"] is False
    assert [s["name"] for s in result["symbols"]["added"]] == ["LABEL"]
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests/test_parser_service.py -q
```

Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.parser_service'`。

- [ ] **Step 3: 实现 parser_service.py**

`app/services/parser_service.py`：

```python
"""tree-sitter 符号级解析：导出符号对比与契约信号提取。

支持 .ts/.tsx/.go/.py；未知语言或解析异常时降级为文件级信号（degraded=True）。
"""

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from tree_sitter_language_pack import get_parser

LANG_BY_EXT = {".ts": "typescript", ".tsx": "tsx", ".go": "go", ".py": "python"}

_ROUTE_PATTERN = re.compile(r"(?:GET|POST|PUT|DELETE|PATCH)\s+(/v\d[\w/{}\-\.]*)|(/v\d[\w/{}\-\.]*)")


@dataclass
class Symbol:
    name: str
    kind: str                 # function / class / interface / type / const / func / method / var
    signature: str            # 规范化的首行文本
    value: str | None = None  # 字面值文本（仅 const/var）


def detect_language(path: str) -> str | None:
    return LANG_BY_EXT.get(Path(path).suffix.lower())


def _first_line(node) -> str:
    return node.text.decode("utf-8", errors="replace").split("\n")[0]


def _norm(line: str) -> str:
    return " ".join(line.split())


def _name_text(node) -> str | None:
    n = node.child_by_field_name("name")
    return n.text.decode("utf-8", errors="replace") if n is not None else None


def _extract_ts(node) -> list[Symbol]:
    out: list[Symbol] = []
    if node.type != "export_statement":
        return out
    for child in node.children:
        if child.type in ("function_declaration", "class_declaration",
                          "interface_declaration", "type_alias_declaration"):
            name = _name_text(child)
            if name:
                kind = {"function_declaration": "function", "class_declaration": "class",
                        "interface_declaration": "interface", "type_alias_declaration": "type"}[child.type]
                out.append(Symbol(name, kind, _norm(_first_line(child))))
        elif child.type == "lexical_declaration":
            for decl in child.children:
                if decl.type != "variable_declarator":
                    continue
                name = _name_text(decl)
                if not name:
                    continue
                value_node = decl.child_by_field_name("value")
                value = _norm(_first_line(value_node)) if value_node is not None else None
                out.append(Symbol(name, "const", _norm(_first_line(decl)), value))
    return out


def _is_exported(name: str) -> bool:
    return bool(name) and name[0].isupper()


def _extract_go(node) -> list[Symbol]:
    out: list[Symbol] = []
    if node.type in ("function_declaration", "method_declaration"):
        name = _name_text(node)
        if name and _is_exported(name):
            out.append(Symbol(name, "func" if node.type == "function_declaration" else "method",
                              _norm(_first_line(node))))
    elif node.type == "type_declaration":
        for spec in node.children:
            if spec.type == "type_spec":
                name = _name_text(spec)
                if name and _is_exported(name):
                    out.append(Symbol(name, "type", _norm(_first_line(spec))))
    elif node.type in ("const_declaration", "var_declaration"):
        for spec in node.children:
            if spec.type in ("const_spec", "var_spec"):
                name = _name_text(spec)
                if not name or not _is_exported(name):
                    continue
                value_node = spec.child_by_field_name("value")
                value = _norm(_first_line(value_node)) if value_node is not None else None
                out.append(Symbol(name, "const" if spec.type == "const_spec" else "var",
                                  _norm(_first_line(spec)), value))
    return out


def _extract_py(node) -> list[Symbol]:
    out: list[Symbol] = []
    if node.type in ("function_definition", "class_definition"):
        name = _name_text(node)
        if name:
            kind = "function" if node.type == "function_definition" else "class"
            out.append(Symbol(name, kind, _norm(_first_line(node))))
    elif node.type == "expression_statement":
        for child in node.children:
            if child.type != "assignment":
                continue
            left = child.child_by_field_name("left")
            right = child.child_by_field_name("right")
            if left is None or left.type != "identifier":
                continue
            name = left.text.decode("utf-8", errors="replace")
            if not name.isupper():
                continue
            value = _norm(_first_line(right)) if right is not None else None
            out.append(Symbol(name, "const", _norm(_first_line(child)), value))
    return out


def extract_symbols(source: str, lang: str) -> list[Symbol]:
    parser = get_parser(lang)
    tree = parser.parse(source.encode("utf-8"))
    out: list[Symbol] = []
    for node in tree.root_node.children:
        if lang in ("typescript", "tsx"):
            out.extend(_extract_ts(node))
        elif lang == "go":
            out.extend(_extract_go(node))
        elif lang == "python":
            out.extend(_extract_py(node))
    return out


def compare_symbols(base: list[Symbol], head: list[Symbol]) -> dict:
    base_map = {s.name: s for s in base}
    head_map = {s.name: s for s in head}
    added = [s for n, s in head_map.items() if n not in base_map]
    removed = [s for n, s in base_map.items() if n not in head_map]
    changed = []
    for name, bs in base_map.items():
        hs = head_map.get(name)
        if hs is not None and bs.signature != hs.signature:
            changed.append({"name": name, "kind": hs.kind, "before": bs.signature, "after": hs.signature,
                            "value_before": bs.value, "value_after": hs.value})
    return {"added": [asdict(s) for s in added], "removed": [asdict(s) for s in removed], "changed": changed}


def detect_contract_signals(path: str, symbols: dict) -> list[dict]:
    signals: list[dict] = []
    for c in symbols["changed"]:
        if (c["kind"] == "const" and c["value_before"] and c["value_after"]
                and c["value_before"] != c["value_after"]):
            signals.append({"kind": "const_change", "path": path,
                            "message": f"常量 {c['name']} 由 {c['value_before']} 变为 {c['value_after']}"})
    for s in symbols["removed"]:
        signals.append({"kind": "symbol_removed", "path": path,
                        "message": f"导出符号 {s['name']}（{s['kind']}）已删除"})
    return signals


def detect_route_signals(path: str, lines: list[dict]) -> list[dict]:
    added_routes: set[str] = set()
    removed_routes: set[str] = set()
    for line in lines:
        if line["t"] not in ("add", "del"):
            continue
        bucket = added_routes if line["t"] == "add" else removed_routes
        for m in _ROUTE_PATTERN.finditer(line["s"]):
            bucket.add(m.group(1) or m.group(2))
    signals = []
    for r in sorted(removed_routes - added_routes):
        signals.append({"kind": "route_removed", "path": path, "message": f"接口路径 {r} 已移除或变更"})
    for r in sorted(added_routes - removed_routes):
        signals.append({"kind": "route_added", "path": path, "message": f"新增接口路径 {r}"})
    return signals


def parse_file_pair(path: str, base_src: str, head_src: str, diff_lines: list[dict]) -> dict:
    """解析一对文件（基线/头版）并输出符号对比与契约信号；失败时降级。"""
    lang = detect_language(path)
    result = {
        "language": lang,
        "degraded": False,
        "symbols": {"added": [], "removed": [], "changed": []},
        "contract_signals": detect_route_signals(path, diff_lines),
    }
    if lang is None:
        result["degraded"] = True
        return result
    try:
        base_symbols = extract_symbols(base_src, lang) if base_src else []
        head_symbols = extract_symbols(head_src, lang) if head_src else []
        symbols = compare_symbols(base_symbols, head_symbols)
        result["symbols"] = symbols
        result["contract_signals"].extend(detect_contract_signals(path, symbols))
    except Exception:  # noqa: BLE001 —— 任何解析异常均降级为文件级信号
        result["degraded"] = True
    return result
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

Expected: 全部通过。首次导入 tree-sitter-language-pack 较慢（约 2-5 秒），后续正常。

- [ ] **Step 5: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/backend
git commit -m 'feat(doc-release): Task 6 tree-sitter 符号解析服务'
```

---

## Task 7: 术语表与提示词模板

**Files:**
- Create: `doc-release/backend/app/glossary.json`
- Create: `doc-release/backend/app/services/glossary.py`
- Create: `doc-release/backend/app/prompts/__init__.py`（空文件）
- Create: `doc-release/backend/app/prompts/docrelease_v1.py`
- Create: `doc-release/backend/tests/test_glossary.py`

- [ ] **Step 1: 写 glossary.json**

`app/glossary.json`：

```json
{
  "version": "2026.10",
  "terms": [
    {"term": "订单中心", "aliases": ["order-center", "订单服务"], "note": "统一订单域服务"},
    {"term": "券叠加", "aliases": ["coupon stack", "stackable", "叠加券"], "note": "多张优惠券组合使用"},
    {"term": "分片流式写出", "aliases": ["stream write", "streamWrite", "流式导出"], "note": "分页拉取逐片写盘，避免大数据量内存溢出"},
    {"term": "指数退避", "aliases": ["exponential backoff", "withRetry"], "note": "重试间隔指数增长的容错策略"},
    {"term": "事件溯源", "aliases": ["event sourcing", "project"], "note": "由事件序列重放推导当前状态"},
    {"term": "多仓库存", "aliases": ["multi warehouse", "allocateAcross", "跨仓"], "note": "跨多个仓库分配库存"},
    {"term": "部分退款", "aliases": ["partial refund", "refundPartial"], "note": "按订单明细发起退款"},
    {"term": "无理由退款窗口", "aliases": ["refund window", "REFUND_WINDOW_DAYS"], "note": "可申请无理由退款的时限"},
    {"term": "秒杀", "aliases": ["seckill", "flash sale"], "note": "限时抢购场景"},
    {"term": "超卖", "aliases": ["oversell", "over-sell"], "note": "库存扣减不一致导致售出数量超过库存"},
    {"term": "幂等", "aliases": ["idempotent", "idempotency"], "note": "重复执行与单次执行结果一致"},
    {"term": "回调", "aliases": ["callback", "notify"], "note": "第三方异步结果通知"},
    {"term": "签名校验", "aliases": ["sign verify", "HMAC", "verifyCallback"], "note": "校验请求来源与完整性"},
    {"term": "会员权益", "aliases": ["benefit", "member level"], "note": "会员等级对应的优惠与特权"},
    {"term": "实时校验", "aliases": ["realtime verify", "verifyRealtime"], "note": "每次请求实时获取最新数据校验"},
    {"term": "游标分页", "aliases": ["cursor", "nextCursor"], "note": "基于游标的分页拉取"},
    {"term": "灰度开关", "aliases": ["feature flag", "featureOn"], "note": "按开关逐步放量"},
    {"term": "迁移", "aliases": ["migration", "迁移至"], "note": "能力从旧位置搬到新位置"},
    {"term": "破坏性变更", "aliases": ["breaking change", "breaking"], "note": "不向后兼容的接口或行为变更"},
    {"term": "回归测试", "aliases": ["regression test"], "note": "验证老功能未被新变更破坏"}
  ]
}
```

- [ ] **Step 2: 写失败测试 test_glossary.py**

```powershell
New-Item -ItemType File -Force -Path app\prompts\__init__.py | Out-Null
```

`tests/test_glossary.py`：

```python
from app.prompts.docrelease_v1 import PROMPT_VERSION, SYSTEM_PROMPT_TEMPLATE, build_user_prompt
from app.services import glossary as g


def test_glossary_loads_and_has_terms():
    data = g.load_glossary()
    assert data["version"]
    assert len(data["terms"]) >= 20


def test_match_terms_by_term_and_alias():
    hits = g.match_terms("导出改为分片流式写出，并加了 withRetry 指数退避")
    assert "分片流式写出" in hits and "指数退避" in hits


def test_match_terms_empty():
    assert g.match_terms("nothing here") == []


def test_prompt_section_contains_terms():
    section = g.build_glossary_prompt_section()
    assert "券叠加" in section and "事件溯源" in section


def test_system_prompt_renders_glossary():
    text = SYSTEM_PROMPT_TEMPLATE.format(glossary="术语占位")
    assert "术语占位" in text
    assert "features" in text
    assert PROMPT_VERSION == "docrelease/v1"


def test_build_user_prompt_includes_symbols_and_signals():
    chunk = {"name": "src/report", "files": [{
        "path": "src/report/export/index.ts", "status": "m", "added": 5, "removed": 2,
        "symbols_summary": "新增 1、删除 0、修改 0",
        "contract_signals": [{"message": "常量 X 由 1 变为 2"}],
        "lines": [{"t": "add", "s": "const a = 1;"}], "truncated": False}]}
    prompt = build_user_prompt(chunk)
    assert "src/report/export/index.ts" in prompt
    assert "符号变更：新增 1、删除 0、修改 0" in prompt
    assert "契约信号：常量 X 由 1 变为 2" in prompt
    assert "+const a = 1;" in prompt
```

- [ ] **Step 3: 运行测试确认失败**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests/test_glossary.py -q
```

Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.glossary'`。

- [ ] **Step 4: 实现 glossary.py 与 docrelease_v1.py**

`app/services/glossary.py`：

```python
"""术语表加载与命中匹配。加载一次后缓存，文件变更需重启服务。"""

import json
from functools import lru_cache
from pathlib import Path

GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "glossary.json"


@lru_cache(maxsize=1)
def load_glossary() -> dict:
    return json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))


def match_terms(text: str) -> list[str]:
    """返回文本中命中的术语名（按术语表顺序、去重）。"""
    lowered = text.lower()
    hits: list[str] = []
    for item in load_glossary()["terms"]:
        names = [item["term"], *item.get("aliases", [])]
        if any(n and n.lower() in lowered for n in names):
            hits.append(item["term"])
    return hits


def build_glossary_prompt_section() -> str:
    lines = []
    for item in load_glossary()["terms"]:
        aliases = "、".join(item.get("aliases", []))
        lines.append(f"- {item['term']}：{item['note']}（别名：{aliases}）")
    return "\n".join(lines)
```

`app/prompts/docrelease_v1.py`：

```python
"""docrelease/v1 提示词模板（输出结构化 JSON：features + highlights + confidence）。"""

PROMPT_VERSION = "docrelease/v1"

SYSTEM_PROMPT_TEMPLATE = """你是发布文档生成系统（DocRelease）的业务化改写引擎。
你的任务：把给定模块的代码变更（含符号级解析结果与契约信号）改写为发布文档用的功能点。

硬性要求：
1. 只输出一个 JSON 对象，不要输出任何解释或额外文字。
2. JSON 结构：
{{"features": [{{"tag": "新增功能|体验优化|缺陷修复|技术重构|破坏性变更",
  "risk": "高|中|低", "breaking": false, "title": "功能点标题（不超过 24 字）",
  "biz": "业务视角说明：对用户/运营意味着什么（2-3 句）",
  "tech": "技术视角说明：改了什么、怎么改的（2-3 句）",
  "visible": "用户可感知的变化，若无写「无」",
  "scope": "影响范围（页面/接口/模块）",
  "acceptance": "验收要点（可执行、可观察）",
  "action": "上线前需要做的事，若无写「无需操作」",
  "role": "主要干系角色：产品|研发|测试|运营|客服",
  "paths": ["涉及文件相对路径"]}}],
  "highlights": ["发布亮点短句（不超过 3 条）"],
  "confidence": 0.0 到 1.0 的数字}}
3. 合并重复功能点；宁缺毋滥，不确定的改动写成「技术重构」并降低 confidence。
4. 涉及删除、签名算法、登录/鉴权、接口路径变化的改动，breaking 置 true 并在 action 中强调。
5. 生成 biz 时必须使用以下术语口径：
{glossary}
"""

_STATUS_LABELS = {"a": "新增", "m": "修改", "d": "删除"}


def build_user_prompt(chunk: dict) -> str:
    lines = [f"模块：{chunk['name']}", f"变更文件（{len(chunk['files'])} 个）："]
    for f in chunk["files"]:
        label = _STATUS_LABELS.get(f["status"], "修改")
        lines.append(f"## 文件 {f['path']}（{label}，+{f['added']}/-{f['removed']}）")
        if f.get("symbols_summary"):
            lines.append(f"符号变更：{f['symbols_summary']}")
        for sig in f.get("contract_signals", []):
            lines.append(f"契约信号：{sig['message']}")
        lines.append("```diff")
        for line in f.get("lines", []):
            prefix = {"add": "+", "del": "-"}.get(line["t"], " ")
            lines.append(prefix + line["s"])
        if f.get("truncated"):
            lines.append("...（diff 已截断）")
        lines.append("```")
    lines.append("请输出 JSON。")
    return "\n".join(lines)
```

- [ ] **Step 5: 运行全部测试确认通过**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

Expected: 全部通过。

- [ ] **Step 6: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/backend
git commit -m 'feat(doc-release): Task 7 术语表与提示词模板'
```

---

## Task 8: 星语封装与 LLM 改写服务

**Files:**
- Create: `doc-release/backend/app/services/xingyu_api.py`
- Create: `doc-release/backend/app/services/llm_service.py`
- Modify: `doc-release/backend/tests/conftest.py`（增加全局 LLM 打桩 autouse fixture）
- Create: `doc-release/backend/tests/test_llm_service.py`

- [ ] **Step 1: 写 xingyu_api.py（复刻工作区已验证的网关调用形态）**

`app/services/xingyu_api.py`：

```python
"""星语大模型网关同步封装（requests），异步侧用 asyncio.to_thread 包装。

网关契约（已验证）：payload 仅 robotCode + chatMessages + requestId，无鉴权头；
多传字段（如 agent）会被网关拒绝。单次调用约 6~15 秒，超时用 settings.llm_timeout。
"""

import asyncio
import json
import uuid

import requests

from app.config import settings


def xingyu_chat(system_prompt: str, user_prompt: str) -> str:
    payload = {
        "robotCode": settings.robot_code,
        "chatMessages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "requestId": str(uuid.uuid4()),
    }
    resp = requests.post(
        settings.xingyu_url,
        json=payload,
        timeout=settings.llm_timeout,
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"星语网关请求失败：HTTP {resp.status_code}")
    data = resp.json()
    if str(data.get("status")) != "0":
        raise RuntimeError(f"星语网关返回错误：{json.dumps(data, ensure_ascii=False)[:300]}")
    contents = (data.get("data") or {}).get("contents") or []
    if not contents:
        raise RuntimeError("星语网关未返回内容")
    return contents[0].get("content", "")


async def generate_by_xingyu(system_prompt: str, user_prompt: str) -> str:
    return await asyncio.to_thread(xingyu_chat, system_prompt, user_prompt)
```

- [ ] **Step 2: 写失败测试 test_llm_service.py**

`tests/test_llm_service.py`：

```python
import json

import pytest

from app.services import llm_service


def _file(path, lines=3, status="m"):
    return {"path": path, "status": status, "added": 1, "removed": 1, "binary": False,
            "truncated": False,
            "lines": [{"t": "add", "s": f"const x{i} = {i};"} for i in range(lines)]}


def _changeset(files, modules=None, signals=None):
    return {"files": files, "stats": {}, "commits": [], "contract_signals": signals or [],
            "modules": modules or [{"name": "src", "files": [f["path"] for f in files]}]}


def test_extract_json_plain():
    assert llm_service.extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced_with_noise():
    text = '好的，结果如下：\n```json\n{"a": {"b": "}"}}\n```\n以上。'
    assert llm_service.extract_json(text) == {"a": {"b": "}"}}


def test_extract_json_raises_without_object():
    with pytest.raises(ValueError):
        llm_service.extract_json("没有 JSON")


def test_build_chunks_splits_by_module_and_limit():
    files = [_file(f"src/a/f{i}.ts") for i in range(10)] + [_file("src/b/g.ts")]
    cs = _changeset(files, modules=[
        {"name": "src/a", "files": [f["path"] for f in files[:10]]},
        {"name": "src/b", "files": ["src/b/g.ts"]},
    ])
    chunks = llm_service.build_chunks(cs, max_files=8)
    assert [c["name"] for c in chunks] == ["src/a·1", "src/a·2", "src/b"]


async def test_rewrite_success(monkeypatch):
    async def fake_chat(system, user):
        return json.dumps({
            "features": [{"title": "报表导出支持分片流式写出", "biz": "分片流式写出避免超时",
                          "tech": "新增 streamWrite", "tag": "新增功能",
                          "paths": ["src/report/export/stream.ts"]}],
            "highlights": ["导出稳定性提升"], "confidence": 0.92}, ensure_ascii=False)

    monkeypatch.setattr(llm_service, "_chat", fake_chat)
    cs = _changeset([_file("src/report/export/stream.ts")],
                    modules=[{"name": "src/report", "files": ["src/report/export/stream.ts"]}])
    out = await llm_service.rewrite_changes(cs)
    assert out["ok"] and not out["all_failed"]
    assert out["features"][0]["title"] == "报表导出支持分片流式写出"
    assert out["features"][0]["role"] == "研发"          # 默认字段补齐
    assert out["llm"]["confidence"] == 0.92
    assert out["llm"]["glossaryHits"] >= 1               # 命中「分片流式写出」
    assert "导出稳定性提升" in out["highlights"]


async def test_rewrite_degraded_when_all_fail(monkeypatch):
    async def bad_chat(system, user):
        raise RuntimeError("网关不可达")

    monkeypatch.setattr(llm_service, "_chat", bad_chat)
    out = await llm_service.rewrite_changes(_changeset([_file("src/a/x.ts")]))
    assert out["all_failed"] is True and out["ok"] is False
    assert out["features"][0]["title"].endswith("变更待人工确认")
    assert out["lowConfidence"]


async def test_rewrite_partial_failure_keeps_success(monkeypatch):
    async def sometimes(system, user):
        if "src/a/x.ts" in user:
            raise RuntimeError("超时")
        return json.dumps({"features": [{"title": "另一个模块的功能点", "biz": "b", "tech": "t"}],
                           "highlights": [], "confidence": 0.8}, ensure_ascii=False)

    monkeypatch.setattr(llm_service, "_chat", sometimes)
    cs = _changeset([_file("src/a/x.ts"), _file("src/b/y.ts")], modules=[
        {"name": "src/a", "files": ["src/a/x.ts"]},
        {"name": "src/b", "files": ["src/b/y.ts"]},
    ])
    out = await llm_service.rewrite_changes(cs)
    assert out["ok"] is True and out["all_failed"] is False
    assert any("src/a" in msg for msg in out["lowConfidence"])
    assert any(f["title"] == "另一个模块的功能点" for f in out["features"])


async def test_contract_signals_enter_highlights(monkeypatch):
    async def fake_chat(system, user):
        return json.dumps({"features": [{"title": "T", "biz": "b", "tech": "t"}],
                           "highlights": [], "confidence": 1.0}, ensure_ascii=False)

    monkeypatch.setattr(llm_service, "_chat", fake_chat)
    cs = _changeset([_file("src/pay/verify.ts")],
                    signals=[{"kind": "symbol_removed", "path": "src/pay/verify.ts",
                              "message": "导出符号 verifyCallback 已删除"}])
    out = await llm_service.rewrite_changes(cs)
    assert any("导出符号 verifyCallback 已删除" in h for h in out["highlights"])
```

- [ ] **Step 3: 运行测试确认失败**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests/test_llm_service.py -q
```

Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.llm_service'`。

- [ ] **Step 4: 实现 llm_service.py**

`app/services/llm_service.py`：

```python
"""LLM 业务化改写：分块 → 并发调用 → JSON 修复 → 合并与降级。"""

import asyncio
import json
import re

from app.config import settings
from app.prompts.docrelease_v1 import PROMPT_VERSION, SYSTEM_PROMPT_TEMPLATE, build_user_prompt
from app.services import glossary as glossary_svc
from app.services.errors import RunCancelled
from app.services.xingyu_api import generate_by_xingyu

_FEATURE_DEFAULTS: dict = {
    "tag": "技术重构", "risk": "中", "breaking": False, "title": "",
    "biz": "", "tech": "", "visible": "无", "scope": "", "acceptance": "",
    "action": "无需操作", "role": "研发", "paths": [],
}


def extract_json(text: str) -> dict:
    """从模型输出提取 JSON：剥离 code fence → 从首个 { 起做括号配平截取。"""
    t = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.S)
    if fence:
        t = fence.group(1)
    start = t.find("{")
    if start == -1:
        raise ValueError("输出中没有 JSON 对象")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(t)):
        ch = t[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(t[start:i + 1])
    raise ValueError("JSON 括号不配平")


def build_chunks(changeset: dict, max_files: int = 8, max_lines: int = 600) -> list[dict]:
    """按模块聚类分块；单块超限时按文件继续拆（同名追加序号）。"""
    files_by_path = {f["path"]: f for f in changeset["files"]}
    chunks: list[dict] = []
    for module in changeset["modules"]:
        group = [files_by_path[p] for p in module["files"] if p in files_by_path]
        current: list[dict] = []
        current_lines = 0
        for f in group:
            cost = max(len(f.get("lines", [])), 1)
            if current and (len(current) >= max_files or current_lines + cost > max_lines):
                chunks.append({"name": module["name"], "files": current})
                current, current_lines = [], 0
            current.append(f)
            current_lines += cost
        if current:
            chunks.append({"name": module["name"], "files": current})

    counts: dict[str, int] = {}
    for c in chunks:
        counts[c["name"]] = counts.get(c["name"], 0) + 1
    seen: dict[str, int] = {}
    for c in chunks:
        if counts[c["name"]] > 1:
            seen[c["name"]] = seen.get(c["name"], 0) + 1
            c["name"] = f"{c['name']}·{seen[c['name']]}"
    return chunks


async def _chat(system_prompt: str, user_prompt: str) -> str:
    if settings.llm_provider == "deepseek":
        return await _chat_deepseek(system_prompt, user_prompt)
    return await generate_by_xingyu(system_prompt, user_prompt)


async def _chat_deepseek(system_prompt: str, user_prompt: str) -> str:
    if not settings.deepseek_api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")
    import httpx

    async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
        resp = await client.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": "deepseek-chat",
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _rewrite_chunk(chunk: dict, sem: asyncio.Semaphore, system_prompt: str) -> dict:
    user_prompt = build_user_prompt(chunk)
    async with sem:
        last_error = ""
        for attempt in (1, 2):
            try:
                prompt = user_prompt
                if attempt == 2:
                    prompt += "\n\n注意：只输出 JSON 对象本身，不要任何解释文字。"
                text = await _chat(system_prompt, prompt)
                return {"ok": True, "chunk": chunk, "data": extract_json(text), "output": text}
            except Exception as exc:  # noqa: BLE001 —— 解析/请求失败均重试一次
                last_error = str(exc)
        return {"ok": False, "chunk": chunk, "error": last_error or "未知错误"}


async def rewrite_changes(changeset: dict, cancel_check=None) -> dict:
    """把变更集改写为功能点结构；cancel_check 在分块启动前检查（取消生效点）。"""
    chunks = build_chunks(changeset)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(glossary=glossary_svc.build_glossary_prompt_section())
    sem = asyncio.Semaphore(max(1, settings.llm_max_concurrency))
    tasks = []
    for c in chunks:
        if cancel_check is not None and cancel_check():
            raise RunCancelled("运行已取消")
        tasks.append(asyncio.create_task(_rewrite_chunk(c, sem, system_prompt)))
    results = await asyncio.gather(*tasks)
    return merge_results(results, changeset)


def _fill_feature_defaults(f: dict) -> dict:
    out = dict(_FEATURE_DEFAULTS)
    if isinstance(f, dict):
        out.update({k: v for k, v in f.items() if k in _FEATURE_DEFAULTS})
    out["title"] = str(out.get("title") or "").strip()
    if not isinstance(out.get("paths"), list):
        out["paths"] = []
    return out


def _degraded_feature(chunk: dict, error: str) -> dict:
    return _fill_feature_defaults({
        "tag": "技术重构", "risk": "中",
        "title": f"{chunk['name']} 变更待人工确认",
        "biz": "该模块的变更未能自动生成业务描述，请在发布前人工确认影响面。",
        "tech": "LLM 改写失败：" + (error or "")[:120],
        "visible": "待确认", "scope": chunk["name"],
        "acceptance": "人工核对 diff 与符号变更",
        "action": "人工确认该模块变更内容",
        "paths": [f["path"] for f in chunk["files"]][:8],
    })


def merge_results(results: list[dict], changeset: dict) -> dict:
    features: list[dict] = []
    seen_titles: set[str] = set()
    highlights: list[str] = []
    low_confidence: list[str] = []
    confidences: list[float] = []
    input_chars = output_chars = 0
    ok_count = 0
    chunk_logs: list[dict] = []

    for r in results:
        chunk = r["chunk"]
        if not r["ok"]:
            error = r.get("error", "")
            features.append(_degraded_feature(chunk, error))
            low_confidence.append(f"{chunk['name']}：LLM 改写失败（{error[:80]}）")
            chunk_logs.append({"chunk": chunk["name"], "ok": False, "error": error[:200]})
            continue
        ok_count += 1
        data = r["data"]
        for raw in data.get("features") or []:
            f = _fill_feature_defaults(raw)
            if not f["title"] or f["title"] in seen_titles:
                continue
            seen_titles.add(f["title"])
            features.append(f)
        for h in data.get("highlights") or []:
            h = str(h).strip()
            if h and h not in highlights:
                highlights.append(h)
        conf = data.get("confidence")
        if isinstance(conf, (int, float)):
            confidences.append(float(conf))
        input_chars += len(build_user_prompt(chunk))
        output_chars += len(r.get("output") or "")
        chunk_logs.append({"chunk": chunk["name"], "ok": True,
                           "features": len(data.get("features") or [])})

    for sig in changeset.get("contract_signals", []):
        text = f"契约变更：{sig['message']}"
        if text not in highlights:
            highlights.append(text)

    glossary_hits = len(glossary_svc.match_terms(
        " ".join(f"{f['title']} {f['biz']} {f['tech']}" for f in features)))

    all_failed = ok_count == 0
    model = ("deepseek-chat" if settings.llm_provider == "deepseek"
             else f"xingyu:{settings.robot_code}")
    return {
        "ok": not all_failed,
        "all_failed": all_failed,
        "features": features,
        "highlights": highlights,
        "lowConfidence": low_confidence,
        "chunk_logs": chunk_logs,
        "llm": {
            "provider": settings.llm_provider,
            "model": model,
            "prompt": PROMPT_VERSION,
            "confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
            "inputChars": input_chars,
            "outputChars": output_chars,
            "glossaryHits": glossary_hits,
            "lowConfidence": low_confidence,
        },
    }
```

- [ ] **Step 5: conftest.py 增加全局 LLM 打桩（保证后续测试离线可跑）**

在 `tests/conftest.py` 末尾追加：

```python
@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    """默认把所有测试的 LLM 调用替换为固定 JSON，保持离线可跑；
    单个测试可用自己的 monkeypatch 覆盖（后设置的生效）。"""
    import json as _json

    from app.services import llm_service

    async def fake_chat(system_prompt: str, user_prompt: str) -> str:
        return _json.dumps({
            "features": [{"tag": "新增功能", "risk": "低", "breaking": False,
                          "title": "自动生成的功能点", "biz": "业务说明", "tech": "技术说明",
                          "visible": "无", "scope": "测试模块", "acceptance": "可验收",
                          "action": "无需操作", "role": "研发", "paths": []}],
            "highlights": [], "confidence": 0.9}, ensure_ascii=False)

    monkeypatch.setattr(llm_service, "_chat", fake_chat)
```

- [ ] **Step 6: 运行全部测试确认通过**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

Expected: 全部通过（含 test_llm_service 的 8 个用例）。

- [ ] **Step 7: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/backend
git commit -m 'feat(doc-release): Task 8 星语封装与 LLM 改写服务'
```

---

## Task 9: renderers（三类产物确定性渲染）

**Files:**
- Create: `doc-release/backend/app/services/renderers.py`
- Create: `doc-release/backend/tests/test_renderers.py`

**约定：** 渲染器是纯函数，入参为 `result`（存入 `run.result` 的完整结构）与 `opts`（`{"tone": "business"|"tech", "mask": bool}`）。tone/mask 只在渲染期生效，不改变存储的结构化结果。

- [ ] **Step 1: 写失败测试 test_renderers.py**

`tests/test_renderers.py`：

```python
import json

from app.services import renderers as r

RESULT = {
    "features": [
        {"tag": "缺陷修复", "risk": "中", "breaking": False, "title": "报表导出超时修复",
         "biz": "导出口径改为分片流式写出，超时问题解决", "tech": "新增 streamWrite 分片写入",
         "visible": "导出不再超时", "scope": "报表导出", "acceptance": "1 万行导出 30 秒内完成",
         "action": "无需操作", "role": "研发", "paths": ["src/report/export/stream.ts"]},
        {"tag": "破坏性变更", "risk": "高", "breaking": True, "title": "v1 下单接口下线",
         "biz": "老接口不再受理流量", "tech": "CreateOrderV1 删除，返回 410",
         "visible": "老客户端调用失败", "scope": "对外 API", "acceptance": "监控无 /v1 流量",
         "action": "确认存量客户端已迁移", "role": "产品", "paths": ["api/legacy/order.go"]},
    ],
    "highlights": ["导出稳定性提升"],
    "lowConfidence": [],
    "contractSignals": [{"kind": "route_removed", "path": "api/legacy/order.go",
                         "message": "接口路径 /v1/order/create 已移除或变更"}],
    "llm": {"provider": "xingyu", "model": "xingyu:ROBOT_00000149", "prompt": "docrelease/v1",
            "confidence": 0.9, "inputChars": 1200, "outputChars": 800, "glossaryHits": 2,
            "lowConfidence": []},
    "meta": {"runId": "run-123", "repoName": "order-center", "version": "v2.13.4",
             "branch": "main", "headShort": "abc1234", "range": "v2.13.3..v2.13.4",
             "trigger": "手动触发", "generatedAt": "2026-10-14 12:00:00",
             "stats": {"commits": 3, "files": 4, "modules": 1, "added": 51, "removed": 16, "days": 2},
             "modules": ["src/report"], "pipeline": [{"name": "定位仓库与变更范围", "ok": True, "ms": 120}]},
}


def test_checklist_has_bom_header_and_rows():
    text = r.render_checklist(RESULT, {"tone": "business", "mask": False})
    assert text.startswith("\ufeff")
    lines = text.strip().splitlines()
    assert lines[0].lstrip("\ufeff").startswith("序号,版本,标签")
    assert "报表导出超时修复" in lines[1]
    assert len(lines) == 3


def test_checklist_tone_switches_explanation():
    biz = r.render_checklist(RESULT, {"tone": "business"})
    tech = r.render_checklist(RESULT, {"tone": "tech"})
    assert "分片流式写出，超时问题解决" in biz
    assert "新增 streamWrite" in tech


def test_checklist_mask_hides_paths():
    text = r.render_checklist(RESULT, {"tone": "business", "mask": True})
    assert "src/report/export/stream.ts" not in text
    assert "…/export/stream.ts" in text


def test_checklist_quotes_commas():
    result = json.loads(json.dumps(RESULT))
    result["features"][0]["title"] = "标题,带逗号"
    text = r.render_checklist(result, {})
    assert '"标题,带逗号"' in text


def test_document_sections():
    text = r.render_document(RESULT, {"tone": "business", "mask": False})
    for section in ["版本概览", "发布亮点", "功能清单", "破坏性变更", "涉及模块与文件",
                    "验收清单", "上线操作步骤", "溯源说明"]:
        assert section in text
    assert "确认存量客户端已迁移" in text


def test_trace_structure_and_sizes():
    text = r.render_trace(RESULT, {"tone": "business", "mask": False},
                          sizes={"checklist": 1000, "document": 2000, "trace": 3000})
    data = json.loads(text)
    assert data["runId"] == "run-123"
    assert data["generator"] == "释文 DocRelease"
    assert data["trigger"]["mode"] == "manual"
    assert data["range"]["base"] == "v2.13.3" and data["range"]["commit"] == "abc1234"
    assert data["confidence"] == 0.9
    assert {a["kind"]: a["bytes"] for a in data["artifacts"]} == {
        "checklist": 1000, "document": 2000, "trace": 3000}
    assert any(s["kind"] == "route_removed" for s in data["contractSignals"])


def test_trace_mask_masks_commit_and_paths():
    data = json.loads(r.render_trace(RESULT, {"tone": "business", "mask": True}))
    assert data["range"]["commit"] == "abc****"
    assert data["features"][0]["paths"] == ["…/export/stream.ts"]
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests/test_renderers.py -q
```

Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.renderers'`。

- [ ] **Step 3: 实现 renderers.py**

`app/services/renderers.py`：

```python
"""三类产物确定性渲染（纯函数）：功能点清单 CSV / 产品文档 MD / 溯源文件 JSON。

tone（业务/技术）与 mask（脱敏）只在渲染期应用，不改变结构化结果。
"""

import json

GENERATOR_NAME = "释文 DocRelease"


def _mask_path(path: str) -> str:
    parts = (path or "").replace("\\", "/").split("/")
    if len(parts) <= 2:
        return path
    return "/".join(["…"] + parts[-2:])


def _mask_commit(short: str) -> str:
    short = short or ""
    return f"{short[:3]}****" if len(short) > 3 else short


def _paths(f: dict, mask: bool) -> list[str]:
    return [(_mask_path(p) if mask else p) for p in (f.get("paths") or [])]


def _explain(f: dict, tone: str) -> str:
    return f.get("tech", "") if tone == "tech" else f.get("biz", "")


def _csv_cell(value) -> str:
    s = "" if value is None else str(value)
    if any(ch in s for ch in [",", '"', "\n", "\r"]):
        return '"' + s.replace('"', '""') + '"'
    return s


def render_checklist(result: dict, opts: dict) -> str:
    meta = result["meta"]
    tone = opts.get("tone", "business")
    mask = bool(opts.get("mask", False))
    header = ["序号", "版本", "标签", "风险", "破坏性", "功能点", "说明",
              "影响范围", "验收要点", "上线动作", "负责角色", "涉及文件"]
    rows = [header]
    for i, f in enumerate(result.get("features", []), start=1):
        rows.append([
            str(i), meta["version"], f.get("tag", ""), f.get("risk", ""),
            "是" if f.get("breaking") else "否", f.get("title", ""), _explain(f, tone),
            f.get("scope", ""), f.get("acceptance", ""), f.get("action", ""),
            f.get("role", ""), "；".join(_paths(f, mask)),
        ])
    lines = [",".join(_csv_cell(c) for c in row) for row in rows]
    return "\ufeff" + "\r\n".join(lines) + "\r\n"


def render_document(result: dict, opts: dict) -> str:
    meta = result["meta"]
    stats = meta.get("stats", {})
    llm = result.get("llm", {})
    tone = opts.get("tone", "business")
    mask = bool(opts.get("mask", False))
    features = result.get("features", [])
    commit = _mask_commit(meta["headShort"]) if mask else meta["headShort"]

    L: list[str] = []
    L.append(f"# {meta['version']} 发布说明")
    L.append("")
    L.append("## 一、版本概览")
    L.append("")
    L.append(f"- 仓库：{meta['repoName']}（分支 {meta['branch']}）")
    L.append(f"- 变更范围：`{meta['range']}`，头部提交 `{commit}`")
    L.append(f"- 变更规模：{stats.get('commits', 0)} 个提交 · {stats.get('files', 0)} 个文件 · "
             f"+{stats.get('added', 0)}/-{stats.get('removed', 0)} 行 · 跨度 {stats.get('days', 0)} 天")
    L.append(f"- 生成时间：{meta['generatedAt']}（{meta['trigger']}）")
    L.append(f"- 功能点：{len(features)} 项，其中破坏性变更 {sum(1 for f in features if f.get('breaking'))} 项")
    L.append("")

    L.append("## 二、发布亮点")
    L.append("")
    for h in result.get("highlights") or []:
        L.append(f"- {h}")
    if not result.get("highlights"):
        L.append("- （无）")
    L.append("")

    L.append("## 三、功能清单")
    L.append("")
    for i, f in enumerate(features, start=1):
        L.append(f"### {i}. {f.get('title', '')}")
        L.append("")
        L.append(f"- 标签：{f.get('tag', '')}｜风险：{f.get('risk', '')}｜"
                 f"破坏性变更：{'是' if f.get('breaking') else '否'}｜负责角色：{f.get('role', '')}")
        L.append(f"- 业务说明：{f.get('biz', '')}")
        L.append(f"- 技术说明：{f.get('tech', '')}")
        L.append(f"- 用户可见变化：{f.get('visible', '')}")
        L.append(f"- 影响范围：{f.get('scope', '')}")
        L.append(f"- 上线动作：{f.get('action', '')}")
        paths = _paths(f, mask)
        if paths:
            L.append(f"- 涉及文件：{'、'.join(paths)}")
        L.append("")

    L.append("## 四、破坏性变更与升级指引")
    L.append("")
    breaking = [f for f in features if f.get("breaking")]
    if breaking:
        for f in breaking:
            L.append(f"- **{f.get('title', '')}**：{f.get('biz', '')}（上线动作：{f.get('action', '')}）")
    else:
        L.append("本版本无破坏性变更。")
    L.append("")

    L.append("## 五、涉及模块与文件")
    L.append("")
    for m in meta.get("modules", []):
        L.append(f"- {m}")
    if not meta.get("modules"):
        L.append("- （无）")
    L.append("")

    L.append("## 六、验收清单")
    L.append("")
    for f in features:
        L.append(f"- [ ] {f.get('title', '')}：{f.get('acceptance', '')}")
    L.append("")

    L.append("## 七、上线操作步骤")
    L.append("")
    actions = [f"{f.get('title', '')}：{f.get('action', '')}"
               for f in features if f.get("action") and f.get("action") != "无需操作"]
    if actions:
        for i, a in enumerate(actions, start=1):
            L.append(f"{i}. {a}")
    else:
        L.append("无需额外操作。")
    L.append("")

    L.append("## 八、溯源说明")
    L.append("")
    L.append(f"- 运行 ID：`{meta['runId']}`（生成器：{GENERATOR_NAME}）")
    L.append(f"- 改写引擎：{llm.get('provider', '')} / {llm.get('model', '')}，提示词版本 {llm.get('prompt', '')}")
    L.append(f"- 输入 {llm.get('inputChars', 0)} 字符，输出 {llm.get('outputChars', 0)} 字符，"
             f"术语命中 {llm.get('glossaryHits', 0)} 处，置信度 {llm.get('confidence', 0)}")
    if result.get("lowConfidence"):
        L.append("- 需人工复核：")
        for item in result["lowConfidence"]:
            L.append(f"  - {item}")
    L.append(f"- 展示口径：{'技术视角' if tone == 'tech' else '业务视角'}"
             f"{'，已开启脱敏' if mask else ''}")
    L.append("")
    return "\n".join(L)


def render_trace(result: dict, opts: dict, sizes: dict | None = None) -> str:
    meta = result["meta"]
    llm = result.get("llm", {})
    mask = bool(opts.get("mask", False))
    sizes = sizes or {}
    data = {
        "traceVersion": "1.0",
        "runId": meta["runId"],
        "generator": GENERATOR_NAME,
        "generatedAt": meta["generatedAt"],
        "trigger": {"mode": "manual", "label": meta["trigger"]},
        "range": {
            "repo": meta["repoName"],
            "base": meta["range"].split("..")[0],
            "head": meta["range"].split("..")[-1],
            "branch": meta["branch"],
            "commit": _mask_commit(meta["headShort"]) if mask else meta["headShort"],
        },
        "pipeline": meta.get("pipeline", []),
        "llm": {
            "provider": llm.get("provider", ""),
            "model": llm.get("model", ""),
            "prompt": llm.get("prompt", ""),
            "inputChars": llm.get("inputChars", 0),
            "outputChars": llm.get("outputChars", 0),
            "glossaryHits": llm.get("glossaryHits", 0),
        },
        "confidence": llm.get("confidence", 0),
        "changes": meta.get("stats", {}),
        "modules": meta.get("modules", []),
        "features": [
            {"id": f"F{i}", "title": f.get("title", ""), "tag": f.get("tag", ""),
             "risk": f.get("risk", ""), "breaking": bool(f.get("breaking")),
             "paths": _paths(f, mask)}
            for i, f in enumerate(result.get("features", []), start=1)
        ],
        "contractSignals": result.get("contractSignals", []),
        "lowConfidence": result.get("lowConfidence", []),
        "artifacts": [
            {"kind": "checklist", "file": "checklist.csv", "bytes": sizes.get("checklist", 0)},
            {"kind": "document", "file": "product-doc.md", "bytes": sizes.get("document", 0)},
            {"kind": "trace", "file": "trace.json", "bytes": sizes.get("trace", 0)},
        ],
        "tone": opts.get("tone", "business"),
        "masked": mask,
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def render_trace_stable(result: dict, opts: dict,
                        base_sizes: dict | None = None, rounds: int = 3) -> tuple[str, dict]:
    """trace 内嵌自身字节数：两遍迭代到稳定（位数变化最多再迭代一次）。"""
    sizes = dict(base_sizes or {})
    sizes.setdefault("trace", 0)
    text = ""
    for _ in range(rounds):
        text = render_trace(result, opts, sizes)
        actual = len(text.encode("utf-8"))
        if actual == sizes["trace"]:
            break
        sizes["trace"] = actual
    return text, sizes
```

- [ ] **Step 4: 运行全部测试确认通过**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

Expected: 全部通过。

- [ ] **Step 5: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/backend
git commit -m 'feat(doc-release): Task 9 三类产物确定性渲染'
```

---

## Task 10: 归档服务与五步流水线

**Files:**
- Create: `doc-release/backend/app/services/archive_service.py`
- Create: `doc-release/backend/app/services/pipeline_service.py`
- Modify: `doc-release/backend/tests/conftest.py`（autouse 注入 pipeline 会话工厂与归档根目录）
- Create: `doc-release/backend/tests/test_pipeline.py`

- [ ] **Step 1: 写 archive_service.py**

`app/services/archive_service.py`：

```python
"""产物归档：写入 <archive_root>/docs/release/<version>/ 与 runId 绑定的删除保护。"""

import json
from pathlib import Path

from app.services.errors import ServiceError


def archive_dir_for(archive_root: Path, version: str) -> Path:
    return Path(archive_root) / "docs" / "release" / version


def write_artifacts(archive_root: Path, version: str, files: dict[str, str]) -> dict[str, Path]:
    """写入三类产物（同版本覆盖）；单文件写入失败重试一次。"""
    target = archive_dir_for(archive_root, version)
    target.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for filename, content in files.items():
        path = target / filename
        last_error: Exception | None = None
        for _ in range(2):
            try:
                path.write_text(content, encoding="utf-8")
                last_error = None
                break
            except OSError as exc:
                last_error = exc
        if last_error is not None:
            raise ServiceError(f"归档写入失败：{filename}（{last_error}）")
        written[filename] = path
    return written


def delete_archive_if_owned(archive_root: Path, version: str, run_id: str) -> bool:
    """删除归档目录，但仅当 trace.json.runId 与目标运行一致（防误删同版本归档）。"""
    target = archive_dir_for(archive_root, version)
    trace_path = target / "trace.json"
    if not trace_path.exists():
        return False
    try:
        data = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if data.get("runId") != run_id:
        return False
    for child in target.iterdir():
        if child.is_file():
            child.unlink()
    target.rmdir()
    return True
```

- [ ] **Step 2: 写失败测试 test_pipeline.py**

`tests/test_pipeline.py`：

```python
import json

import pytest
from sqlalchemy import func, select

from app.models import Artifact, Repo, Run
from app.models.run import blank_steps
from app.services import archive_service, git_service, llm_service, pipeline_service
from tests.gitfix import commit, init_repo, tag, write_files


@pytest.fixture
def work_repo(tmp_path):
    r = init_repo(tmp_path)
    write_files(r, {"src/a.ts": "export const A = 1;\n"})
    commit(r, "init")
    tag(r, "v1.0.0")
    write_files(r, {"src/a.ts": "export const A = 2;\nexport function run() {\n  return A;\n}\n"})
    commit(r, "feat: a", date="2026-08-21 09:00:00 +0800")
    tag(r, "v1.1.0")
    return r


async def _make_run(db_session, repo_path, version="v1.1.0", base="v1.0.0"):
    repo = Repo(name="work", path=str(repo_path), is_sample=False)
    db_session.add(repo)
    await db_session.commit()
    run = Run(repo_id=repo.id, base_ref=base, head_ref=version, version_label=version)
    run.steps = blank_steps()
    db_session.add(run)
    await db_session.commit()
    return run


def test_delete_archive_requires_owner(tmp_path):
    root = tmp_path / "ar"
    archive_service.write_artifacts(root, "v1.0.0", {
        "trace.json": json.dumps({"runId": "r1"}), "checklist.csv": "x"})
    assert archive_service.delete_archive_if_owned(root, "v1.0.0", "r2") is False
    assert archive_service.archive_dir_for(root, "v1.0.0").exists()
    assert archive_service.delete_archive_if_owned(root, "v1.0.0", "r1") is True
    assert not archive_service.archive_dir_for(root, "v1.0.0").exists()


async def test_execute_run_success(work_repo, db_session, archive_root):
    run = await _make_run(db_session, work_repo)
    q = pipeline_service.bus.subscribe(run.id)
    await pipeline_service.execute_run(run.id)
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    pipeline_service.bus.unsubscribe(run.id, q)

    await db_session.refresh(run)
    assert run.status == "succeeded"
    assert [s["status"] for s in run.steps] == ["done"] * 5
    assert all(s.get("duration_ms") is not None for s in run.steps)
    assert run.result["features"][0]["title"] == "自动生成的功能点"  # conftest 打桩输出
    assert run.result["meta"]["range"] == "v1.0.0..v1.1.0"
    assert run.result["meta"]["branch"] == "main"
    assert run.result["meta"]["modules"] == ["src"]

    count = (await db_session.execute(select(func.count()).select_from(Artifact))).scalar_one()
    assert count == 3

    target = archive_root / "docs" / "release" / "v1.1.0"
    assert (target / "checklist.csv").exists()
    assert (target / "product-doc.md").exists()
    trace = json.loads((target / "trace.json").read_text(encoding="utf-8"))
    assert trace["runId"] == run.id
    assert {a["kind"]: a["bytes"] for a in trace["artifacts"]} == {
        "checklist": (target / "checklist.csv").stat().st_size,
        "document": (target / "product-doc.md").stat().st_size,
        "trace": (target / "trace.json").stat().st_size,
    }

    names = [e["event"] for e in events]
    assert names.count("step") >= 10          # 每步 active + done
    assert names[-1] == "done"
    assert events[-1]["data"]["status"] == "succeeded"


async def test_execute_run_llm_all_failed(work_repo, db_session, monkeypatch):
    async def bad_chat(system, user):
        raise RuntimeError("网关不可达")

    monkeypatch.setattr(llm_service, "_chat", bad_chat)
    run = await _make_run(db_session, work_repo)
    await pipeline_service.execute_run(run.id)
    await db_session.refresh(run)
    assert run.status == "failed"
    assert "LLM 改写全部失败" in run.error
    assert run.steps[3]["status"] == "failed"
    assert run.steps[4]["status"] == "pending"
    assert run.logs and run.logs[-1]["channel"] == "error"


async def test_execute_run_cancelled_before_start(work_repo, db_session):
    run = await _make_run(db_session, work_repo)
    pipeline_service.cancel_run(run.id)
    await pipeline_service.execute_run(run.id)
    await db_session.refresh(run)
    assert run.status == "cancelled"
    assert all(s["status"] == "pending" for s in run.steps)
    assert any("取消" in log["tag"] for log in run.logs)


async def test_execute_run_cancelled_between_steps(work_repo, db_session, monkeypatch):
    run = await _make_run(db_session, work_repo)
    original = git_service.list_refs

    def cancelling_list_refs(path):
        pipeline_service.cancel_run(run.id)   # 在步骤 1 执行中触发取消
        return original(path)

    monkeypatch.setattr(git_service, "list_refs", cancelling_list_refs)
    await pipeline_service.execute_run(run.id)
    await db_session.refresh(run)
    assert run.status == "cancelled"
    assert run.steps[0]["status"] == "done"       # 步骤 1 正常完成
    assert all(s["status"] == "pending" for s in run.steps[1:])
```

- [ ] **Step 3: 运行测试确认失败**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests/test_pipeline.py -q
```

Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.pipeline_service'`。

- [ ] **Step 4: conftest.py 追加 pipeline 注入 fixture**

在 `tests/conftest.py` 末尾追加（注意放在文件最后，保持已有 fixture 不变）：

```python
@pytest.fixture(autouse=True)
def archive_root(session_maker, tmp_path_factory):
    """把 pipeline 的会话工厂指向测试库、归档根目录指向临时目录（每个测试隔离）。"""
    from app.services import pipeline_service

    pipeline_service.set_session_factory(session_maker)
    root = tmp_path_factory.mktemp("archive")
    pipeline_service.set_archive_root(root)
    pipeline_service._live_states.clear()
    pipeline_service._cancelled.clear()
    return root
```

- [ ] **Step 5: 实现 pipeline_service.py**

`app/services/pipeline_service.py`：

```python
"""五步流水线编排、运行状态机、进程内事件总线与取消。

执行模型：API 层 create_task 调用 execute_run；execute_run 自带数据库会话
（与请求生命周期解耦），运行期状态存在内存 _live_states 供 SSE snapshot 使用，
每个步骤结束时落库，结束时整体落库（logs/result/status）。
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Artifact, Repo, Run
from app.models.run import blank_steps
from app.services import archive_service, git_service, llm_service, parser_service, renderers
from app.services.errors import GitError, RunCancelled, ServiceError

logger = logging.getLogger(__name__)

_PIPELINE_MAX_LINES = 600

_session_factory: Callable = AsyncSessionLocal
_archive_root: Path = Path(settings.archive_dir)
_live_states: dict[str, dict] = {}
_cancelled: set[str] = set()


def set_session_factory(factory: Callable) -> None:
    global _session_factory
    _session_factory = factory


def set_archive_root(root: Path) -> None:
    global _archive_root
    _archive_root = Path(root)


class RunEventBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(run_id, set()).add(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(run_id)
        if subs is not None:
            subs.discard(q)
            if not subs:
                self._subs.pop(run_id, None)

    def publish(self, run_id: str, event: dict) -> None:
        for q in list(self._subs.get(run_id, ())):
            q.put_nowait(event)


bus = RunEventBus()


def get_live_state(run_id: str) -> dict | None:
    return _live_states.get(run_id)


def is_cancelled(run_id: str) -> bool:
    return run_id in _cancelled


def cancel_run(run_id: str) -> bool:
    """标记取消；实际生效点在每步开始与 LLM 分块启动前。"""
    _cancelled.add(run_id)
    return True


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _log(run_id: str, state: dict, channel: str, tag: str, message: str) -> None:
    line = {"ts": _now(), "channel": channel, "tag": tag, "message": message}
    state["logs"].append(line)
    bus.publish(run_id, {"event": "log", "data": line})


async def _persist_progress(db, run: Run, state: dict) -> None:
    run.current_step = state["current_step"]
    run.steps = state["steps"]
    if state.get("stats"):
        run.stats = state["stats"]
    await db.commit()


async def _run_step(run_id: str, run: Run, state: dict, db, index: int, fn):
    if is_cancelled(run_id):
        raise RunCancelled("运行已取消")
    step = state["steps"][index]
    total_steps = len(state["steps"])
    step["status"] = "active"
    step["started_at"] = _now()
    state["current_step"] = index
    bus.publish(run_id, {"event": "step", "data": {"index": index, "name": step["name"], "status": "active"}})
    bus.publish(run_id, {"event": "progress", "data": {"percent": int(index / total_steps * 100)}})
    started = datetime.now()
    try:
        result = await fn()
    except RunCancelled:
        step["status"] = "pending"
        raise
    except Exception:
        step["status"] = "failed"
        step["finished_at"] = _now()
        bus.publish(run_id, {"event": "step", "data": {"index": index, "name": step["name"], "status": "failed"}})
        raise
    step["status"] = "done"
    step["finished_at"] = _now()
    step["duration_ms"] = int((datetime.now() - started).total_seconds() * 1000)
    bus.publish(run_id, {"event": "step", "data": {"index": index, "name": step["name"],
                                                   "status": "done", "duration_ms": step["duration_ms"]}})
    bus.publish(run_id, {"event": "progress", "data": {"percent": int((index + 1) / total_steps * 100)}})
    await _persist_progress(db, run, state)
    return result


async def _finish_cancelled(db, run: Run, state: dict, run_id: str) -> None:
    _cancelled.discard(run_id)
    state["status"] = "cancelled"
    state["error"] = "运行已取消"
    _log(run_id, state, "warn", "取消", "运行已被用户取消")
    run.status = "cancelled"
    run.steps = state["steps"]
    run.logs = state["logs"]
    run.error = "运行已取消"
    run.finished_at = datetime.utcnow()
    await db.commit()
    bus.publish(run_id, {"event": "done", "data": {"status": "cancelled", "result": None}})


async def _finish_failed(db, run: Run, state: dict, run_id: str, exc: Exception) -> None:
    message = str(exc) or exc.__class__.__name__
    if isinstance(exc, GitError):
        message = f"Git 错误：{message}"
    state["status"] = "failed"
    state["error"] = message
    _log(run_id, state, "error", "失败", message)
    run.status = "failed"
    run.steps = state["steps"]
    run.logs = state["logs"]
    if state.get("stats"):
        run.stats = state["stats"]
    run.error = message
    run.finished_at = datetime.utcnow()
    await db.commit()
    bus.publish(run_id, {"event": "error", "data": {"message": message}})
    bus.publish(run_id, {"event": "done", "data": {"status": "failed", "result": None}})


async def execute_run(run_id: str) -> None:
    """后台任务：执行五步流水线，异常/取消均完整落库并广播。"""
    async with _session_factory() as db:
        run = await db.get(Run, run_id)
        if run is None:
            return
        repo = await db.get(Repo, run.repo_id)
        if repo is None:
            run.status = "failed"
            run.error = "仓库记录不存在"
            run.finished_at = datetime.utcnow()
            await db.commit()
            bus.publish(run_id, {"event": "error", "data": {"message": "仓库记录不存在"}})
            bus.publish(run_id, {"event": "done", "data": {"status": "failed", "result": None}})
            return

        state = {"status": "running", "current_step": -1, "steps": blank_steps(),
                 "logs": [], "stats": {}, "result": None, "error": None}
        _live_states[run_id] = state
        run.status = "running"
        run.steps = state["steps"]
        await db.commit()

        try:
            if is_cancelled(run_id):
                raise RunCancelled("运行已取消")

            async def step1():
                git_service.resolve_ref(repo.path, run.base_ref)
                head_sha = git_service.resolve_ref(repo.path, run.head_ref)
                commits = git_service.list_commits(repo.path, run.base_ref, run.head_ref)
                refs = git_service.list_refs(repo.path)
                _log(run_id, state, "step", "范围",
                     f"解析 {run.base_ref}..{run.head_ref}，头部 {head_sha[:7]}")
                _log(run_id, state, "step", "提交", f"范围内 {len(commits)} 个提交")
                return {"head_sha": head_sha, "commits": commits,
                        "branch": refs["default_branch"] or "main"}

            range_info = await _run_step(run_id, run, state, db, 0, step1)

            async def step2():
                cs = git_service.collect_diff(repo.path, run.base_ref, run.head_ref,
                                              max_lines=_PIPELINE_MAX_LINES)
                state["stats"] = cs["stats"]
                _log(run_id, state, "step", "规模",
                     f"{cs['stats']['files']} 个文件，+{cs['stats']['added']}/-{cs['stats']['removed']} 行，"
                     f"{cs['stats']['modules']} 个模块")
                for m in cs["modules"]:
                    _log(run_id, state, "step", "模块", f"{m['name']}（{len(m['files'])} 个文件）")
                return cs

            changeset = await _run_step(run_id, run, state, db, 1, step2)

            async def step3():
                total = {"added": 0, "removed": 0, "changed": 0}
                signals: list[dict] = []
                degraded = 0
                for f in changeset["files"]:
                    if f.get("binary"):
                        f["ast"] = None
                        f["contract_signals"] = []
                        continue
                    base_src = (git_service.show_file(repo.path, run.base_ref, f["path"])
                                if f["status"] != "a" else "")
                    head_src = (git_service.show_file(repo.path, run.head_ref, f["path"])
                                if f["status"] != "d" else "")
                    parsed = parser_service.parse_file_pair(f["path"], base_src, head_src,
                                                            f.get("lines", []))
                    f["ast"] = parsed
                    f["contract_signals"] = parsed["contract_signals"]
                    if parsed["degraded"]:
                        degraded += 1
                    for key in total:
                        total[key] += len(parsed["symbols"].get(key, []))
                    signals.extend(parsed["contract_signals"])
                changeset["contract_signals"] = signals
                _log(run_id, state, "step", "符号",
                     f"新增 {total['added']} · 修改 {total['changed']} · 删除 {total['removed']}")
                for sig in signals:
                    _log(run_id, state, "warn", "契约", sig["message"])
                if degraded:
                    _log(run_id, state, "warn", "降级",
                         f"{degraded} 个文件未解析到符号级（已降级为文件级信号）")
                return {"total": total, "signals": signals, "degraded": degraded}

            await _run_step(run_id, run, state, db, 2, step3)

            async def step4():
                outcome = await llm_service.rewrite_changes(
                    changeset, cancel_check=lambda: is_cancelled(run_id))
                if outcome["all_failed"]:
                    raise ServiceError("LLM 改写全部失败，运行终止")
                for cl in outcome["chunk_logs"]:
                    if cl["ok"]:
                        _log(run_id, state, "step", "分块", f"{cl['chunk']}：生成 {cl['features']} 个功能点")
                    else:
                        _log(run_id, state, "warn", "分块", f"{cl['chunk']}：改写失败（{cl['error'][:60]}）")
                for item in outcome["lowConfidence"]:
                    _log(run_id, state, "warn", "复核", item)
                _log(run_id, state, "step", "改写",
                     f"功能点 {len(outcome['features'])} 个 · 置信度 {outcome['llm']['confidence']} · "
                     f"术语命中 {outcome['llm']['glossaryHits']} 处")
                return outcome

            outcome = await _run_step(run_id, run, state, db, 3, step4)

            async def step5():
                meta = {
                    "runId": run.id,
                    "repoName": repo.name,
                    "version": run.version_label,
                    "branch": range_info["branch"],
                    "headShort": range_info["head_sha"][:7],
                    "range": f"{run.base_ref}..{run.head_ref}",
                    "trigger": "手动触发",
                    "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "stats": changeset["stats"],
                    "modules": [m["name"] for m in changeset["modules"]],
                    "pipeline": [{"name": s["name"], "ok": s["status"] == "done",
                                  "ms": s.get("duration_ms", 0)} for s in state["steps"]],
                }
                result = {
                    "features": outcome["features"],
                    "highlights": outcome["highlights"],
                    "lowConfidence": outcome["lowConfidence"],
                    "llm": outcome["llm"],
                    "contractSignals": changeset["contract_signals"],
                    "meta": meta,
                }
                opts = {"tone": run.tone, "mask": run.mask}
                checklist = renderers.render_checklist(result, opts)
                document = renderers.render_document(result, opts)
                trace, _sizes = renderers.render_trace_stable(result, opts, base_sizes={
                    "checklist": len(checklist.encode("utf-8")),
                    "document": len(document.encode("utf-8")),
                })
                files = {"checklist.csv": checklist, "product-doc.md": document, "trace.json": trace}
                written = archive_service.write_artifacts(_archive_root, run.version_label, files)
                for kind, filename in (("checklist", "checklist.csv"),
                                       ("document", "product-doc.md"),
                                       ("trace", "trace.json")):
                    path = written[filename]
                    db.add(Artifact(run_id=run.id, kind=kind, filename=filename,
                                    path=str(path), bytes=path.stat().st_size))
                _log(run_id, state, "step", "归档",
                     f"{archive_service.archive_dir_for(_archive_root, run.version_label)}")
                return result

            result = await _run_step(run_id, run, state, db, 4, step5)

            final_status = "degraded" if outcome["lowConfidence"] else "succeeded"
            state["status"] = final_status
            state["result"] = result
            state["current_step"] = len(state["steps"])
            run.status = final_status
            run.current_step = len(state["steps"])
            run.steps = state["steps"]
            run.logs = state["logs"]
            run.stats = changeset["stats"]
            run.result = result
            run.finished_at = datetime.utcnow()
            await db.commit()
            bus.publish(run_id, {"event": "progress", "data": {"percent": 100}})
            bus.publish(run_id, {"event": "done",
                                 "data": {"status": final_status, "result": result}})
        except RunCancelled:
            await _finish_cancelled(db, run, state, run_id)
        except Exception as exc:  # noqa: BLE001 —— 运行失败需完整落库并广播
            logger.exception("运行 %s 失败", run_id)
            await _finish_failed(db, run, state, run_id, exc)
```

- [ ] **Step 6: 运行全部测试确认通过**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

Expected: 全部通过（test_pipeline 6 个用例全过）。若 `test_execute_run_success` 中 trace 字节数断言失败，检查 `render_trace_stable` 迭代收敛逻辑（位数变化需多迭代一次）。

- [ ] **Step 7: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/backend
git commit -m 'feat(doc-release): Task 10 归档服务与五步流水线'
```

---

## Task 11: API 层（repos / runs / SSE / artifacts）

**Files:**
- Create: `doc-release/backend/app/schemas/__init__.py`（空文件）
- Create: `doc-release/backend/app/schemas/repo.py`
- Create: `doc-release/backend/app/schemas/run.py`
- Create: `doc-release/backend/app/api/__init__.py`（空文件）
- Create: `doc-release/backend/app/api/repos.py`
- Create: `doc-release/backend/app/api/runs.py`
- Modify: `doc-release/backend/app/services/pipeline_service.py`（增加 `get_archive_root()` 访问器）
- Modify: `doc-release/backend/app/main.py`（注册路由 + CORS）
- Create: `doc-release/backend/tests/test_api_repos.py`
- Create: `doc-release/backend/tests/test_api_runs.py`

- [ ] **Step 1: 创建空包文件与 schemas**

```powershell
New-Item -ItemType File -Force -Path app\schemas\__init__.py, app\api\__init__.py | Out-Null
```

`app/schemas/repo.py`：

```python
from pydantic import BaseModel, Field


class RepoCreate(BaseModel):
    path: str = Field(min_length=1)
    name: str | None = None
```

`app/schemas/run.py`：

```python
from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    repo_id: int
    base_ref: str = Field(min_length=1)
    head_ref: str = Field(min_length=1)
    version_label: str | None = None
    tone: str = "business"
    mask: bool = False
```

- [ ] **Step 2: 写失败测试 test_api_repos.py**

`tests/test_api_repos.py`：

```python
import pytest

from tests.gitfix import commit, init_repo, tag, write_files


@pytest.fixture
def sample_dir(tmp_path):
    r = init_repo(tmp_path)
    write_files(r, {"src/a.ts": "export const A = 1;\n"})
    commit(r, "init")
    tag(r, "v1.0.0")
    write_files(r, {"src/a.ts": "export const A = 2;\n"})
    commit(r, "change", date="2026-08-22 09:00:00 +0800")
    tag(r, "v1.1.0")
    return r


async def test_repo_crud_and_refs(client, sample_dir):
    resp = await client.post("/api/repos", json={"path": str(sample_dir)})
    assert resp.status_code == 201
    repo = resp.json()
    assert repo["name"] == "repo" and repo["is_sample"] is False

    dup = await client.post("/api/repos", json={"path": str(sample_dir)})
    assert dup.status_code == 409

    bad = await client.post("/api/repos", json={"path": str(sample_dir.parent / "nope")})
    assert bad.status_code == 400

    lst = await client.get("/api/repos")
    assert len(lst.json()) == 1

    refs = await client.get(f"/api/repos/{repo['id']}/refs")
    assert refs.status_code == 200
    assert [t["name"] for t in refs.json()["tags"]] == ["v1.0.0", "v1.1.0"]

    scen = await client.get(f"/api/repos/{repo['id']}/scenarios")
    assert scen.json() == []          # 非示例仓库没有内置场景


async def test_preview_and_empty_range(client, sample_dir):
    repo_id = (await client.post("/api/repos", json={"path": str(sample_dir)})).json()["id"]
    ok = await client.get(f"/api/repos/{repo_id}/preview", params={"base": "v1.0.0", "head": "v1.1.0"})
    assert ok.status_code == 200
    data = ok.json()
    assert data["stats"]["commits"] == 1
    assert data["files"][0]["path"] == "src/a.ts"

    empty = await client.get(f"/api/repos/{repo_id}/preview", params={"base": "v1.1.0", "head": "v1.1.0"})
    assert empty.status_code == 422

    bad = await client.get(f"/api/repos/{repo_id}/preview", params={"base": "nope", "head": "v1.1.0"})
    assert bad.status_code == 422


async def test_delete_repo(client, sample_dir):
    repo_id = (await client.post("/api/repos", json={"path": str(sample_dir)})).json()["id"]
    assert (await client.delete(f"/api/repos/{repo_id}")).status_code == 200
    assert (await client.get("/api/repos")).json() == []
    assert (await client.delete(f"/api/repos/{repo_id}")).status_code == 404
```

- [ ] **Step 3: 写失败测试 test_api_runs.py**

`tests/test_api_runs.py`：

```python
import asyncio
import json as jsonlib

import pytest

from tests.gitfix import commit, init_repo, tag, write_files


@pytest.fixture
def sample_dir(tmp_path):
    r = init_repo(tmp_path)
    write_files(r, {"src/a.ts": "export const A = 1;\n"})
    commit(r, "init")
    tag(r, "v1.0.0")
    write_files(r, {"src/a.ts": "export const A = 2;\nexport function run() {\n  return A;\n}\n"})
    commit(r, "feat", date="2026-08-22 09:00:00 +0800")
    tag(r, "v1.1.0")
    return r


async def _register(client, path) -> int:
    return (await client.post("/api/repos", json={"path": str(path)})).json()["id"]


async def _wait_terminal(client, run_id, timeout=15.0) -> dict:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        data = (await client.get(f"/api/runs/{run_id}")).json()
        if data["status"] not in ("pending", "running"):
            return data
        await asyncio.sleep(0.05)
    raise AssertionError("运行未在超时内结束")


def _slow_chat(seconds: float):
    async def chat(system, user):
        await asyncio.sleep(seconds)
        return jsonlib.dumps({"features": [], "highlights": [], "confidence": 0.5},
                             ensure_ascii=False)
    return chat


async def test_run_full_flow(client, sample_dir):
    repo_id = await _register(client, sample_dir)
    created = await client.post("/api/runs", json={
        "repo_id": repo_id, "base_ref": "v1.0.0", "head_ref": "v1.1.0",
        "version_label": "v1.1.0", "tone": "business", "mask": False})
    assert created.status_code == 201
    run_id = created.json()["id"]

    detail = await _wait_terminal(client, run_id)
    assert detail["status"] == "succeeded"
    assert detail["repo_name"] == "repo"
    assert [a["kind"] for a in detail["artifacts"]] == ["checklist", "document", "trace"]

    art = await client.get(f"/api/runs/{run_id}/artifacts/checklist")
    assert art.status_code == 200
    assert art.text.startswith("\ufeff")
    assert "自动生成的功能点" in art.text

    doc = await client.get(f"/api/runs/{run_id}/artifacts/document", params={"tone": "tech"})
    assert doc.status_code == 200 and "技术说明" in doc.text

    dl = await client.get(f"/api/runs/{run_id}/artifacts/document/download")
    assert "attachment" in dl.headers["content-disposition"]

    listing = (await client.get("/api/runs")).json()
    assert listing["total"] == 1
    assert listing["items"][0]["status"] == "succeeded"
    assert "logs" not in listing["items"][0]        # 列表不返回重型字段

    trace = jsonlib.loads((await client.get(f"/api/runs/{run_id}/artifacts/trace")).text)
    assert trace["runId"] == run_id


async def test_run_validation_and_duplicate(client, sample_dir, monkeypatch):
    from app.services import llm_service

    monkeypatch.setattr(llm_service, "_chat", _slow_chat(0.4))
    repo_id = await _register(client, sample_dir)
    bad = await client.post("/api/runs", json={
        "repo_id": repo_id, "base_ref": "nope", "head_ref": "v1.1.0"})
    assert bad.status_code == 422

    payload = {"repo_id": repo_id, "base_ref": "v1.0.0", "head_ref": "v1.1.0"}
    first = await client.post("/api/runs", json=payload)
    assert first.status_code == 201
    dup = await client.post("/api/runs", json=payload)
    assert dup.status_code == 409

    detail = await _wait_terminal(client, first.json()["id"])
    assert detail["status"] == "succeeded"
    second = await client.post("/api/runs", json=payload)
    assert second.status_code == 201
    await _wait_terminal(client, second.json()["id"])


async def test_cancel_running(client, sample_dir, monkeypatch):
    from app.services import llm_service

    monkeypatch.setattr(llm_service, "_chat", _slow_chat(1.0))
    repo_id = await _register(client, sample_dir)
    run_id = (await client.post("/api/runs", json={
        "repo_id": repo_id, "base_ref": "v1.0.0", "head_ref": "v1.1.0"})).json()["id"]
    assert (await client.post(f"/api/runs/{run_id}/cancel")).status_code == 200
    detail = await _wait_terminal(client, run_id)
    assert detail["status"] == "cancelled"
    assert (await client.post(f"/api/runs/{run_id}/cancel")).status_code == 409


async def test_artifacts_guards(client, sample_dir, monkeypatch):
    from app.services import llm_service

    monkeypatch.setattr(llm_service, "_chat", _slow_chat(0.5))
    repo_id = await _register(client, sample_dir)
    run_id = (await client.post("/api/runs", json={
        "repo_id": repo_id, "base_ref": "v1.0.0", "head_ref": "v1.1.0"})).json()["id"]
    assert (await client.get(f"/api/runs/{run_id}/artifacts/checklist")).status_code == 409
    assert (await client.get(f"/api/runs/{run_id}/artifacts/report")).status_code == 422
    assert (await client.get("/api/runs/unknown-id/artifacts/checklist")).status_code == 404
    await _wait_terminal(client, run_id)


async def test_sse_live_and_finished(client, sample_dir, monkeypatch):
    from app.services import llm_service

    monkeypatch.setattr(llm_service, "_chat", _slow_chat(0.3))
    repo_id = await _register(client, sample_dir)
    run_id = (await client.post("/api/runs", json={
        "repo_id": repo_id, "base_ref": "v1.0.0", "head_ref": "v1.1.0"})).json()["id"]

    events: list[str] = []
    guard = 0
    async with client.stream("GET", f"/api/runs/{run_id}/events") as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        async for line in resp.aiter_lines():
            guard += 1
            assert guard < 2000
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
            if events and events[-1] == "done":
                break
    assert events[0] == "snapshot"
    assert "step" in events and "log" in events
    assert events[-1] == "done"

    await _wait_terminal(client, run_id)
    events2: list[str] = []
    async with client.stream("GET", f"/api/runs/{run_id}/events") as resp:
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                events2.append(line.split(":", 1)[1].strip())
            if events2 and events2[-1] == "done":
                break
    assert events2 == ["snapshot", "done"]


async def test_delete_run_and_archive(client, sample_dir):
    repo_id = await _register(client, sample_dir)
    run_id = (await client.post("/api/runs", json={
        "repo_id": repo_id, "base_ref": "v1.0.0", "head_ref": "v1.1.0",
        "version_label": "v9.9.9"})).json()["id"]
    await _wait_terminal(client, run_id)
    assert (await client.delete(f"/api/runs/{run_id}")).status_code == 200
    assert (await client.get(f"/api/runs/{run_id}")).status_code == 404
    assert (await client.delete(f"/api/runs/{run_id}")).status_code == 404
```

- [ ] **Step 4: 运行测试确认失败**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests/test_api_repos.py tests/test_api_runs.py -q
```

Expected: FAIL —— 404 Not Found（路由尚未注册）。

- [ ] **Step 5: 实现 api/repos.py 与 api/runs.py**

`app/api/repos.py`：

```python
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import seed_data
from app.database import get_db
from app.models import Repo, Run
from app.schemas.repo import RepoCreate
from app.services import git_service
from app.services.errors import GitError

router = APIRouter(prefix="/api/repos", tags=["repos"])

PREVIEW_MAX_LINES = 300


async def _get_repo_or_404(db: AsyncSession, repo_id: int) -> Repo:
    repo = await db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="仓库不存在")
    return repo


@router.get("")
async def list_repos(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.execute(select(Repo).order_by(Repo.id))).scalars().all()
    return [r.to_dict() for r in rows]


@router.post("", status_code=201)
async def create_repo(payload: RepoCreate, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        git_service.validate_repo(payload.path)
    except GitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    existing = (await db.execute(select(Repo).where(Repo.path == payload.path))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="该仓库路径已注册")
    name = (payload.name or "").strip() or Path(payload.path).name
    repo = Repo(name=name, path=payload.path, is_sample=False)
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return repo.to_dict()


@router.delete("/{repo_id}")
async def delete_repo(repo_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    repo = await _get_repo_or_404(db, repo_id)
    run_count = (await db.execute(
        select(func.count()).select_from(Run).where(Run.repo_id == repo_id))).scalar_one()
    if run_count:
        raise HTTPException(status_code=400, detail=f"该仓库已有 {run_count} 条运行记录，不可删除")
    await db.delete(repo)
    await db.commit()
    return {"ok": True}


@router.get("/{repo_id}/refs")
async def repo_refs(repo_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    repo = await _get_repo_or_404(db, repo_id)
    try:
        return git_service.list_refs(repo.path)
    except GitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{repo_id}/scenarios")
async def repo_scenarios(repo_id: int, db: AsyncSession = Depends(get_db)) -> list[dict]:
    repo = await _get_repo_or_404(db, repo_id)
    return list(seed_data.SCENARIOS) if repo.is_sample else []


@router.get("/{repo_id}/preview")
async def repo_preview(repo_id: int, base: str, head: str,
                       db: AsyncSession = Depends(get_db)) -> dict:
    repo = await _get_repo_or_404(db, repo_id)
    try:
        return git_service.collect_diff(repo.path, base, head, max_lines=PREVIEW_MAX_LINES)
    except GitError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
```

`app/api/runs.py`：

```python
import asyncio
import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Artifact, Repo, Run
from app.models.run import blank_steps
from app.schemas.run import RunCreate
from app.services import archive_service, git_service, pipeline_service, renderers
from app.services.errors import GitError

router = APIRouter(prefix="/api/runs", tags=["runs"])

_ACTIVE_STATUSES = ("pending", "running")
_KIND_META = {
    "checklist": ("checklist.csv", "text/csv; charset=utf-8"),
    "document": ("product-doc.md", "text/markdown; charset=utf-8"),
    "trace": ("trace.json", "application/json; charset=utf-8"),
}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _run_detail(db: AsyncSession, run: Run) -> dict:
    detail = run.to_dict()
    repo = await db.get(Repo, run.repo_id)
    detail["repo_name"] = repo.name if repo else ""
    arts = (await db.execute(select(Artifact).where(Artifact.run_id == run.id))).scalars().all()
    detail["artifacts"] = [a.to_dict() for a in arts]
    return detail


@router.post("", status_code=201)
async def create_run(payload: RunCreate, db: AsyncSession = Depends(get_db)) -> dict:
    repo = await db.get(Repo, payload.repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="仓库不存在")
    if payload.tone not in ("business", "tech"):
        raise HTTPException(status_code=422, detail="tone 仅支持 business 或 tech")
    try:
        git_service.resolve_ref(repo.path, payload.base_ref)
        git_service.resolve_ref(repo.path, payload.head_ref)
    except GitError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    dup = (await db.execute(
        select(Run).where(Run.repo_id == payload.repo_id,
                         Run.base_ref == payload.base_ref,
                         Run.head_ref == payload.head_ref,
                         Run.status.in_(_ACTIVE_STATUSES)))).scalars().first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="相同范围已有运行中的任务")

    run = Run(
        repo_id=payload.repo_id,
        base_ref=payload.base_ref,
        head_ref=payload.head_ref,
        version_label=(payload.version_label or "").strip() or payload.head_ref,
        tone=payload.tone,
        mask=payload.mask,
    )
    run.steps = blank_steps()
    db.add(run)
    await db.commit()
    await db.refresh(run)

    asyncio.create_task(pipeline_service.execute_run(run.id))
    return await _run_detail(db, run)


@router.get("")
async def list_runs(limit: int = 20, offset: int = 0,
                   db: AsyncSession = Depends(get_db)) -> dict:
    total = (await db.execute(select(func.count()).select_from(Run))).scalar_one()
    rows = (await db.execute(select(Run).order_by(Run.created_at.desc(), Run.id)
                             .limit(min(max(limit, 1), 100)).offset(max(offset, 0)))).scalars().all()
    repo_names: dict[int, str] = {}
    if rows:
        repo_ids = {r.repo_id for r in rows}
        repos = (await db.execute(select(Repo).where(Repo.id.in_(repo_ids)))).scalars().all()
        repo_names = {repo.id: repo.name for repo in repos}
    items = []
    for r in rows:
        d = r.to_dict()
        d.pop("steps", None)
        d.pop("logs", None)
        d.pop("result", None)
        d["repo_name"] = repo_names.get(r.repo_id, "")
        items.append(d)
    return {"total": total, "items": items}


@router.get("/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    return await _run_detail(db, run)


def _build_snapshot(run: Run, live: dict | None) -> dict:
    base = run.to_dict()
    if live and live.get("status") == "running":
        base.update({"status": live["status"], "current_step": live["current_step"],
                     "steps": live["steps"], "logs": live["logs"],
                     "stats": live.get("stats") or {}, "result": live.get("result")})
    return base


@router.get("/{run_id}/events")
async def run_events(run_id: str, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")

    async def gen():
        queue = pipeline_service.bus.subscribe(run_id)
        try:
            snapshot = _build_snapshot(run, pipeline_service.get_live_state(run_id))
            seen = {(l.get("ts"), l.get("tag"), l.get("message")) for l in snapshot.get("logs", [])}
            yield _sse("snapshot", {"run": snapshot})
            if snapshot["status"] not in ("pending", "running"):
                yield _sse("done", {"status": snapshot["status"], "result": snapshot.get("result")})
                return
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                if ev["event"] == "log":
                    key = (ev["data"].get("ts"), ev["data"].get("tag"), ev["data"].get("message"))
                    if key in seen:
                        continue
                    seen.add(key)
                yield _sse(ev["event"], ev["data"])
                if ev["event"] == "done":
                    break
        finally:
            pipeline_service.bus.unsubscribe(run_id, queue)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    if run.status not in _ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail=f"运行已是 {run.status} 状态，无法取消")
    pipeline_service.cancel_run(run_id)
    return {"ok": True}


def _render_artifact(run: Run, kind: str, tone: str | None, mask: bool | None) -> str:
    if kind not in _KIND_META:
        raise HTTPException(status_code=422, detail="kind 仅支持 checklist/document/trace")
    if not run.result:
        raise HTTPException(status_code=409, detail="运行尚未完成，无产物可下载")
    opts = {"tone": tone or run.tone, "mask": run.mask if mask is None else mask}
    if opts["tone"] not in ("business", "tech"):
        raise HTTPException(status_code=422, detail="tone 仅支持 business 或 tech")
    result = run.result
    if kind == "checklist":
        return renderers.render_checklist(result, opts)
    if kind == "document":
        return renderers.render_document(result, opts)
    checklist = renderers.render_checklist(result, opts)
    document = renderers.render_document(result, opts)
    text, _ = renderers.render_trace_stable(result, opts, base_sizes={
        "checklist": len(checklist.encode("utf-8")),
        "document": len(document.encode("utf-8")),
    })
    return text


@router.get("/{run_id}/artifacts/{kind}")
async def get_artifact(run_id: str, kind: str, tone: str | None = None, mask: bool | None = None,
                       db: AsyncSession = Depends(get_db)) -> Response:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    text = _render_artifact(run, kind, tone, mask)
    _, media = _KIND_META[kind]
    return Response(content=text, media_type=media)


@router.get("/{run_id}/artifacts/{kind}/download")
async def download_artifact(run_id: str, kind: str, tone: str | None = None, mask: bool | None = None,
                            db: AsyncSession = Depends(get_db)) -> Response:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    text = _render_artifact(run, kind, tone, mask)
    filename, media = _KIND_META[kind]
    return Response(content=text, media_type=media,
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@router.delete("/{run_id}")
async def delete_run(run_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    if run.status in _ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="运行仍在进行中，请先取消")
    for art in (await db.execute(select(Artifact).where(Artifact.run_id == run.id))).scalars().all():
        await db.delete(art)
    archive_service.delete_archive_if_owned(pipeline_service.get_archive_root(),
                                            run.version_label, run.id)
    await db.delete(run)
    await db.commit()
    return {"ok": True}
```

- [ ] **Step 6: pipeline_service 增加归档根目录访问器**

在 `app/services/pipeline_service.py` 的 `set_archive_root` 函数下方追加：

```python
def get_archive_root() -> Path:
    return _archive_root
```

- [ ] **Step 7: main.py 注册路由与 CORS**

`app/main.py` 整体替换为：

```python
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

import seed_sample_repo
from app import models  # noqa: F401  确保模型在 metadata 中注册
from app.api import repos as repos_api
from app.api import runs as runs_api
from app.config import settings
from app.database import AsyncSessionLocal, Base, engine
from app.models import Repo


async def _ensure_sample_repo() -> None:
    """首次启动时幂等生成示例仓库并注册为 is_sample=True 的仓库记录。"""
    repo_path = await asyncio.to_thread(seed_sample_repo.generate, Path(settings.sample_repo_dir))
    resolved = str(repo_path.resolve())
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(Repo).where(Repo.path == resolved))).scalar_one_or_none()
        if existing is None:
            name = "order-center" if repo_path.name == seed_sample_repo.REPO_DIR_NAME else repo_path.name
            db.add(Repo(name=name, path=resolved, is_sample=True))
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_sample_repo()
    yield


app = FastAPI(title="释文 DocRelease", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


app.include_router(repos_api.router)
app.include_router(runs_api.router)
```

- [ ] **Step 8: 运行全部测试确认通过**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

Expected: 全部通过（test_api_runs 中涉及后台任务的用例耗时稍长，属正常）。若 SSE 用例挂起，检查 `client.stream` 的 break 条件是否命中了 done 事件后的首行 data。

- [ ] **Step 9: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/backend
git commit -m 'feat(doc-release): Task 11 API 层与 SSE 事件流'
```

---

## Task 12: 端到端冒烟脚本与后端 README

**Files:**
- Create: `doc-release/backend/e2e_smoke.py`
- Create: `doc-release/backend/README.md`

- [ ] **Step 1: 写 e2e_smoke.py**

`e2e_smoke.py`：

```python
"""端到端冒烟：进程内起 uvicorn（默认打桩 LLM），跑通三大场景并校验产物。

用法（在 backend 目录下）：
  .\\venv\\Scripts\\python.exe e2e_smoke.py            # 打桩 LLM（离线模式）
  .\\venv\\Scripts\\python.exe e2e_smoke.py --real     # 真实星语网关（需内网）
"""

import asyncio
import json
import sys
import threading
import time

import httpx
import uvicorn

import app.main as main_module
from app.services import llm_service

HOST = "127.0.0.1"
PORT = 8100
BASE = f"http://{HOST}:{PORT}"


async def _fake_chat(system_prompt: str, user_prompt: str) -> str:
    return json.dumps({
        "features": [{
            "tag": "技术重构", "risk": "低", "breaking": False,
            "title": "冒烟生成的占位功能点", "biz": "冒烟测试用业务说明",
            "tech": "冒烟测试用技术说明", "visible": "无", "scope": "冒烟",
            "acceptance": "冒烟断言", "action": "无需操作", "role": "研发", "paths": [],
        }],
        "highlights": ["冒烟通过"], "confidence": 0.9,
    }, ensure_ascii=False)


async def _run_checks() -> list[str]:
    failures: list[str] = []
    async with httpx.AsyncClient(base_url=BASE, timeout=180) as client:
        repos = (await client.get("/api/repos")).json()
        sample = next((r for r in repos if r["is_sample"]), None)
        if sample is None:
            return ["未找到示例仓库（is_sample=True）"]

        refs = (await client.get(f"/api/repos/{sample['id']}/refs")).json()
        tags = {t["name"] for t in refs["tags"]}
        for t in ("v2.13.3", "v2.13.4", "v2.14.0", "v3.0.0"):
            if t not in tags:
                failures.append(f"缺少标签 {t}")

        scenarios = (await client.get(f"/api/repos/{sample['id']}/scenarios")).json()
        if len(scenarios) != 3:
            failures.append(f"场景数应为 3，实际 {len(scenarios)}")

        for sc in scenarios:
            resp = await client.post("/api/runs", json={
                "repo_id": sample["id"], "base_ref": sc["base"], "head_ref": sc["head"],
                "version_label": sc["version"], "tone": "business", "mask": False})
            if resp.status_code != 201:
                failures.append(f"[{sc['id']}] 创建运行失败：{resp.status_code} {resp.text[:200]}")
                continue
            run_id = resp.json()["id"]
            deadline = time.time() + 180
            detail: dict = {}
            while time.time() < deadline:
                detail = (await client.get(f"/api/runs/{run_id}")).json()
                if detail["status"] not in ("pending", "running"):
                    break
                await asyncio.sleep(0.3)
            if detail.get("status") != "succeeded":
                failures.append(f"[{sc['id']}] 终态 {detail.get('status')}（error={detail.get('error')}）")
                continue

            for kind in ("checklist", "document", "trace"):
                art = await client.get(f"/api/runs/{run_id}/artifacts/{kind}")
                if art.status_code != 200 or not art.text.strip():
                    failures.append(f"[{sc['id']}] 产物 {kind} 不可读或为空")
            trace = json.loads((await client.get(f"/api/runs/{run_id}/artifacts/trace")).text)
            if trace["runId"] != run_id:
                failures.append(f"[{sc['id']}] trace.runId 不匹配")
            print(f"  [{sc['id']}] {sc['version']}：功能点 {len(trace['features'])} 个，"
                  f"提交 {trace['changes'].get('commits')} 个，产物 3 份 OK")
    return failures


def main() -> int:
    if "--real" not in sys.argv:
        llm_service._chat = _fake_chat
        print("使用打桩 LLM（离线模式）")
    else:
        print("使用真实星语网关")

    config = uvicorn.Config(main_module.app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    try:
        failures = asyncio.run(_run_checks())
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    if failures:
        print("冒烟失败：")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("冒烟全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 手动运行冒烟验证**

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe e2e_smoke.py
```

Expected: 打印三个场景的通过行与「冒烟全部通过」，退出码 0。首次运行会生成 `sample_repo/order-center` 与 `archive/`、`docrelease.db`（均在 .gitignore 中）。若 8100 端口被占用，改脚本顶部 `PORT` 后重跑。

- [ ] **Step 3: 写 backend/README.md**

`README.md`：

```markdown
# 释文 DocRelease · 后端

从代码变更自动生成发布文档的后端服务：读取本地 git 仓库的变更范围（base..head），
经五步流水线（定位范围 → 收集变更 → tree-sitter AST 解析 → 星语 LLM 业务化改写 → 产物归档），
通过 SSE 实时推送进度，产出 `checklist.csv` / `product-doc.md` / `trace.json` 三类产物。

## 环境

- Python 3.11（Windows x64 已验证，tree-sitter 有预编译 wheel）
- 内网环境可直接访问星语网关；脱离内网时运行会在 LLM 步骤失败/降级

## 初始化

```powershell
cd doc-release\backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env    # 按需修改
```

## 启动

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

首次启动会自动：建表 → 幂等生成示例仓库 `sample_repo/order-center`（含 v2.13.3/v2.13.4/v2.14.0/v3.0.0 四个标签与三大场景）→ 注册为 `is_sample=True` 的仓库。

## 测试

```powershell
.\venv\Scripts\python.exe -m pytest tests -q
```

全部测试离线可跑（conftest 全局打桩 LLM，不会调用真实星语）。

## 冒烟

```powershell
.\venv\Scripts\python.exe e2e_smoke.py           # 打桩 LLM（离线）
.\venv\Scripts\python.exe e2e_smoke.py --real    # 真实星语（内网）
```

## 种子脚本

```powershell
.\venv\Scripts\python.exe seed_sample_repo.py            # 默认生成到 sample_repo/order-center
.\venv\Scripts\python.exe seed_sample_repo.py D:\tmp\demo  # 指定目录
```

## API 摘要（前缀 /api）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /health | 健康检查 |
| GET | /repos | 仓库列表 |
| POST | /repos | 注册本地仓库（body: path, name?） |
| DELETE | /repos/{id} | 删除仓库（有运行记录时 400） |
| GET | /repos/{id}/refs | 分支与标签列表 |
| GET | /repos/{id}/scenarios | 内置场景（仅示例仓） |
| GET | /repos/{id}/preview?base=&head= | 变更预览（截断至 300 行/文件） |
| POST | /runs | 创建并启动运行（body: repo_id, base_ref, head_ref, version_label?, tone?, mask?） |
| GET | /runs | 运行列表（分页 total/items） |
| GET | /runs/{id} | 运行详情（含 steps/logs/stats/result/artifacts） |
| GET | /runs/{id}/events | SSE 事件流（snapshot/step/log/progress/done/error + 15s 心跳） |
| POST | /runs/{id}/cancel | 取消运行 |
| DELETE | /runs/{id} | 删除运行（含归档，trace.runId 匹配才删） |
| GET | /runs/{id}/artifacts/{kind} | 渲染产物（kind: checklist/document/trace；query: tone, mask） |
| GET | /runs/{id}/artifacts/{kind}/download | 下载产物 |

## 归档

产物写入 `archive/docs/release/<version>/`（同版本覆盖；删除时校验 trace.runId 防误删）。
```

- [ ] **Step 4: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/backend
git commit -m 'feat(doc-release): Task 12 冒烟脚本与后端 README'
```

---

## Task 13: 前端工程骨架

**Files:**
- Create: `doc-release/frontend/package.json`、`.gitignore`、`index.html`、`env.d.ts`、`vite.config.ts`、`tsconfig.json`、`tsconfig.app.json`、`tsconfig.node.json`
- Create: `doc-release/frontend/src/main.ts`、`App.vue`、`router/index.ts`、`types/index.ts`、`data/steps.ts`、`styles/theme.css`
- Create: `doc-release/frontend/src/components/TopBar.vue`
- Create: `doc-release/frontend/src/views/ConsoleView.vue`、`HistoryView.vue`、`HistoryDetailView.vue`（本任务先占位）

- [ ] **Step 1: 写工程配置文件**

`package.json`：

```json
{
  "name": "doc-release-frontend",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@element-plus/icons-vue": "^2.3.1",
    "axios": "^1.8.4",
    "element-plus": "^2.9.7",
    "marked": "^15.0.7",
    "pinia": "^3.0.1",
    "vue": "^3.5.13",
    "vue-router": "^4.5.0"
  },
  "devDependencies": {
    "@tsconfig/node22": "^22.0.0",
    "@types/node": "^22.10.0",
    "@vitejs/plugin-vue": "^5.2.3",
    "@vue/tsconfig": "^0.7.0",
    "typescript": "~5.7.3",
    "vite": "^6.2.4",
    "vue-tsc": "^2.2.8"
  }
}
```

`vite.config.ts`：

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
```

`tsconfig.json`：

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

`tsconfig.app.json`：

```json
{
  "extends": "@vue/tsconfig/tsconfig.dom.json",
  "include": ["env.d.ts", "src/**/*", "src/**/*.vue"],
  "compilerOptions": {
    "composite": true,
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  }
}
```

`tsconfig.node.json`：

```json
{
  "extends": "@tsconfig/node22/tsconfig.json",
  "include": ["vite.config.*"],
  "compilerOptions": {
    "composite": true,
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
    "module": "ESNext",
    "types": ["node"]
  }
}
```

`env.d.ts`：

```ts
/// <reference types="vite/client" />
```

`index.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>释文 DocRelease · 发布文档自动生成</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

`.gitignore`：

```
node_modules/
dist/
.vite/
```

- [ ] **Step 2: 写 types/index.ts 与 data/steps.ts**

`src/types/index.ts`：

```ts
export interface Repo {
  id: number
  name: string
  path: string
  is_sample: boolean
  created_at: string
}

export interface RefItem {
  name: string
  short: string
}

export interface Refs {
  branches: RefItem[]
  tags: RefItem[]
  default_branch: string
}

export interface Scenario {
  id: string
  name: string
  short: string
  version: string
  base: string
  head: string
  description: string
}

export interface Stats {
  commits: number
  files: number
  modules: number
  added: number
  removed: number
  days: number
}

export interface CommitInfo {
  hash: string
  author: string
  date: string
  subject: string
}

export interface DiffLine {
  t: 'add' | 'del' | 'ctx'
  s: string
}

export interface PreviewFile {
  status: 'a' | 'm' | 'd'
  path: string
  added: number
  removed: number
  binary: boolean
  truncated: boolean
  lines: DiffLine[]
}

export interface ModuleGroup {
  name: string
  files: string[]
}

export interface Preview {
  base: string
  head: string
  commits: CommitInfo[]
  files: PreviewFile[]
  stats: Stats
  modules: ModuleGroup[]
}

export type StepStatus = 'pending' | 'active' | 'done' | 'failed'

export interface StepState {
  index: number
  name: string
  status: StepStatus
  started_at?: string
  finished_at?: string
  duration_ms?: number
}

export interface LogLine {
  ts: string
  channel: string
  tag: string
  message: string
}

export interface Feature {
  tag: string
  risk: string
  breaking: boolean
  title: string
  biz: string
  tech: string
  visible: string
  scope: string
  acceptance: string
  action: string
  role: string
  paths: string[]
}

export interface LlmMeta {
  provider: string
  model: string
  prompt: string
  confidence: number
  inputChars: number
  outputChars: number
  glossaryHits: number
  lowConfidence: string[]
}

export interface RunMeta {
  runId: string
  repoName: string
  version: string
  branch: string
  headShort: string
  range: string
  trigger: string
  generatedAt: string
  stats: Stats
  modules: string[]
  pipeline: { name: string; ok: boolean; ms: number }[]
}

export interface ContractSignal {
  kind: string
  path: string
  message: string
}

export interface RunResult {
  features: Feature[]
  highlights: string[]
  lowConfidence: string[]
  llm: LlmMeta
  contractSignals: ContractSignal[]
  meta: RunMeta
}

export interface ArtifactInfo {
  kind: string
  filename: string
  bytes: number
}

export interface RunDetail {
  id: string
  repo_id: number
  repo_name: string
  base_ref: string
  head_ref: string
  version_label: string
  tone: string
  mask: boolean
  status: string
  current_step: number
  steps: StepState[]
  logs: LogLine[]
  stats: Stats | Record<string, never>
  result: RunResult | null
  error: string | null
  created_at: string
  finished_at: string | null
  artifacts: ArtifactInfo[]
}

export interface RunSummary {
  id: string
  repo_id: number
  repo_name: string
  base_ref: string
  head_ref: string
  version_label: string
  tone: string
  mask: boolean
  status: string
  current_step: number
  stats: Stats
  error: string | null
  created_at: string
  finished_at: string | null
}

export interface RunList {
  total: number
  items: RunSummary[]
}

export interface SseEvent {
  event: string
  data: any
}
```

`src/data/steps.ts`（五步的读/写/失败说明，文案与 demo 语义对齐）：

```ts
export interface StepExplain {
  read: string
  write: string
  failure: string
}

export const STEP_EXPLAINS: StepExplain[] = [
  { read: '仓库路径、base/head 引用、提交历史', write: '解析后的版本锚点与提交统计', failure: '引用无效或仓库不可读，运行终止' },
  { read: 'base..head 的逐文件 diff 与 numstat', write: '变更文件集、增删行数、模块聚类', failure: '范围内无变更提交，运行终止' },
  { read: '变更前后的文件内容', write: '导出符号增删改对比与契约信号', failure: '单文件解析失败时降级为文件级信号，不中断' },
  { read: '结构性变更 + 术语表口径', write: '功能点 JSON（业务/技术双写）与置信度', failure: '单块失败降级占位；全部失败则运行失败' },
  { read: '结构化结果与展示选项（口径/脱敏）', write: 'checklist.csv / product-doc.md / trace.json', failure: '归档不可写，运行失败' },
]
```

- [ ] **Step 3: 写 theme.css（复刻 demo 设计语言）**

`src/styles/theme.css`：

```css
:root {
  --brand: #2f5bff;
  --brand-600: #2148d8;
  --brand-50: #eef3ff;
  --bg: #f4f6fb;
  --panel: #ffffff;
  --line: #e4e8f2;
  --text: #1c2540;
  --muted: #6b7690;
  --ok: #17a673;
  --warn: #d99000;
  --danger: #e5484d;
  --radius: 12px;
  --shadow: 0 2px 12px rgba(28, 37, 64, .06);
  --mono: "Cascadia Code", Consolas, "Courier New", monospace;
}

* { box-sizing: border-box; }

html, body, #app { height: 100%; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.6 "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.panel { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }
.panel-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 14px; border-bottom: 1px solid var(--line); font-weight: 600; }
.panel-body { padding: 14px; }
.panel-body--flush { padding: 0; }

.chip { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px; border-radius: 999px; font-size: 12px; background: var(--brand-50); color: var(--brand); }
.chip--ghost { background: transparent; border: 1px solid var(--line); color: var(--muted); }

.tag { display: inline-block; padding: 1px 8px; border-radius: 6px; font-size: 12px; white-space: nowrap; }
.tag--add { background: #e8f8f1; color: var(--ok); }
.tag--mod { background: #fff5e0; color: var(--warn); }
.tag--del { background: #fdeaea; color: var(--danger); }
.tag--breaking { background: #fdeaea; color: var(--danger); }
.tag--quiet { background: var(--bg); color: var(--muted); }

.stat-row { display: flex; flex-wrap: wrap; gap: 8px; }
.stat { display: flex; flex-direction: column; gap: 0; padding: 6px 12px; border: 1px solid var(--line); border-radius: 8px; min-width: 76px; background: var(--panel); }
.stat b { font-size: 17px; }
.stat span { color: var(--muted); font-size: 12px; }

.note-box { background: var(--brand-50); border: 1px solid #d7e1ff; border-radius: 8px; padding: 10px 12px; color: #33508f; font-size: 13px; }

/* 终端 */
.term { background: #0e1424; color: #d5dcf0; font-family: var(--mono); font-size: 12px; line-height: 1.7; border-radius: 8px; padding: 12px; overflow: auto; }
.term-line { display: flex; gap: 8px; white-space: pre-wrap; word-break: break-all; }
.term-ts { color: #5b6b96; flex: none; }
.term-tag { flex: none; color: #7ea2ff; }
.term--warn .term-tag { color: #f0b429; }
.term--error .term-tag { color: #f2757a; }

/* 步骤列表 */
.steps { display: flex; flex-direction: column; gap: 8px; }
.step { border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; background: var(--panel); }
.step--active { border-color: var(--brand); background: var(--brand-50); }
.step--done { border-color: #cdeadd; }
.step--failed { border-color: #f5c6c8; background: #fdf3f3; }
.step-title { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.step-no { width: 22px; height: 22px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; background: var(--bg); color: var(--muted); }
.step--active .step-no { background: var(--brand); color: #fff; }
.step--done .step-no { background: var(--ok); color: #fff; }
.step--failed .step-no { background: var(--danger); color: #fff; }
.step-meta { margin-top: 6px; color: var(--muted); font-size: 12px; display: grid; gap: 2px; }
.step-meta em { font-style: normal; color: #47536f; margin-right: 4px; }

/* diff */
.diff-file { border: 1px solid var(--line); border-radius: 8px; margin-bottom: 8px; overflow: hidden; }
.diff-file-head { display: flex; align-items: center; gap: 8px; padding: 6px 10px; background: #fafbfe; border-bottom: 1px solid var(--line); font-size: 12px; }
.diff-file-path { font-family: var(--mono); }
.diff-lines { font-family: var(--mono); font-size: 12px; line-height: 1.6; max-height: 260px; overflow: auto; }
.diff-line { display: flex; white-space: pre; }
.diff-line--add { background: #eaf9f2; }
.diff-line--del { background: #fdeeee; }
.diff-sign { width: 18px; flex: none; text-align: center; color: var(--muted); user-select: none; }

/* 标签页 */
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--line); padding: 0 10px; }
.tab { padding: 8px 12px; font-size: 13px; color: var(--muted); cursor: pointer; border-bottom: 2px solid transparent; }
.tab--active { color: var(--brand); border-bottom-color: var(--brand); font-weight: 600; }

/* JSON / Markdown 预览 */
.json-view { font-family: var(--mono); font-size: 12px; line-height: 1.6; white-space: pre-wrap; word-break: break-all; background: #fafbfe; border: 1px solid var(--line); border-radius: 8px; padding: 12px; max-height: 520px; overflow: auto; }
.md-view { line-height: 1.75; }
.md-view h1 { font-size: 20px; }
.md-view h2 { font-size: 16px; border-bottom: 1px solid var(--line); padding-bottom: 4px; margin-top: 22px; }
.md-view h3 { font-size: 14px; margin-bottom: 6px; }
.md-view table { border-collapse: collapse; width: 100%; }
.md-view td, .md-view th { border: 1px solid var(--line); padding: 6px 10px; font-size: 13px; }

/* 通用 */
.toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.muted { color: var(--muted); }
.mono { font-family: var(--mono); }
.empty { padding: 28px 16px; text-align: center; color: var(--muted); }
.table-simple { width: 100%; border-collapse: collapse; }
.table-simple th, .table-simple td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); font-size: 13px; }
.table-simple th { color: var(--muted); font-weight: 600; }
.scroll { overflow: auto; }

.status { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; padding: 2px 10px; border-radius: 999px; }
.status::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.status--pending { background: #f0f2f7; color: var(--muted); }
.status--running { background: var(--brand-50); color: var(--brand); }
.status--succeeded { background: #e8f8f1; color: var(--ok); }
.status--degraded { background: #fff5e0; color: var(--warn); }
.status--failed { background: #fdeaea; color: var(--danger); }
.status--cancelled { background: #f0f2f7; color: var(--muted); }
```

- [ ] **Step 4: 写 main.ts / router / App.vue / TopBar.vue / 占位视图**

`src/main.ts`：

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import './styles/theme.css'

createApp(App).use(createPinia()).use(router).use(ElementPlus).mount('#app')
```

`src/router/index.ts`：

```ts
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'console', component: () => import('@/views/ConsoleView.vue') },
    { path: '/history', name: 'history', component: () => import('@/views/HistoryView.vue') },
    { path: '/history/:id', name: 'history-detail', component: () => import('@/views/HistoryDetailView.vue') },
  ],
})

export default router
```

`src/App.vue`：

```vue
<template>
  <div class="app-shell">
    <TopBar />
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import TopBar from '@/components/TopBar.vue'
</script>

<style scoped>
.app-shell { min-height: 100%; display: flex; flex-direction: column; }
.app-main { flex: 1; width: 100%; max-width: 1560px; margin: 0 auto; padding: 16px 20px 32px; }
</style>
```

`src/components/TopBar.vue`：

```vue
<template>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="brand-block">
        <span class="brand-name">释文 DocRelease</span>
        <span class="brand-sub muted">发布文档自动生成</span>
      </div>
      <nav class="nav">
        <router-link class="nav-item" :class="{ 'nav-item--active': route.name === 'console' }" to="/">工作台</router-link>
        <router-link class="nav-item" :class="{ 'nav-item--active': String(route.name || '').startsWith('history') }" to="/history">发布历史</router-link>
      </nav>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<style scoped>
.topbar { background: var(--panel); border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 10; }
.topbar-inner { max-width: 1560px; margin: 0 auto; padding: 10px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.brand-block { display: flex; align-items: baseline; gap: 10px; }
.brand-name { font-size: 18px; font-weight: 700; color: var(--brand); }
.brand-sub { font-size: 12px; }
.nav { display: flex; gap: 6px; }
.nav-item { padding: 6px 12px; border-radius: 8px; color: var(--muted); text-decoration: none; font-size: 13px; }
.nav-item--active { background: var(--brand-50); color: var(--brand); font-weight: 600; }
</style>
```

说明：demo 顶栏的「返回主站」链接在真实系统中无对应目标（认证与主站导航均为非目标），按 YAGNI 省略；「当前页导航（工作台 / 发布历史）」承担定位职责。

占位视图（本任务先最小可用，后续任务补齐）：

`src/views/ConsoleView.vue`：

```vue
<template>
  <div class="panel"><div class="panel-body empty">工作台建设中</div></div>
</template>

<script setup lang="ts"></script>
```

`src/views/HistoryView.vue`：

```vue
<template>
  <div class="panel"><div class="panel-body empty">发布历史建设中</div></div>
</template>

<script setup lang="ts"></script>
```

`src/views/HistoryDetailView.vue`：

```vue
<template>
  <div class="panel"><div class="panel-body empty">运行详情建设中</div></div>
</template>

<script setup lang="ts"></script>
```

- [ ] **Step 5: 安装依赖并验证构建**

```powershell
cd doc-release\frontend
npm install
npm run build
```

Expected: 构建成功（`vue-tsc --noEmit` 无错，`vite build` 输出 dist/）。若 `@types/node` 未安装导致 tsconfig.node 报错，确认 devDependencies 中包含它后重装。

- [ ] **Step 6: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/frontend
git commit -m 'feat(doc-release): Task 13 前端工程骨架'
```

---

## Task 14: API 客户端、SSE 订阅与 Pinia 状态

**Files:**
- Create: `doc-release/frontend/src/api/client.ts`
- Create: `doc-release/frontend/src/api/sse.ts`
- Create: `doc-release/frontend/src/stores/repo.ts`
- Create: `doc-release/frontend/src/stores/run.ts`

- [ ] **Step 1: 写 api/client.ts**

`src/api/client.ts`：

```ts
import axios from 'axios'
import type { Preview, Refs, Repo, RunDetail, RunList, Scenario } from '@/types'

const http = axios.create({ baseURL: '/api', timeout: 30000 })

export async function getRepos(): Promise<Repo[]> {
  return (await http.get('/repos')).data
}

export async function createRepo(path: string, name?: string): Promise<Repo> {
  return (await http.post('/repos', { path, name })).data
}

export async function deleteRepo(id: number): Promise<void> {
  await http.delete(`/repos/${id}`)
}

export async function getRefs(repoId: number): Promise<Refs> {
  return (await http.get(`/repos/${repoId}/refs`)).data
}

export async function getScenarios(repoId: number): Promise<Scenario[]> {
  return (await http.get(`/repos/${repoId}/scenarios`)).data
}

export async function getPreview(repoId: number, base: string, head: string): Promise<Preview> {
  return (await http.get(`/repos/${repoId}/preview`, { params: { base, head } })).data
}

export interface RunCreatePayload {
  repo_id: number
  base_ref: string
  head_ref: string
  version_label?: string
  tone?: string
  mask?: boolean
}

export async function createRun(payload: RunCreatePayload): Promise<RunDetail> {
  return (await http.post('/runs', payload)).data
}

export async function getRuns(limit = 20, offset = 0): Promise<RunList> {
  return (await http.get('/runs', { params: { limit, offset } })).data
}

export async function getRun(runId: string): Promise<RunDetail> {
  return (await http.get(`/runs/${runId}`)).data
}

export async function cancelRun(runId: string): Promise<void> {
  await http.post(`/runs/${runId}/cancel`)
}

export async function deleteRun(runId: string): Promise<void> {
  await http.delete(`/runs/${runId}`)
}

export async function getArtifactText(runId: string, kind: string, tone: string, mask: boolean): Promise<string> {
  const resp = await http.get(`/runs/${runId}/artifacts/${kind}`, {
    params: { tone, mask },
    responseType: 'text',
    transformResponse: [(data: string) => data],
  })
  return resp.data as string
}

export function artifactDownloadUrl(runId: string, kind: string, tone: string, mask: boolean): string {
  return `/api/runs/${runId}/artifacts/${kind}/download?tone=${tone}&mask=${mask}`
}

export function extractError(err: unknown): string {
  const e = err as { response?: { data?: { detail?: unknown } }; message?: string }
  const detail = e?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => (d as { msg?: string }).msg || '').join('；')
  }
  return e?.message || '请求失败'
}
```

- [ ] **Step 2: 写 api/sse.ts（fetch + ReadableStream 手动解析 + 指数退避重连）**

`src/api/sse.ts`：

```ts
import type { SseEvent } from '@/types'

export interface SseHandle {
  close: () => void
}

export function subscribeRun(
  runId: string,
  onEvent: (ev: SseEvent) => void,
  onError?: (err: unknown) => void,
  maxRetries = 5,
): SseHandle {
  const controller = new AbortController()
  let closed = false
  let retries = 0

  const connect = async (): Promise<void> => {
    try {
      const resp = await fetch(`/api/runs/${runId}/events`, {
        signal: controller.signal,
        headers: { Accept: 'text/event-stream' },
      })
      if (!resp.ok || !resp.body) {
        throw new Error(`SSE 连接失败：HTTP ${resp.status}`)
      }
      retries = 0
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx = buffer.indexOf('\n\n')
        while (idx !== -1) {
          const block = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          const ev = parseBlock(block)
          if (ev) {
            onEvent(ev)
            if (ev.event === 'done') {
              closed = true
              controller.abort()
              return
            }
          }
          idx = buffer.indexOf('\n\n')
        }
      }
      if (!closed) throw new Error('SSE 连接中断')
    } catch (err) {
      if (closed || controller.signal.aborted) return
      if (retries >= maxRetries) {
        onError?.(err)
        return
      }
      retries += 1
      setTimeout(connect, 1000 * 2 ** (retries - 1))
    }
  }

  void connect()

  return {
    close: () => {
      closed = true
      controller.abort()
    },
  }
}

function parseBlock(raw: string): SseEvent | null {
  if (raw.startsWith(':')) return null   // 心跳
  let event = 'message'
  let data = ''
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data += line.slice(5).trim()
  }
  if (!data) return null
  try {
    return { event, data: JSON.parse(data) }
  } catch {
    return null
  }
}
```

- [ ] **Step 3: 写 stores/repo.ts**

`src/stores/repo.ts`：

```ts
import { defineStore } from 'pinia'
import * as api from '@/api/client'
import type { Preview, RefItem, Refs, Repo, Scenario } from '@/types'

export const useRepoStore = defineStore('repo', {
  state: () => ({
    repos: [] as Repo[],
    currentRepoId: null as number | null,
    refs: null as Refs | null,
    scenarios: [] as Scenario[],
    preview: null as Preview | null,
    loadingPreview: false,
    error: '',
    baseRef: '',
    headRef: '',
    versionLabel: '',
    tone: 'business' as 'business' | 'tech',
    mask: false,
  }),
  getters: {
    currentRepo(state): Repo | null {
      return state.repos.find((r) => r.id === state.currentRepoId) || null
    },
    isSample(state): boolean {
      return !!state.repos.find((r) => r.id === state.currentRepoId)?.is_sample
    },
    refOptions(state): RefItem[] {
      if (!state.refs) return []
      return [...state.refs.tags, ...state.refs.branches]
    },
  },
  actions: {
    async loadRepos() {
      this.repos = await api.getRepos()
      if (this.currentRepoId === null && this.repos.length) {
        await this.selectRepo(this.repos[0].id)
      }
    },
    async selectRepo(id: number) {
      this.currentRepoId = id
      this.preview = null
      this.error = ''
      this.refs = await api.getRefs(id)
      this.scenarios = await api.getScenarios(id)
      const first = this.scenarios[0]
      if (first) {
        await this.applyScenario(first)
      } else if (this.refs) {
        const tags = this.refs.tags
        this.baseRef = tags[tags.length - 2]?.name || tags[tags.length - 1]?.name || this.refs.default_branch
        this.headRef = tags[tags.length - 1]?.name || this.refs.default_branch
        this.versionLabel = this.headRef
        await this.loadPreview()
      }
    },
    async applyScenario(sc: Scenario) {
      this.baseRef = sc.base
      this.headRef = sc.head
      this.versionLabel = sc.version
      await this.loadPreview()
    },
    async loadPreview() {
      if (this.currentRepoId === null || !this.baseRef || !this.headRef) return
      this.loadingPreview = true
      this.error = ''
      try {
        this.preview = await api.getPreview(this.currentRepoId, this.baseRef, this.headRef)
      } catch (err) {
        this.preview = null
        this.error = api.extractError(err)
      } finally {
        this.loadingPreview = false
      }
    },
    async swapRefs() {
      const base = this.baseRef
      this.baseRef = this.headRef
      this.headRef = base
      await this.loadPreview()
    },
  },
})
```

- [ ] **Step 4: 写 stores/run.ts**

`src/stores/run.ts`：

```ts
import { defineStore } from 'pinia'
import * as api from '@/api/client'
import { subscribeRun, type SseHandle } from '@/api/sse'
import type { LogLine, RunDetail, RunResult, SseEvent, StepState } from '@/types'

function logKey(line: LogLine): string {
  return `${line.ts}|${line.tag}|${line.message}`
}

export const useRunStore = defineStore('run', {
  state: () => ({
    current: null as RunDetail | null,
    steps: [] as StepState[],
    logs: [] as LogLine[],
    status: 'idle',
    progress: 0,
    error: '',
    result: null as RunResult | null,
    stats: {} as Record<string, number>,
    handle: null as SseHandle | null,
    seen: new Set<string>(),
  }),
  getters: {
    isActive(state): boolean {
      return state.status === 'pending' || state.status === 'running'
    },
  },
  actions: {
    closeStream() {
      this.handle?.close()
      this.handle = null
    },
    reset() {
      this.closeStream()
      this.current = null
      this.steps = []
      this.logs = []
      this.status = 'idle'
      this.progress = 0
      this.error = ''
      this.result = null
      this.stats = {}
      this.seen = new Set()
    },
    applySnapshot(detail: RunDetail) {
      this.current = detail
      this.steps = detail.steps || []
      this.logs = detail.logs || []
      this.status = detail.status
      this.error = detail.error || ''
      this.result = detail.result
      this.stats = (detail.stats || {}) as Record<string, number>
      this.seen = new Set(this.logs.map(logKey))
    },
    applyEvent(ev: SseEvent) {
      if (ev.event === 'snapshot') {
        this.applySnapshot(ev.data.run as RunDetail)
      } else if (ev.event === 'step') {
        const { index, status, duration_ms } = ev.data as { index: number; status: StepState['status']; duration_ms?: number }
        const step = this.steps[index]
        if (step) {
          step.status = status
          if (duration_ms !== undefined) step.duration_ms = duration_ms
        }
        if (this.current) this.current.current_step = index
      } else if (ev.event === 'log') {
        const line = ev.data as LogLine
        const key = logKey(line)
        if (!this.seen.has(key)) {
          this.seen.add(key)
          this.logs.push(line)
        }
      } else if (ev.event === 'progress') {
        this.progress = (ev.data as { percent: number }).percent ?? this.progress
      } else if (ev.event === 'error') {
        this.error = (ev.data as { message?: string }).message || '运行失败'
      } else if (ev.event === 'done') {
        this.status = (ev.data as { status: string }).status
        const result = (ev.data as { result?: RunResult | null }).result
        if (result) this.result = result
        this.progress = 100
        this.closeStream()
      }
    },
    connect(runId: string) {
      this.handle = subscribeRun(
        runId,
        (ev) => this.applyEvent(ev),
        (err) => {
          this.error = api.extractError(err)
        },
      )
    },
    async startRun(
      repoId: number,
      payload: { base_ref: string; head_ref: string; version_label: string; tone: string; mask: boolean },
    ) {
      this.reset()
      const detail = await api.createRun({ repo_id: repoId, ...payload })
      this.applySnapshot(detail)
      this.connect(detail.id)
    },
    async attach(runId: string) {
      this.reset()
      const detail = await api.getRun(runId)
      this.applySnapshot(detail)
      if (this.isActive) this.connect(runId)
    },
    async cancel() {
      if (!this.current) return
      await api.cancelRun(this.current.id)
    },
  },
})
```

- [ ] **Step 5: 验证构建通过**

```powershell
cd doc-release\frontend
npm run build
```

Expected: 构建成功（vue-tsc 无类型错误）。

- [ ] **Step 6: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/frontend
git commit -m 'feat(doc-release): Task 14 API 客户端、SSE 订阅与状态管理'
```

---

## Task 15: 顶部控制条与变更预览面板

**Files:**
- Create: `doc-release/frontend/src/components/ControlBar.vue`
- Create: `doc-release/frontend/src/components/DiffPanel.vue`
- Modify: `doc-release/frontend/src/views/ConsoleView.vue`（三栏布局组装，中/右栏本任务先留占位区域）

- [ ] **Step 1: 写 ControlBar.vue**

`src/components/ControlBar.vue`：

```vue
<template>
  <section class="panel">
    <div class="panel-body control-grid">
      <div class="field">
        <label class="field-label">仓库</label>
        <el-select v-model="repoModel" placeholder="选择仓库" style="width: 220px">
          <el-option v-for="r in store.repos" :key="r.id"
                     :label="r.is_sample ? `${r.name}（内置示例）` : r.name" :value="r.id" />
        </el-select>
      </div>

      <div v-if="store.scenarios.length" class="field">
        <label class="field-label">内置场景</label>
        <div class="toolbar">
          <button v-for="sc in store.scenarios" :key="sc.id" class="chip-btn"
                  :class="{ 'chip-btn--active': sc.base === store.baseRef && sc.head === store.headRef }"
                  :title="sc.description" @click="store.applyScenario(sc)">
            {{ sc.name }} · {{ sc.version }}
          </button>
        </div>
      </div>

      <div class="field">
        <label class="field-label">变更范围</label>
        <div class="toolbar">
          <el-select v-model="baseModel" style="width: 148px" @change="store.loadPreview()">
            <el-option v-for="r in store.refOptions" :key="`b-${r.name}`" :label="r.name" :value="r.name" />
          </el-select>
          <button class="swap-btn" title="交换 base/head" @click="store.swapRefs()">⇄</button>
          <el-select v-model="headModel" style="width: 148px" @change="store.loadPreview()">
            <el-option v-for="r in store.refOptions" :key="`h-${r.name}`" :label="r.name" :value="r.name" />
          </el-select>
        </div>
      </div>

      <div class="field">
        <label class="field-label">版本号</label>
        <el-input v-model="versionModel" style="width: 140px" placeholder="如 v2.14.0" />
      </div>

      <div class="field">
        <label class="field-label">展示口径</label>
        <el-radio-group v-model="toneModel" size="small">
          <el-radio-button value="business">业务</el-radio-button>
          <el-radio-button value="tech">技术</el-radio-button>
        </el-radio-group>
      </div>

      <div class="field">
        <label class="field-label">脱敏</label>
        <el-switch v-model="maskModel" />
      </div>

      <div class="field field--actions">
        <el-button type="primary" :loading="runStore.isActive" :disabled="!canRun" @click="onRun">
          {{ runStore.isActive ? '运行中…' : '开始生成' }}
        </el-button>
        <el-button v-if="runStore.isActive" @click="runStore.cancel()">取消</el-button>
      </div>
    </div>

    <div v-if="runStore.status !== 'idle'" class="run-progress">
      <el-progress :percentage="runStore.progress" :stroke-width="6"
                   :status="progressStatus" :show-text="false" />
      <span class="muted run-progress-text">进度 {{ runStore.progress }}%</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { extractError } from '@/api/client'
import { useRepoStore } from '@/stores/repo'
import { useRunStore } from '@/stores/run'

const store = useRepoStore()
const runStore = useRunStore()

const repoModel = computed({
  get: () => store.currentRepoId ?? undefined,
  set: (v: number | undefined) => {
    if (typeof v === 'number') void store.selectRepo(v)
  },
})

const baseModel = computed({ get: () => store.baseRef, set: (v: string) => { store.baseRef = v } })
const headModel = computed({ get: () => store.headRef, set: (v: string) => { store.headRef = v } })
const versionModel = computed({ get: () => store.versionLabel, set: (v: string) => { store.versionLabel = v } })
const toneModel = computed({
  get: () => store.tone,
  set: (v: string | number | boolean | undefined) => { store.tone = v === 'tech' ? 'tech' : 'business' },
})
const maskModel = computed({
  get: () => store.mask,
  set: (v: string | number | boolean) => { store.mask = Boolean(v) },
})

const canRun = computed(
  () => store.currentRepoId !== null && !!store.baseRef && !!store.headRef && !runStore.isActive,
)

const progressStatus = computed(() => {
  if (runStore.status === 'failed' || runStore.status === 'cancelled') return 'exception' as const
  if (runStore.status === 'succeeded' || runStore.status === 'degraded') return 'success' as const
  return undefined
})

async function onRun() {
  if (store.currentRepoId === null) return
  try {
    await runStore.startRun(store.currentRepoId, {
      base_ref: store.baseRef,
      head_ref: store.headRef,
      version_label: store.versionLabel || store.headRef,
      tone: store.tone,
      mask: store.mask,
    })
  } catch (err) {
    ElMessage.error(extractError(err))
  }
}
</script>

<style scoped>
.control-grid { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 14px 18px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 12px; color: var(--muted); }
.field--actions { margin-left: auto; flex-direction: row; align-items: center; gap: 8px; }
.chip-btn { border: 1px solid var(--line); background: var(--panel); cursor: pointer; padding: 4px 12px; border-radius: 999px; font-size: 12px; color: var(--muted); }
.chip-btn:hover { border-color: var(--brand); color: var(--brand); }
.chip-btn--active { background: var(--brand-50); border-color: var(--brand); color: var(--brand); font-weight: 600; }
.swap-btn { border: 1px solid var(--line); background: var(--panel); border-radius: 8px; width: 30px; height: 30px; cursor: pointer; color: var(--muted); }
.swap-btn:hover { color: var(--brand); border-color: var(--brand); }
.run-progress { display: flex; align-items: center; gap: 10px; padding: 0 14px 14px; }
.run-progress :deep(.el-progress) { flex: 1; }
.run-progress-text { font-size: 12px; white-space: nowrap; }
</style>
```

- [ ] **Step 2: 写 DiffPanel.vue**

`src/components/DiffPanel.vue`：

```vue
<template>
  <section class="panel diff-panel">
    <div class="panel-header">
      <span>变更预览</span>
      <span v-if="store.preview" class="muted mono">{{ store.preview.base }} → {{ store.preview.head }}</span>
    </div>
    <div class="panel-body scroll diff-body">
      <div v-if="store.error" class="note-box note-box--error">{{ store.error }}</div>
      <div v-else-if="store.loadingPreview" class="empty">加载变更中…</div>
      <div v-else-if="!store.preview" class="empty">选择仓库与变更范围后预览变更</div>
      <template v-else>
        <div class="stat-row">
          <div class="stat"><b>{{ store.preview.stats.commits }}</b><span>提交</span></div>
          <div class="stat"><b>{{ store.preview.stats.files }}</b><span>文件</span></div>
          <div class="stat"><b>{{ store.preview.stats.modules }}</b><span>模块</span></div>
          <div class="stat"><b class="add-text">+{{ store.preview.stats.added }}</b><span>新增行</span></div>
          <div class="stat"><b class="del-text">-{{ store.preview.stats.removed }}</b><span>删除行</span></div>
          <div class="stat"><b>{{ store.preview.stats.days }}</b><span>跨度天</span></div>
        </div>

        <h4 class="section-title">提交记录</h4>
        <ul class="commit-list">
          <li v-for="c in store.preview.commits" :key="c.hash">
            <span class="mono muted">{{ c.hash }}</span>
            <span class="commit-subject">{{ c.subject }}</span>
            <span class="muted">{{ c.date }}</span>
          </li>
        </ul>

        <h4 class="section-title">文件 diff（{{ store.preview.files.length }}）</h4>
        <div v-for="f in store.preview.files" :key="f.path" class="diff-file">
          <div class="diff-file-head">
            <span class="tag" :class="statusClass(f.status)">{{ statusLabel(f.status) }}</span>
            <span class="diff-file-path">{{ f.path }}</span>
            <span class="muted">+{{ f.added }} / -{{ f.removed }}</span>
            <span v-if="f.truncated" class="chip chip--ghost">已截断</span>
          </div>
          <div v-if="f.binary" class="diff-lines"><div class="diff-line"><span class="diff-sign">·</span>二进制文件，未展示内容</div></div>
          <div v-else class="diff-lines">
            <div v-for="(l, i) in f.lines" :key="i" class="diff-line" :class="`diff-line--${l.t}`">
              <span class="diff-sign">{{ l.t === 'add' ? '+' : l.t === 'del' ? '-' : ' ' }}</span><span>{{ l.s }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useRepoStore } from '@/stores/repo'

const store = useRepoStore()

function statusLabel(status: string): string {
  return { a: '新增', m: '修改', d: '删除' }[status] || '修改'
}

function statusClass(status: string): string {
  return { a: 'tag--add', d: 'tag--del' }[status] || 'tag--mod'
}
</script>

<style scoped>
.diff-panel { display: flex; flex-direction: column; min-height: 0; }
.diff-body { flex: 1; overflow: auto; max-height: calc(100vh - 260px); }
.section-title { margin: 14px 0 8px; font-size: 13px; color: var(--muted); }
.commit-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.commit-list li { display: flex; gap: 8px; font-size: 13px; }
.commit-subject { flex: 1; }
.add-text { color: var(--ok); }
.del-text { color: var(--danger); }
.note-box--error { background: #fdf3f3; border-color: #f5c6c8; color: #a03034; }
</style>
```

- [ ] **Step 3: 改写 ConsoleView.vue（三栏布局）**

`src/views/ConsoleView.vue`：

```vue
<template>
  <div class="console">
    <ControlBar />
    <div class="console-grid">
      <DiffPanel />
      <section class="panel">
        <div class="panel-header"><span>运行流水线</span></div>
        <div class="panel-body empty">运行面板接入中</div>
      </section>
      <section class="panel">
        <div class="panel-header"><span>产物</span></div>
        <div class="panel-body empty">产物面板接入中</div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import ControlBar from '@/components/ControlBar.vue'
import DiffPanel from '@/components/DiffPanel.vue'
import { useRepoStore } from '@/stores/repo'
import { useRunStore } from '@/stores/run'

const store = useRepoStore()
const runStore = useRunStore()

onMounted(async () => {
  await store.loadRepos()
})

onBeforeUnmount(() => {
  runStore.closeStream()
})
</script>

<style scoped>
.console { display: flex; flex-direction: column; gap: 14px; }
.console-grid { display: grid; grid-template-columns: 1.05fr 0.85fr 1.1fr; gap: 14px; align-items: start; }
@media (max-width: 1180px) {
  .console-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 820px) {
  .console-grid { grid-template-columns: 1fr; }
}
</style>
```

- [ ] **Step 4: 联调验证（需前后端同时运行）**

终端 A（后端，若 8000 被占则换 8001 并同步改 vite.config.ts 的 proxy target）：

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

终端 B（前端）：

```powershell
cd doc-release\frontend
npm run build
npm run dev
```

浏览器打开 `http://localhost:5173`，逐项确认：
1. 顶部导航显示「工作台 / 发布历史」，工作台顶部控制条已渲染
2. 仓库默认选中「order-center（内置示例）」，下方出现 3 个场景按钮（补丁修复/功能迭代/大版本升级）
3. 变更预览区展示统计卡片、提交记录与逐文件 diff（新增/修改/删除标签颜色正确）
4. 点击「大版本升级」场景：范围变为 v2.14.0..v3.0.0，预览刷新（含删除的 api/legacy/order.go 红色行）
5. 点「⇄」交换 base/head：范围反向，预览显示错误提示（无变更提交，422）而不是崩溃

- [ ] **Step 5: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/frontend
git commit -m 'feat(doc-release): Task 15 顶部控制条与变更预览面板'
```

---

## Task 16: 运行面板（步骤列表、终端日志与运行接线）

**Files:**
- Create: `doc-release/frontend/src/components/StatusBadge.vue`
- Create: `doc-release/frontend/src/components/StepList.vue`
- Create: `doc-release/frontend/src/components/TerminalLog.vue`
- Create: `doc-release/frontend/src/components/PipelinePanel.vue`
- Modify: `doc-release/frontend/src/data/steps.ts`（追加 STEP_NAMES，与后端 `app/models/run.py` 的 STEP_NAMES 一致）
- Modify: `doc-release/frontend/src/views/ConsoleView.vue`（中栏接入 PipelinePanel）

- [ ] **Step 1: data/steps.ts 追加 STEP_NAMES**

在 `src/data/steps.ts` 顶部（`export interface StepExplain` 之前）追加：

```ts
export const STEP_NAMES = [
  '定位仓库与变更范围',
  '收集变更（diff 与统计）',
  'AST 解析变更结构',
  'LLM 业务化语义改写',
  '产物生成并归档',
]
```

- [ ] **Step 2: 写 StatusBadge.vue**

`src/components/StatusBadge.vue`：

```vue
<template>
  <span class="status" :class="`status--${status}`">{{ label }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string }>()

const LABELS: Record<string, string> = {
  pending: '排队中',
  running: '运行中',
  succeeded: '成功',
  degraded: '降级完成',
  failed: '失败',
  cancelled: '已取消',
  idle: '未运行',
}

const label = computed(() => LABELS[props.status] || props.status)
</script>
```

- [ ] **Step 3: 写 StepList.vue**

`src/components/StepList.vue`（未运行时展示本地五步占位，运行时展示后端步骤状态）：

```vue
<template>
  <div class="steps">
    <div v-for="s in displaySteps" :key="s.index" class="step" :class="stepClass(s)">
      <div class="step-title">
        <span class="step-no">{{ s.index + 1 }}</span>
        <span>{{ s.name }}</span>
        <span class="step-side" :class="`step-side--${s.status}`">{{ statusText(s) }}</span>
      </div>
      <div class="step-meta">
        <div><em>读</em>{{ explain(s.index).read }}</div>
        <div><em>写</em>{{ explain(s.index).write }}</div>
        <div><em>失败</em>{{ explain(s.index).failure }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { StepState } from '@/types'
import { STEP_EXPLAINS, STEP_NAMES, type StepExplain } from '@/data/steps'

const props = defineProps<{ steps: StepState[] }>()

const displaySteps = computed<StepState[]>(() => {
  if (props.steps.length) return props.steps
  return STEP_NAMES.map((name, index) => ({ index, name, status: 'pending' as const }))
})

function stepClass(s: StepState): string {
  return s.status === 'pending' ? '' : `step--${s.status}`
}

function statusText(s: StepState): string {
  if (s.status === 'active') return '运行中…'
  if (s.status === 'done') return `已完成${durationText(s)}`
  if (s.status === 'failed') return '失败'
  return '待运行'
}

function durationText(s: StepState): string {
  if (s.duration_ms === undefined || s.duration_ms === null) return ''
  return s.duration_ms >= 1000 ? ` · ${(s.duration_ms / 1000).toFixed(1)}s` : ` · ${s.duration_ms}ms`
}

function explain(index: number): StepExplain {
  return STEP_EXPLAINS[index] || { read: '', write: '', failure: '' }
}
</script>

<style scoped>
.step-side { margin-left: auto; font-size: 12px; color: var(--muted); white-space: nowrap; }
.step-side--active { color: var(--brand); }
.step-side--done { color: var(--ok); }
.step-side--failed { color: var(--danger); }
.step-meta div { word-break: break-all; }
</style>
```

- [ ] **Step 4: 写 TerminalLog.vue**

`src/components/TerminalLog.vue`（终端窗口标题条 + tag 颜色分级 + 新日志自动滚底）：

```vue
<template>
  <div class="term">
    <div class="term-hd">
      <span class="dots"><i></i><i></i><i></i></span>
      <span>docrelease — /workspace/pipeline</span>
    </div>
    <div ref="box" class="term-body">
      <div v-if="!logs.length" class="term-hint">等待运行日志…</div>
      <div v-for="(l, i) in logs" :key="i" class="term-line" :class="lineClass(l)">
        <span class="term-ts">{{ timeOf(l.ts) }}</span>
        <span class="term-tag">{{ l.tag }}</span>
        <span>{{ l.message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import type { LogLine } from '@/types'

const props = defineProps<{ logs: LogLine[] }>()
const box = ref<HTMLElement | null>(null)

function timeOf(ts: string): string {
  return ts.length >= 19 ? ts.slice(11, 19) : ts
}

function lineClass(l: LogLine): string {
  if (l.channel === 'error') return 'term--error'
  if (l.channel === 'warn') return 'term--warn'
  return ''
}

watch(
  () => props.logs.length,
  async () => {
    await nextTick()
    if (box.value) box.value.scrollTop = box.value.scrollHeight
  },
)
</script>

<style scoped>
.term { height: 300px; padding: 0; display: flex; flex-direction: column; overflow: hidden; }
.term-hd { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #151d33; color: #8b98bd; font-size: 11px; border-bottom: 1px solid #1d2742; flex: none; }
.dots { display: inline-flex; gap: 5px; }
.dots i { width: 9px; height: 9px; border-radius: 50%; }
.dots i:nth-child(1) { background: #f2757a; }
.dots i:nth-child(2) { background: #f0b429; }
.dots i:nth-child(3) { background: #3ecf8e; }
.term-body { flex: 1; overflow: auto; padding: 10px 12px; }
.term-hint { color: #5b6b96; }
</style>
```

- [ ] **Step 5: 写 PipelinePanel.vue**

`src/components/PipelinePanel.vue`：

```vue
<template>
  <section class="panel">
    <div class="panel-header">
      <span>运行流水线</span>
      <StatusBadge v-if="runStore.status !== 'idle'" :status="runStore.status" />
    </div>
    <div class="pipeline-body">
      <StepList :steps="runStore.steps" />
      <TerminalLog :logs="runStore.logs" />
    </div>
    <div v-if="runStore.error" class="note-box pipeline-error">{{ runStore.error }}</div>
  </section>
</template>

<script setup lang="ts">
import { useRunStore } from '@/stores/run'
import StatusBadge from '@/components/StatusBadge.vue'
import StepList from '@/components/StepList.vue'
import TerminalLog from '@/components/TerminalLog.vue'

const runStore = useRunStore()
</script>

<style scoped>
.pipeline-body { display: flex; flex-direction: column; gap: 12px; padding: 14px; }
.pipeline-error { margin: 0 14px 14px; background: #fdf3f3; border-color: #f5c6c8; color: #a03034; }
</style>
```

- [ ] **Step 6: ConsoleView.vue 中栏接入**

`src/views/ConsoleView.vue` 整体替换为：

```vue
<template>
  <div class="console">
    <ControlBar />
    <div class="console-grid">
      <DiffPanel />
      <PipelinePanel />
      <section class="panel">
        <div class="panel-header"><span>产物</span></div>
        <div class="panel-body empty">产物面板接入中</div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import ControlBar from '@/components/ControlBar.vue'
import DiffPanel from '@/components/DiffPanel.vue'
import PipelinePanel from '@/components/PipelinePanel.vue'
import { useRepoStore } from '@/stores/repo'
import { useRunStore } from '@/stores/run'

const store = useRepoStore()
const runStore = useRunStore()

onMounted(async () => {
  await store.loadRepos()
})

onBeforeUnmount(() => {
  runStore.closeStream()
})
</script>

<style scoped>
.console { display: flex; flex-direction: column; gap: 14px; }
.console-grid { display: grid; grid-template-columns: 1.05fr 0.85fr 1.1fr; gap: 14px; align-items: start; }
@media (max-width: 1180px) {
  .console-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 820px) {
  .console-grid { grid-template-columns: 1fr; }
}
</style>
```

- [ ] **Step 7: 构建验证**

```powershell
cd doc-release\frontend
npm run build
```

Expected: 构建成功（vue-tsc 无类型错误）。

- [ ] **Step 8: 联调验证（前后端同时运行）**

终端 A（后端）：

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

终端 B（前端）：

```powershell
cd doc-release\frontend
npm run dev
```

浏览器打开 `http://localhost:5173`，选择内置示例仓库并点「开始生成」，逐项确认：
1. 状态徽标变「运行中」，按钮变 loading +「运行中…」，出现「取消」按钮
2. 中栏五步依次点亮：active（蓝色）→ done（绿色 + 耗时）；未运行的步骤显示「待运行」与读写失败说明
3. 终端窗口（mac 风格标题条）日志滚动输出，tag 包含「范围 / 提交 / 规模 / 模块 / 符号 / 分块 / 改写 / 归档」，warn 行黄色、error 行红色
4. 顶部进度条随步骤推进递增，结束时 100%，状态为「成功」（存在低置信项时为「降级完成」）
5. 若 `.env` 未配置星语/DeepSeek 密钥：步骤④转失败（红色），终端最后出现 error 行，状态「失败」——这是预期错误路径，UI 不应崩溃
6. 再次运行并中途点「取消」：状态「已取消」，未开始的步骤保持「待运行」，终端出现「取消」标签的 warn 行

- [ ] **Step 9: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/frontend
git commit -m 'feat(doc-release): Task 16 运行面板与流水线接线'
```

---

## Task 17: 产物渲染与导出（OutputPanel）

**Files:**
- Create: `doc-release/frontend/src/render/artifacts.ts`
- Create: `doc-release/frontend/src/components/OutputPanel.vue`
- Modify: `doc-release/frontend/src/views/ConsoleView.vue`（右栏接入 OutputPanel）

- [ ] **Step 1: 写 render/artifacts.ts**

`src/render/artifacts.ts`（CSV 解析 / JSON 格式化 / Markdown 渲染三个纯函数）：

```ts
import { marked } from 'marked'

/** 解析带 BOM 的 CSV 文本为二维数组，支持引号转义与字段内逗号。 */
export function parseCsv(text: string): string[][] {
  const src = text.replace(/^\uFEFF/, '')
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false
  for (let i = 0; i < src.length; i += 1) {
    const ch = src[i]
    if (quoted) {
      if (ch === '"') {
        if (src[i + 1] === '"') {
          field += '"'
          i += 1
        } else {
          quoted = false
        }
      } else {
        field += ch
      }
    } else if (ch === '"') {
      quoted = true
    } else if (ch === ',') {
      row.push(field)
      field = ''
    } else if (ch === '\n') {
      row.push(field)
      field = ''
      rows.push(row)
      row = []
    } else if (ch !== '\r') {
      field += ch
    }
  }
  if (field !== '' || row.length) {
    row.push(field)
    rows.push(row)
  }
  return rows.filter((r) => r.some((c) => c.trim() !== ''))
}

/** JSON 文本格式化；解析失败时原样返回。 */
export function formatJson(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
}

/** Markdown 渲染为 HTML。 */
export function renderMarkdown(md: string): string {
  return marked.parse(md) as string
}
```

- [ ] **Step 2: 写 OutputPanel.vue**

`src/components/OutputPanel.vue`（三类产物 tabs + 口径/脱敏即时重渲染 + 复制/下载）：

```vue
<template>
  <section class="panel">
    <div class="panel-header">
      <span>产物</span>
      <div v-if="hasArtifacts" class="toolbar">
        <span class="tiny muted">口径</span>
        <el-radio-group v-model="toneModel" size="small">
          <el-radio-button value="business">业务</el-radio-button>
          <el-radio-button value="tech">技术</el-radio-button>
        </el-radio-group>
        <span class="tiny muted">脱敏</span>
        <el-switch v-model="maskModel" size="small" />
      </div>
    </div>

    <template v-if="hasArtifacts">
      <div class="tabs">
        <div v-for="t in tabs" :key="t.kind" class="tab"
             :class="{ 'tab--active': activeKind === t.kind }" @click="activeKind = t.kind">
          {{ t.label }}
        </div>
        <div class="tab-actions">
          <el-button size="small" @click="copyContent">复制</el-button>
          <el-button size="small" type="primary" plain @click="download">下载</el-button>
        </div>
      </div>
      <div class="panel-body scroll output-body">
        <div v-if="loadError" class="note-box output-error">{{ loadError }}</div>
        <div v-else-if="loading" class="empty">加载产物中…</div>
        <template v-else>
          <table v-if="activeKind === 'checklist'" class="table-simple">
            <thead>
              <tr><th v-for="(h, i) in csvHead" :key="i">{{ h }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in csvBody" :key="ri">
                <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else-if="activeKind === 'document'" class="md-view" v-html="mdHtml" />
          <pre v-else class="json-view">{{ jsonText }}</pre>
        </template>
      </div>
    </template>
    <div v-else class="panel-body empty">运行完成后在此查看三类产物并导出</div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { artifactDownloadUrl, extractError, getArtifactText } from '@/api/client'
import { formatJson, parseCsv, renderMarkdown } from '@/render/artifacts'
import { useRepoStore } from '@/stores/repo'
import { useRunStore } from '@/stores/run'

const store = useRepoStore()
const runStore = useRunStore()

const tabs = [
  { kind: 'checklist', label: '发布检查清单' },
  { kind: 'document', label: '产品说明' },
  { kind: 'trace', label: '溯源数据' },
]

const activeKind = ref('checklist')
const content = ref('')
const loading = ref(false)
const loadError = ref('')

const hasArtifacts = computed(() => !!runStore.current?.artifacts?.length)

const toneModel = computed({
  get: () => store.tone,
  set: (v: string | number | boolean | undefined) => { store.tone = v === 'tech' ? 'tech' : 'business' },
})
const maskModel = computed({
  get: () => store.mask,
  set: (v: string | number | boolean) => { store.mask = Boolean(v) },
})

const csvRows = computed(() => (activeKind.value === 'checklist' && content.value ? parseCsv(content.value) : []))
const csvHead = computed(() => csvRows.value[0] || [])
const csvBody = computed(() => csvRows.value.slice(1))
const mdHtml = computed(() => (activeKind.value === 'document' && content.value ? renderMarkdown(content.value) : ''))
const jsonText = computed(() => (activeKind.value === 'trace' && content.value ? formatJson(content.value) : ''))

async function load() {
  const run = runStore.current
  if (!run || !run.artifacts?.length) {
    content.value = ''
    loadError.value = ''
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    content.value = await getArtifactText(run.id, activeKind.value, store.tone, store.mask)
  } catch (err) {
    content.value = ''
    loadError.value = extractError(err)
  } finally {
    loading.value = false
  }
}

watch(
  () => [runStore.current?.id, runStore.result, activeKind.value, store.tone, store.mask],
  () => { void load() },
  { immediate: true },
)

async function copyContent() {
  if (!content.value) return
  try {
    await navigator.clipboard.writeText(content.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动选择复制')
  }
}

function download() {
  const run = runStore.current
  if (!run) return
  window.open(artifactDownloadUrl(run.id, activeKind.value, store.tone, store.mask), '_blank')
}
</script>

<style scoped>
.output-body { max-height: calc(100vh - 300px); }
.tiny { font-size: 12px; }
.tab-actions { margin-left: auto; display: flex; align-items: center; gap: 8px; }
.output-error { background: #fdf3f3; border-color: #f5c6c8; color: #a03034; }
.output-body :deep(.table-simple) { white-space: nowrap; }
</style>
```

- [ ] **Step 3: ConsoleView.vue 右栏接入**

`src/views/ConsoleView.vue` 整体替换为：

```vue
<template>
  <div class="console">
    <ControlBar />
    <div class="console-grid">
      <DiffPanel />
      <PipelinePanel />
      <OutputPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import ControlBar from '@/components/ControlBar.vue'
import DiffPanel from '@/components/DiffPanel.vue'
import OutputPanel from '@/components/OutputPanel.vue'
import PipelinePanel from '@/components/PipelinePanel.vue'
import { useRepoStore } from '@/stores/repo'
import { useRunStore } from '@/stores/run'

const store = useRepoStore()
const runStore = useRunStore()

onMounted(async () => {
  await store.loadRepos()
})

onBeforeUnmount(() => {
  runStore.closeStream()
})
</script>

<style scoped>
.console { display: flex; flex-direction: column; gap: 14px; }
.console-grid { display: grid; grid-template-columns: 1.05fr 0.85fr 1.1fr; gap: 14px; align-items: start; }
@media (max-width: 1180px) {
  .console-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 820px) {
  .console-grid { grid-template-columns: 1fr; }
}
</style>
```

- [ ] **Step 4: 构建验证**

```powershell
cd doc-release\frontend
npm run build
```

Expected: 构建成功（vue-tsc 无类型错误）。

- [ ] **Step 5: 联调验证**

运行一次 patch 场景至成功后逐项确认：
1. 右栏出现 tabs「发布检查清单 / 产品说明 / 溯源数据」，默认展示清单表格（第一行为表头，列含 module / feature / status 等，可横向滚动）
2. 切「产品说明」：Markdown 正确渲染（标题层级、表格、列表）；切「溯源数据」：JSON 缩进格式化，含 runId、artifacts、pipeline 字段
3. 切换口径「业务↔技术」：当前 tab 内容即时重渲染（标题文案变化）
4. 打开「脱敏」开关：路径/路由信息变为掩码（如 `src/**`）
5. 点「复制」：剪贴板内容与当前展示一致；点「下载」：浏览器保存 checklist.csv / product-doc.md / trace.json
6. 未运行或运行失败时：右栏保持空状态提示，控制台无报错

- [ ] **Step 6: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/frontend
git commit -m 'feat(doc-release): Task 17 产物渲染与导出'
```

---

## Task 18: 发布历史列表与详情页

**Files:**
- Create: `doc-release/frontend/src/components/RunTable.vue`
- Modify: `doc-release/frontend/src/views/HistoryView.vue`（列表页实现）
- Modify: `doc-release/frontend/src/views/HistoryDetailView.vue`（详情页实现，复用 PipelinePanel / OutputPanel）
- Modify: `doc-release/frontend/src/views/ConsoleView.vue`（onMounted 增加运行态重连）

- [ ] **Step 1: 写 RunTable.vue**

`src/components/RunTable.vue`：

```vue
<template>
  <div class="scroll">
    <table class="table-simple">
      <thead>
        <tr>
          <th>时间</th>
          <th>仓库</th>
          <th>版本</th>
          <th>范围</th>
          <th>状态</th>
          <th>耗时</th>
          <th style="width: 150px">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!runs.length">
          <td colspan="7" class="empty">暂无发布记录</td>
        </tr>
        <tr v-for="r in runs" :key="r.id">
          <td class="mono">{{ fmtTime(r.created_at) }}</td>
          <td>{{ r.repo_name }}</td>
          <td>{{ r.version_label }}</td>
          <td class="mono">{{ r.base_ref }}..{{ r.head_ref }}</td>
          <td><StatusBadge :status="r.status" /></td>
          <td>{{ duration(r) }}</td>
          <td>
            <el-button size="small" @click="$emit('view', r.id)">查看</el-button>
            <el-button size="small" type="danger" plain @click="$emit('remove', r.id)">删除</el-button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import type { RunSummary } from '@/types'
import StatusBadge from '@/components/StatusBadge.vue'

defineProps<{ runs: RunSummary[] }>()
defineEmits<{ view: [id: string]; remove: [id: string] }>()

function fmtTime(iso: string): string {
  return iso ? iso.replace('T', ' ').slice(0, 19) : '-'
}

function duration(r: RunSummary): string {
  if (!r.finished_at) return '-'
  const ms = new Date(r.finished_at).getTime() - new Date(r.created_at).getTime()
  if (!Number.isFinite(ms) || ms <= 0) return '<1s'
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}
</script>
```

- [ ] **Step 2: 写 HistoryView.vue**

`src/views/HistoryView.vue` 整体替换为：

```vue
<template>
  <section class="panel">
    <div class="panel-header">
      <span>发布历史</span>
      <div class="toolbar">
        <span class="muted">共 {{ total }} 条</span>
        <el-button size="small" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>
    <RunTable :runs="items" @view="onView" @remove="onRemove" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteRun, extractError, getRuns } from '@/api/client'
import RunTable from '@/components/RunTable.vue'
import type { RunSummary } from '@/types'

const router = useRouter()
const items = ref<RunSummary[]>([])
const total = ref(0)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await getRuns(100, 0)
    items.value = data.items
    total.value = data.total
  } catch (err) {
    ElMessage.error(extractError(err))
  } finally {
    loading.value = false
  }
}

function onView(id: string) {
  void router.push(`/history/${id}`)
}

async function onRemove(id: string) {
  try {
    await ElMessageBox.confirm('删除后不可恢复，确认删除该次运行记录与归档产物？', '删除确认', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteRun(id)
    ElMessage.success('已删除')
    await load()
  } catch (err) {
    ElMessage.error(extractError(err))
  }
}

onMounted(() => { void load() })
</script>
```

- [ ] **Step 3: 写 HistoryDetailView.vue**

`src/views/HistoryDetailView.vue` 整体替换为：

```vue
<template>
  <div class="detail">
    <section class="panel">
      <div class="panel-header">
        <div class="toolbar">
          <el-button size="small" @click="router.push('/history')">← 返回列表</el-button>
          <span class="mono muted">{{ runId }}</span>
        </div>
        <StatusBadge v-if="runStore.current" :status="runStore.status" />
      </div>
      <div v-if="runStore.current" class="panel-body detail-meta">
        <div class="meta-item"><span class="muted">仓库</span><b>{{ runStore.current.repo_name }}</b></div>
        <div class="meta-item"><span class="muted">版本</span><b>{{ runStore.current.version_label }}</b></div>
        <div class="meta-item"><span class="muted">范围</span><b class="mono">{{ runStore.current.base_ref }}..{{ runStore.current.head_ref }}</b></div>
        <div class="meta-item"><span class="muted">开始</span><b class="mono">{{ fmt(runStore.current.created_at) }}</b></div>
        <div class="meta-item"><span class="muted">结束</span><b class="mono">{{ fmt(runStore.current.finished_at) }}</b></div>
      </div>
      <div v-else class="panel-body empty">加载运行详情中…</div>
    </section>
    <div class="detail-grid">
      <PipelinePanel />
      <OutputPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { extractError } from '@/api/client'
import OutputPanel from '@/components/OutputPanel.vue'
import PipelinePanel from '@/components/PipelinePanel.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useRepoStore } from '@/stores/repo'
import { useRunStore } from '@/stores/run'

const route = useRoute()
const router = useRouter()
const runStore = useRunStore()
const repoStore = useRepoStore()

const runId = computed(() => String(route.params.id || ''))

function fmt(iso: string | null): string {
  return iso ? iso.replace('T', ' ').slice(0, 19) : '-'
}

onMounted(async () => {
  try {
    await runStore.attach(runId.value)
    const run = runStore.current
    if (run) {
      repoStore.tone = run.tone === 'tech' ? 'tech' : 'business'
      repoStore.mask = run.mask
    }
  } catch (err) {
    ElMessage.error(extractError(err))
    void router.replace('/history')
  }
})

onBeforeUnmount(() => {
  runStore.closeStream()
})
</script>

<style scoped>
.detail { display: flex; flex-direction: column; gap: 14px; }
.detail-meta { display: flex; flex-wrap: wrap; gap: 10px 26px; }
.meta-item { display: flex; gap: 8px; align-items: baseline; font-size: 13px; }
.detail-grid { display: grid; grid-template-columns: 0.9fr 1.1fr; gap: 14px; align-items: start; }
@media (max-width: 980px) {
  .detail-grid { grid-template-columns: 1fr; }
}
</style>
```

- [ ] **Step 4: ConsoleView.vue 增加运行态重连**

修改 `src/views/ConsoleView.vue` 的 `onMounted`（其余不变）：

```ts
onMounted(async () => {
  await store.loadRepos()
  // 从其他页面切回时，若当前运行仍在进行且流已断开，则重新订阅
  if (runStore.current && runStore.isActive && !runStore.handle) {
    runStore.connect(runStore.current.id)
  }
})
```

- [ ] **Step 5: 构建验证**

```powershell
cd doc-release\frontend
npm run build
```

Expected: 构建成功（vue-tsc 无类型错误）。

- [ ] **Step 6: 联调验证**

1. 在工作台完成至少 2 次运行（其中一次中途取消）
2. 顶部导航点「发布历史」：表格展示记录，时间/仓库/版本/范围/状态/耗时均正确，刷新按钮可用
3. 点「查看」进入详情页：步骤状态与终端日志完整回放（done 步骤带耗时），产物 tabs 可切换，口径/脱敏回放为该次运行的值
4. 对「运行中」的记录点查看：SSE 重新订阅，步骤与进度持续更新
5. 点「删除」：确认框确认后记录消失；后端归档目录下对应版本目录已同步删除（手工验证 `backend\\archive` 目录）
6. 详情页点「← 返回列表」回到列表

- [ ] **Step 7: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release/frontend
git commit -m 'feat(doc-release): Task 18 发布历史列表与详情页'
```

---

## Task 19: 收尾（运行中锁定、现场恢复、端到端冒烟与根 README）

**Files:**
- Modify: `doc-release/frontend/src/components/ControlBar.vue`（运行中禁用仓库/范围/场景/选项切换，对照设计 6.6）
- Modify: `doc-release/frontend/src/stores/run.ts`（startRun 记录 lastRun）
- Modify: `doc-release/frontend/src/views/ConsoleView.vue`（刷新后恢复现场）
- Modify: `README.md`（仓库根，增补 doc-release 小节，对照设计 11 交付物清单）

- [ ] **Step 1: ControlBar 运行中禁用切换**

按以下 5 处修改 `src/components/ControlBar.vue`（其余不变）：

1）仓库下拉：

```vue
<el-select v-model="repoModel" placeholder="选择仓库" style="width: 220px" :disabled="runStore.isActive">
```

2）场景 chips：

```vue
<button v-for="sc in store.scenarios" :key="sc.id" class="chip-btn"
        :class="{ 'chip-btn--active': sc.base === store.baseRef && sc.head === store.headRef }"
        :disabled="runStore.isActive" :title="sc.description" @click="store.applyScenario(sc)">
  {{ sc.name }} · {{ sc.version }}
</button>
```

3）范围双下拉与交换按钮：

```vue
<el-select v-model="baseModel" style="width: 148px" :disabled="runStore.isActive" @change="store.loadPreview()">
```

```vue
<button class="swap-btn" title="交换 base/head" :disabled="runStore.isActive" @click="store.swapRefs()">⇄</button>
```

```vue
<el-select v-model="headModel" style="width: 148px" :disabled="runStore.isActive" @change="store.loadPreview()">
```

4）版本号输入：

```vue
<el-input v-model="versionModel" style="width: 140px" placeholder="如 v2.14.0" :disabled="runStore.isActive" />
```

5）口径与脱敏：

```vue
<el-radio-group v-model="toneModel" size="small" :disabled="runStore.isActive">
```

```vue
<el-switch v-model="maskModel" :disabled="runStore.isActive" />
```

并在 ControlBar.vue 的 scoped style 末尾追加禁用态样式：

```css
.chip-btn:disabled, .swap-btn:disabled { opacity: .55; cursor: not-allowed; }
```

- [ ] **Step 2: 运行现场恢复（刷新 / 跨页面）**

修改 `src/stores/run.ts` 的 `startRun`（新增一行 localStorage 记录）：

```ts
    async startRun(
      repoId: number,
      payload: { base_ref: string; head_ref: string; version_label: string; tone: string; mask: boolean },
    ) {
      this.reset()
      const detail = await api.createRun({ repo_id: repoId, ...payload })
      localStorage.setItem('docrelease:lastRun', detail.id)
      this.applySnapshot(detail)
      this.connect(detail.id)
    },
```

修改 `src/views/ConsoleView.vue` 的 `onMounted`（在 Task 18 Step 4 基础上再补充刷新恢复分支）：

```ts
onMounted(async () => {
  await store.loadRepos()
  // 刷新页面后恢复现场：优先恢复最近一次运行
  if (!runStore.current) {
    const lastRun = localStorage.getItem('docrelease:lastRun')
    if (lastRun) {
      try {
        await runStore.attach(lastRun)
      } catch {
        localStorage.removeItem('docrelease:lastRun')
      }
    }
  }
  // 从其他页面切回时，若当前运行仍在进行且流已断开，则重新订阅
  if (runStore.current && runStore.isActive && !runStore.handle) {
    runStore.connect(runStore.current.id)
  }
})
```

- [ ] **Step 3: 全量构建与后端测试回归**

```powershell
cd doc-release\frontend
npm run build
```

Expected: 构建成功。

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

Expected: 全部通过。

```powershell
cd doc-release\backend
.\venv\Scripts\python.exe e2e_smoke.py
```

Expected: 三个场景 PASS + 「冒烟全部通过」，退出码 0。

- [ ] **Step 4: 端到端手动冒烟清单**

前后端同时启动，逐项验证（对应设计文档 §9 验收标准）：
1. 工作台默认选中 order-center，场景切换后 preview 与统计刷新正确
2. 运行 patch 场景：五步依次推进 → 状态「成功」→ 产物三 tabs 可看可导出
3. 运行中：仓库/场景/范围/选项控件均为禁用态，可点「取消」；重复点运行不可用
4. 产物 tab 内切「业务/技术」与脱敏：内容即时变化；下载文件与展示一致
5. 工作台运行中刷新页面：自动恢复现场（步骤状态与日志回放，运行中则继续流式推进）
6. 历史页：查看详情、回放日志与产物、删除记录后 `backend\\archive` 对应版本目录同步清理
7. 错误路径：注册非 git 目录弹错误提示；base/head 交换为同一引用后 preview 提示 422 错误不崩溃
8. 注册一个现有本地 git 仓库（非示例），能完成 preview 与一次运行（LLM 不可用时失败路径也可，链路不报错）

- [ ] **Step 5: 根 README 增补 doc-release 小节**

修改仓库根 `README.md`，共 3 处：

1）「项目总览」表格追加一行：

```markdown
| [doc-release](#5-doc-release) | 发布文档自动生成（释文） | 五步异步流水线 + SSE + tree-sitter AST + 星语 LLM |
```

2）在 `## 4. rag-knowledge-base` 小节结束的分隔线之后、`## 快速开始` 之前插入：

```markdown
## 5. doc-release

> 输入任意 git 仓库的变更范围（base..head），自动生成发布文档三件套：发布检查清单（CSV）、产品说明（Markdown）、溯源数据（JSON）。

**核心能力：**
- **五步异步流水线**：定位范围 → 收集 diff → tree-sitter AST 解析 → LLM 业务化改写 → 确定性渲染并归档
- **SSE 实时推送**：步骤状态 / 终端日志 / 进度事件驱动三栏工作台；断线指数退避重连、刷新恢复现场
- **结构化中间层**：LLM 只产出 JSON 功能点，产物由确定性渲染器生成，可溯源可比对
- **内置示例仓库**：order-center 含补丁 / 功能 / 大版本三大变更场景，首次启动自动生成
- **发布历史**：运行回看、按口径（业务/技术）与脱敏开关即时重渲染、导出与删除

```
doc-release/
├── backend/     # FastAPI + 五步流水线 + tree-sitter + SSE
└── frontend/    # Vue 3 + Element Plus 三栏工作台 + 发布历史
```
```

3）「项目架构」代码树中，`├── rag-knowledge-base/` 块之后、`└── docs/` 之前插入：

```
├── doc-release/             # ⑤ 发布文档自动生成（释文）
│   ├── backend/             #   五步流水线 + tree-sitter + 星语 LLM
│   └── frontend/            #   Vue 3 三栏工作台 + 发布历史
```

- [ ] **Step 6: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git status --short
git add doc-release README.md
git commit -m 'feat(doc-release): Task 19 收尾、现场恢复与根 README'
```
