# 内容生产发布工作台实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建独立应用 `content-workbench`：输入活动主题与文本资料，按类型一键生成有据可查的公告/FAQ/海报文案，覆盖式编辑＋审核门禁＋角色分离＋审计日志，通过后下载 Markdown/HTML 或创建模拟发布任务。

**Architecture:** 前后端分离。后端 FastAPI＋SQLAlchemy(async)＋SQLite，服务层含纯函数式证据检索、协议化生成器（DeepSeek 客户端＋测试 Fake）、类型化输出校验、导出渲染器、模拟发布适配器；前端 Vue 3＋TS＋Element Plus，分角色页面。规格见 `docs/superpowers/specs/2026-10-13-content-generation-workbench-design.md`。

**Tech Stack:** Python 3.11（fastapi、sqlalchemy[asyncio]、aiosqlite、httpx、pydantic-settings、pytest、pytest-asyncio）｜Node.js（vue3、vue-router、element-plus、axios、vite、typescript、vue-tsc）

**关键决策（实现者无需再做选择）：**
- 应用目录 `content-workbench/{backend,frontend}`，后端端口 8000，前端 Vite 代理 `/api`。
- 认证：users/tokens 表，PBKDF2 口令哈希，Bearer Token；启动时种子账号 `editor/editor123`、`reviewer/review123`。
- 角色：仅 `editor`/`reviewer`；规格中的"管理员查看审计"由 `reviewer` 承担。
- 状态机 `draft → pending_review → approved|rejected`；`pending_review` 锁编辑；编辑 approved 自动回落 draft 并审计前后快照；draft/rejected 可提交审核。
- citations 存 `{source_id, text}`（片段原文随引用保存，审核面板直接展示）。
- LLM 无 Key 时由 `get_generator` 依赖抛 422；测试统一 override 为 FakeGenerator。
- 模型输出约定为 `{"assets": [...]}` JSON 对象（兼容 json_object 模式）。
- 前端验证方式：`npm run build`（vue-tsc 类型检查）＋任务 17 冒烟清单（与仓库既有前端验证惯例一致，不引入组件测试框架）。
- PowerShell 下 git commit 消息一律用单引号。
- 后端依赖版本沿用仓库既有项目：`fastapi==0.141.1`、`uvicorn==0.52.4`、`sqlalchemy==2.0.52`、`aiosqlite==0.20.0`、`pydantic-settings==2.15.0`、`httpx==0.28.1`、`pytest==9.1.1`、`pytest-asyncio==1.3.0`。

---

### Task 1: 后端项目骨架与测试基建

**Files:**
- Create: `content-workbench/backend/requirements.txt`
- Create: `content-workbench/backend/pytest.ini`
- Create: `content-workbench/backend/.gitignore`
- Create: `content-workbench/backend/app/__init__.py`
- Create: `content-workbench/backend/app/config.py`
- Create: `content-workbench/backend/app/database.py`
- Create: `content-workbench/backend/app/audit.py`
- Create: `content-workbench/backend/app/auth.py`
- Create: `content-workbench/backend/app/models/__init__.py`
- Create: `content-workbench/backend/app/models/content.py`
- Create: `content-workbench/backend/app/api/__init__.py`
- Create: `content-workbench/backend/app/api/router.py`
- Create: `content-workbench/backend/app/api/auth.py`
- Create: `content-workbench/backend/app/main.py`
- Create: `content-workbench/backend/tests/__init__.py`
- Create: `content-workbench/backend/tests/conftest.py`
- Create: `content-workbench/backend/tests/test_smoke.py`
- Create: `content-workbench/backend/tests/test_auth.py`

- [ ] **Step 1: 创建目录与依赖文件**

```powershell
mkdir content-workbench\backend\app\models, content-workbench\backend\app\api, content-workbench\backend\tests
```

`requirements.txt`：

```
fastapi==0.141.1
uvicorn==0.52.4
sqlalchemy==2.0.52
aiosqlite==0.20.0
pydantic-settings==2.15.0
httpx==0.28.1
pytest==9.1.1
pytest-asyncio==1.3.0
```

`pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
```

`.gitignore`：

```
venv/
__pycache__/
*.db
.pytest_cache/
.env
```

- [ ] **Step 2: 配置、数据库、审计助手**

`app/config.py`：

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./workbench.db"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    max_evidence_chunks: int = 6


settings = Settings()
```

`app/database.py`：

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        yield session
```

`app/audit.py`：

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import AuditLog


async def record_audit(db: AsyncSession, actor: str, action: str, object_type: str, object_id: str, detail: dict | None = None) -> None:
    db.add(AuditLog(actor=actor, action=action, object_type=object_type, object_id=object_id, detail=detail))
    await db.commit()
```

- [ ] **Step 3: 认证助手（口令、种子、角色依赖）**

`app/auth.py`：

```python
import hashlib
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.content import Token, User

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(8).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 10000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
    except ValueError:
        return False
    return hash_password(password, salt) == stored


async def seed_users(db: AsyncSession) -> None:
    if not (await db.scalars(select(User).limit(1))).first():
        db.add_all([
            User(username="editor", password_hash=hash_password("editor123"), role="editor"),
            User(username="reviewer", password_hash=hash_password("review123"), role="reviewer"),
        ])
        await db.commit()


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer), db: AsyncSession = Depends(get_db)) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    row = (await db.scalars(select(Token).where(Token.token == credentials.credentials))).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")
    return await db.get(User, row.user_id)


def require_role(role: str):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"需要 {role} 角色")
        return user
    return dependency
```

- [ ] **Step 4: 数据模型（全部实体）**

`app/models/content.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(16))


class Token(Base):
    __tablename__ = "tokens"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ContentProject(Base):
    __tablename__ = "content_projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    theme: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(200))
    tone: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("content_projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ContentAsset(Base):
    __tablename__ = "content_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("content_projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    content: Mapped[dict] = mapped_column(JSON)
    citations: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReviewRecord(Base):
    __tablename__ = "review_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("content_assets.id"), index=True)
    decision: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str] = mapped_column(Text, default="")
    reviewer: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DeliveryTask(Base):
    __tablename__ = "delivery_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("content_assets.id"), index=True)
    channel: Mapped[str] = mapped_column(String(32), default="mock")
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    object_type: Mapped[str] = mapped_column(String(32))
    object_id: Mapped[str] = mapped_column(String(36), index=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 5: 登录路由、应用入口、路由装配**

`app/api/auth.py`：

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, verify_password
from app.database import get_db
from app.models.content import Token, User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginPayload(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(payload: LoginPayload, db: AsyncSession = Depends(get_db)) -> dict:
    user = (await db.scalars(select(User).where(User.username == payload.username))).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = uuid.uuid4().hex
    db.add(Token(token=token, user_id=user.id))
    await db.commit()
    return {"token": token, "username": user.username, "role": user.role}


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> dict:
    return {"username": user.username, "role": user.role}
```

`app/api/router.py`：

```python
from fastapi import APIRouter

from app.api import auth as auth_api

api_router = APIRouter()
api_router.include_router(auth_api.router)
```

`app/main.py`：

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.auth import seed_users
from app.database import Base, SessionLocal, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        await seed_users(db)
    yield


app = FastAPI(title="Content Workbench", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router, prefix="/api")
```

- [ ] **Step 6: 测试基建（conftest + smoke + auth）**

`tests/conftest.py`：

```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models.content import User


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    async with session_factory() as session:
        session.add_all([
            User(username="editor", password_hash=hash_password("editor123"), role="editor"),
            User(username="reviewer", password_hash=hash_password("review123"), role="reviewer"),
        ])
        await session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def editor_headers(client) -> dict:
    response = await client.post("/api/auth/login", json={"username": "editor", "password": "editor123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest_asyncio.fixture
async def reviewer_headers(client) -> dict:
    response = await client.post("/api/auth/login", json={"username": "reviewer", "password": "review123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}
```

`tests/test_smoke.py`：

```python
async def test_app_starts(client):
    response = await client.get("/docs")
    assert response.status_code == 200
```

`tests/test_auth.py`：

```python
async def test_login_success(client):
    response = await client.post("/api/auth/login", json={"username": "editor", "password": "editor123"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "editor" and body["token"]


async def test_login_wrong_password(client):
    response = await client.post("/api/auth/login", json={"username": "editor", "password": "bad"})
    assert response.status_code == 401


async def test_missing_token_rejected(client):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_me_returns_role(client, editor_headers):
    response = await client.get("/api/auth/me", headers=editor_headers)
    assert response.status_code == 200 and response.json()["role"] == "editor"
```

- [ ] **Step 7: 安装依赖并运行测试**

```powershell
cd content-workbench\backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m pytest tests/test_auth.py tests/test_smoke.py -v
```

Expected: 5 passed。

- [ ] **Step 8: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench/backend
git commit -m 'feat(workbench): 后端骨架、认证与测试基建'
```

---

### Task 2: 项目与资料管理 API

**Files:**
- Create: `content-workbench/backend/app/api/projects.py`
- Modify: `content-workbench/backend/app/api/router.py`
- Test: `content-workbench/backend/tests/test_projects.py`

- [ ] **Step 1: 写失败测试**

`tests/test_projects.py`：

```python
async def _create_project(client, headers, name="V2 发布") -> dict:
    payload = {"name": name, "theme": "智能报表 2.0", "audience": "企业数据分析师", "tone": "专业"}
    response = await client.post("/api/projects", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


async def test_create_project(client, editor_headers):
    project = await _create_project(client, editor_headers)
    assert project["theme"] == "智能报表 2.0"


async def test_editor_role_required(client, reviewer_headers):
    response = await client.post("/api/projects", json={"name": "x", "theme": "t", "audience": "a"}, headers=reviewer_headers)
    assert response.status_code == 403


async def test_list_projects(client, editor_headers):
    await _create_project(client, editor_headers)
    response = await client.get("/api/projects", headers=editor_headers)
    assert response.status_code == 200 and len(response.json()) == 1


async def test_source_dedup_by_hash(client, editor_headers):
    project = await _create_project(client, editor_headers)
    body = {"name": "操作手册", "content": "第一段。智能报表支持拖拽分析。\n\n第二段。"}
    first = await client.post(f"/api/projects/{project['id']}/sources", json=body, headers=editor_headers)
    second = await client.post(f"/api/projects/{project['id']}/sources", json=body, headers=editor_headers)
    assert first.status_code == 201 and second.status_code == 409


async def test_delete_project_cascades(client, editor_headers):
    project = await _create_project(client, editor_headers)
    await client.post(f"/api/projects/{project['id']}/sources", json={"name": "s", "content": "内容。"}, headers=editor_headers)
    assert (await client.delete(f"/api/projects/{project['id']}", headers=editor_headers)).status_code == 204
    assert (await client.get(f"/api/projects/{project['id']}/sources", headers=editor_headers)).status_code == 404
```

- [ ] **Step 2: 运行确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_projects.py -v
```

Expected: FAIL（404）。

- [ ] **Step 3: 实现**

`app/api/projects.py`：

```python
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import require_role
from app.database import get_db
from app.models.content import ContentAsset, ContentProject, DeliveryTask, ReviewRecord, Source, User

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectPayload(BaseModel):
    name: str
    theme: str
    audience: str
    tone: str = ""


class SourcePayload(BaseModel):
    name: str
    content: str


async def _load_project(db: AsyncSession, project_id: str) -> ContentProject:
    project = await db.get(ContentProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.post("", status_code=201)
async def create_project(payload: ProjectPayload, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("editor"))) -> dict:
    project = ContentProject(name=payload.name, theme=payload.theme, audience=payload.audience, tone=payload.tone)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    await record_audit(db, user.username, "create_project", "project", project.id)
    return _serialize(project)


@router.get("")
async def list_projects(db: AsyncSession = Depends(get_db), _: User = Depends(require_role("editor"))) -> list[dict]:
    projects = list((await db.scalars(select(ContentProject).order_by(ContentProject.created_at.desc()))).all())
    return [_serialize(project) for project in projects]


@router.get("/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("editor"))) -> dict:
    return _serialize(await _load_project(db, project_id))


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("editor"))) -> None:
    project = await _load_project(db, project_id)
    assets = list((await db.scalars(select(ContentAsset).where(ContentAsset.project_id == project_id))).all())
    for asset in assets:
        for row in (await db.scalars(select(ReviewRecord).where(ReviewRecord.asset_id == asset.id))).all():
            await db.delete(row)
        for row in (await db.scalars(select(DeliveryTask).where(DeliveryTask.asset_id == asset.id))).all():
            await db.delete(row)
        await db.delete(asset)
    for source in (await db.scalars(select(Source).where(Source.project_id == project_id))).all():
        await db.delete(source)
    await db.delete(project)
    await db.commit()
    await record_audit(db, user.username, "delete_project", "project", project_id)


@router.post("/{project_id}/sources", status_code=201)
async def add_source(project_id: str, payload: SourcePayload, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("editor"))) -> dict:
    await _load_project(db, project_id)
    content_hash = hashlib.sha256(payload.content.encode()).hexdigest()
    exists = (await db.scalars(select(Source).where(Source.project_id == project_id, Source.content_hash == content_hash))).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="资料内容重复")
    source = Source(project_id=project_id, name=payload.name, content=payload.content, content_hash=content_hash)
    db.add(source)
    await db.commit()
    await db.refresh(source)
    await record_audit(db, user.username, "add_source", "source", source.id, detail={"project_id": project_id})
    return {"id": source.id, "name": source.name, "created_at": str(source.created_at)}


@router.get("/{project_id}/sources")
async def list_sources(project_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("editor"))) -> list[dict]:
    await _load_project(db, project_id)
    sources = list((await db.scalars(select(Source).where(Source.project_id == project_id))).all())
    return [{"id": s.id, "name": s.name, "created_at": str(s.created_at)} for s in sources]


@router.delete("/{project_id}/sources/{source_id}", status_code=204)
async def delete_source(project_id: str, source_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("editor"))) -> None:
    await _load_project(db, project_id)
    source = await db.get(Source, source_id)
    if source is None or source.project_id != project_id:
        raise HTTPException(status_code=404, detail="资料不存在")
    await db.delete(source)
    await db.commit()
    await record_audit(db, user.username, "delete_source", "source", source_id, detail={"project_id": project_id})


def _serialize(project: ContentProject) -> dict:
    return {"id": project.id, "name": project.name, "theme": project.theme, "audience": project.audience, "tone": project.tone, "created_at": str(project.created_at)}
```

`app/api/router.py` 追加：

```python
from app.api import projects as projects_api
api_router.include_router(projects_api.router)
```

- [ ] **Step 4: 运行确认通过**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_projects.py -v
```

Expected: 6 passed。

- [ ] **Step 5: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench/backend
git commit -m 'feat(workbench): 项目与资料管理 API'
```

---

### Task 3: 证据检索服务

**Files:**
- Create: `content-workbench/backend/app/services/__init__.py`
- Create: `content-workbench/backend/app/services/retrieval.py`
- Test: `content-workbench/backend/tests/test_retrieval.py`

- [ ] **Step 1: 写失败测试**

`tests/test_retrieval.py`：

```python
from app.services.retrieval import select_evidence, split_and_rank


def test_split_blank_lines_and_sentences():
    text = "智能报表支持拖拽分析。\n\n另外还支持导出 Excel 文件！"
    pieces = split_and_rank(text, "s1", ["智能报表"])
    assert {p.text for p in pieces} == {"智能报表支持拖拽分析。", "另外还支持导出 Excel 文件！"}


def test_short_noise_dropped():
    pieces = split_and_rank("好的。好的。", "s1", ["x"])
    assert pieces == []


def test_score_counts_keyword_hits_and_orders():
    text = "智能报表 2.0 支持拖拽分析，智能报表还能定时推送。"
    pieces = split_and_rank(text, "s1", ["智能报表", "拖拽"])
    assert pieces[0].score == 2


def test_select_dedup_orders_and_filters_zero():
    sources = [("s1", "智能报表支持导出。"), ("s2", "智能报表支持导出。无关键词段落。"), ("s3", "完全无关的内容。")]
    evidence = select_evidence(sources, ["智能报表", "导出"], top_k=2)
    assert len(evidence) == 1 and evidence[0].source_id in {"s1", "s2"}


def test_select_returns_top_k():
    sources = [("s1", "A关键词。B关键词。C关键词。"), ("s2", "D关键词。")]
    evidence = select_evidence(sources, ["A关键词", "B关键词", "C关键词", "D关键词"], top_k=2)
    assert len(evidence) == 2 and evidence[0].score == 1
```

- [ ] **Step 2: 运行确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_retrieval.py -v
```

Expected: FAIL（ModuleNotFoundError）。

- [ ] **Step 3: 实现**

`app/services/retrieval.py`：

```python
import re
from dataclasses import dataclass


@dataclass
class Evidence:
    source_id: str
    text: str
    score: int


def split_and_rank(text: str, source_id: str, keywords: list[str]) -> list[Evidence]:
    keywords = [keyword.strip() for keyword in keywords if keyword and keyword.strip()]
    pieces = []
    for block in re.split(r"\n\s*\n", text):
        for piece in re.split(r"(?<=[。！？])\s*", block):
            piece = piece.strip()
            if len(piece) < 15:
                continue
            score = sum(1 for keyword in keywords if keyword in piece)
            pieces.append(Evidence(source_id=source_id, text=piece, score=score))
    return pieces


def select_evidence(sources: list[tuple[str, str]], keywords: list[str], top_k: int) -> list[Evidence]:
    seen = set()
    candidates = []
    for source_id, content in sources:
        for evidence in split_and_rank(content, source_id, keywords):
            if evidence.text in seen:
                continue
            seen.add(evidence.text)
            if evidence.score > 0:
                candidates.append(evidence)
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:top_k]
```

- [ ] **Step 4: 运行确认通过**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_retrieval.py -v
```

Expected: 5 passed。

- [ ] **Step 5: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench/backend
git commit -m 'feat(workbench): 纯函数式证据检索服务'
```

---

### Task 4: 生成器协议、DeepSeek 客户端、类型校验器与 Fake

**Files:**
- Create: `content-workbench/backend/app/services/generation.py`
- Modify: `content-workbench/backend/tests/conftest.py`（override get_generator）
- Create: `content-workbench/backend/tests/helpers.py`
- Test: `content-workbench/backend/tests/test_generation_service.py`

- [ ] **Step 1: 写失败测试**

`tests/test_generation_service.py`：

```python
import json
import pytest
from app.services.generation import FakeGenerator, GenerationValidationError, validate_generation

ALLOWED = {"s1": "智能报表支持拖拽分析。", "s2": "支持导出 Excel。"}


def test_validate_accepts_complete_output():
    items = FakeGenerator.build(["s1", "s2"], theme="智能报表", audience="分析师")
    results = validate_generation(items, ALLOWED)
    assert {kind for kind, _, _ in results} == {"announcement", "faq", "poster"}
    assert results[0][2][0]["text"] == "智能报表支持拖拽分析。"


def test_validate_rejects_unknown_source():
    items = FakeGenerator.build(["sX"], theme="t", audience="a")
    with pytest.raises(GenerationValidationError):
        validate_generation(items, ALLOWED)


def test_validate_rejects_missing_field():
    items = FakeGenerator.build(["s1"], theme="t", audience="a")
    items[0]["content"].pop("title")
    with pytest.raises(GenerationValidationError):
        validate_generation(items, ALLOWED)


def test_validate_rejects_incomplete_kinds():
    items = [item for item in FakeGenerator.build(["s1"], theme="t", audience="a") if item["kind"] != "poster"]
    with pytest.raises(GenerationValidationError):
        validate_generation(items, ALLOWED)


def test_validate_rejects_empty_faq_item_citations():
    items = FakeGenerator.build(["s1"], theme="t", audience="a")
    items[1]["content"]["items"][0]["source_ids"] = []
    with pytest.raises(GenerationValidationError):
        validate_generation(items, ALLOWED)


def test_fake_parses_assets_wrapper():
    payload = json.dumps({"assets": FakeGenerator.build(["s1"], theme="t", audience="a")}, ensure_ascii=False)
    items = json.loads(payload)["assets"]
    assert len(items) == 3
```

- [ ] **Step 2: 运行确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_generation_service.py -v
```

Expected: FAIL（ModuleNotFoundError）。

- [ ] **Step 3: 实现**

`app/services/generation.py`：

```python
import json
import logging
from typing import Any, Protocol
import httpx

logger = logging.getLogger(__name__)

SCHEMAS: dict[str, dict[str, type]] = {
    "announcement": {"title": str, "summary": str, "body": str, "actions": list},
    "faq": {"items": list},
    "poster": {"headline": str, "subhead": str, "selling_points": list, "cta": str},
}
KINDS = frozenset(SCHEMAS)

PROMPT = """你是产品内容生成助手。仅依据给定证据资料生成公告、FAQ、海报文案，禁止使用证据之外的产品事实。
只输出 JSON 对象 {"assets": [...]}，数组元素形如：
{"kind": "announcement", "content": {"title": "...", "summary": "...", "body": "...", "actions": ["..."]}, "source_ids": ["s1"]}
{"kind": "faq", "content": {"items": [{"question": "...", "answer": "...", "source_ids": ["s1"]}]}, "source_ids": ["s1"]}
{"kind": "poster", "content": {"headline": "...", "subhead": "...", "selling_points": ["..."], "cta": "..."}, "source_ids": ["s1"]}
source_ids 只能取自证据给出的 source_id。"""


class ContentGenerator(Protocol):
    async def generate(self, theme: str, audience: str, evidence: list[dict]) -> list[dict]: ...


class DeepSeekGenerator:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(self, theme: str, audience: str, evidence: list[dict]) -> list[dict]:
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": json.dumps({"theme": theme, "audience": audience, "evidence": evidence}, ensure_ascii=False)},
            ],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        return data["assets"] if isinstance(data, dict) else data


class FakeGenerator:
    async def generate(self, theme: str, audience: str, evidence: list[dict]) -> list[dict]:
        ids = [item["source_id"] for item in evidence]
        text = evidence[0]["text"] if evidence else "智能报表支持拖拽分析与导出。"
        return self.build(ids, theme=theme, audience=audience, text=text)

    @staticmethod
    def build(source_ids: list[str], theme: str, audience: str, text: str = "智能报表支持拖拽分析与导出。") -> list[dict]:
        ids = list(source_ids)
        return [
            {"kind": "announcement", "content": {"title": f"{theme}正式发布", "summary": text[:50], "body": text, "actions": ["查看详情"]}, "source_ids": ids},
            {"kind": "faq", "content": {"items": [{"question": f"什么是{theme}？", "answer": text[:50], "source_ids": ids}]}, "source_ids": ids},
            {"kind": "poster", "content": {"headline": theme, "subhead": audience, "selling_points": [text[:20]], "cta": "立即了解"}, "source_ids": ids},
        ]


class GenerationValidationError(ValueError):
    pass


def _citations(node: dict, allowed: dict[str, str]) -> list[dict]:
    ids = node.get("source_ids")
    if not isinstance(ids, list) or not ids:
        raise GenerationValidationError("缺少来源引用")
    citations = []
    for source_id in ids:
        if source_id not in allowed:
            raise GenerationValidationError("引用了未知来源")
        citations.append({"source_id": source_id, "text": allowed[source_id]})
    return citations


def validate_kind_content(kind: str, content: dict) -> None:
    schema = SCHEMAS.get(kind)
    if schema is None or not isinstance(content, dict):
        raise GenerationValidationError("内容类型或结构非法")
    for field, field_type in schema.items():
        if not isinstance(content.get(field), field_type):
            raise GenerationValidationError(f"字段 {field} 缺失或类型错误")
    if kind == "faq":
        for entry in content["items"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("question"), str) or not isinstance(entry.get("answer"), str):
                raise GenerationValidationError("FAQ 问答项结构非法")


def validate_generation(items: list[dict], allowed: dict[str, str]) -> list[tuple[str, dict, list[dict]]]:
    results = []
    for item in items:
        kind, content = item.get("kind"), item.get("content")
        validate_kind_content(kind, content)
        if kind == "faq":
            citations = []
            for entry in content["items"]:
                citations.extend(_citations(entry, allowed))
        else:
            citations = _citations(item, allowed)
        unique = list({(c["source_id"], c["text"]): c for c in citations}.values())
        results.append((kind, content, unique))
    if {kind for kind, _, _ in results} != KINDS:
        raise GenerationValidationError("未生成完整的三类内容")
    return results


def parse_model_output(raw: Any) -> list[dict]:
    data = raw["assets"] if isinstance(raw, dict) else raw
    if not isinstance(data, list):
        raise GenerationValidationError("模型输出结构非法")
    return data
```

- [ ] **Step 4: 创建测试辅助 helpers**

`tests/helpers.py`：

```python
async def setup_project_with_source(client, editor_headers, theme="智能报表 2.0", content="智能报表 2.0 支持拖拽分析与一键导出，面向数据分析师。") -> str:
    project = (await client.post("/api/projects", json={"name": "V2", "theme": theme, "audience": "数据分析师"}, headers=editor_headers)).json()
    await client.post(f"/api/projects/{project['id']}/sources", json={"name": "手册", "content": content}, headers=editor_headers)
    return project["id"]
```

- [ ] **Step 5: 运行确认通过**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_generation_service.py -v
```

Expected: 6 passed。

- [ ] **Step 6: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench/backend
git commit -m 'feat(workbench): 生成器协议、DeepSeek 客户端与类型化校验'
```

---

### Task 5: 一键生成 API（拒答规则＋审计）

**Files:**
- Create: `content-workbench/backend/app/api/generation.py`
- Modify: `content-workbench/backend/app/api/router.py`
- Test: `content-workbench/backend/tests/test_generation_api.py`

- [ ] **Step 1: 写失败测试**

`tests/test_generation_api.py`：

```python
from tests.helpers import setup_project_with_source


async def test_generate_creates_three_assets(client, editor_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    response = await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)
    assert response.status_code == 201
    assets = response.json()
    assert {a["kind"] for a in assets} == {"announcement", "faq", "poster"}
    assert all(a["citations"] and a["citations"][0]["text"] for a in assets)


async def test_generate_without_sources_rejected(client, editor_headers):
    project = (await client.post("/api/projects", json={"name": "V2", "theme": "主题X", "audience": "用户"}, headers=editor_headers)).json()
    response = await client.post(f"/api/projects/{project['id']}/generate", headers=editor_headers)
    assert response.status_code == 422 and "需补充资料" in response.json()["detail"]


async def test_generate_irrelevant_sources_rejected(client, editor_headers):
    project_id = await setup_project_with_source(client, editor_headers, theme="完全无关主题Z")
    response = await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)
    assert response.status_code == 422 and "需补充资料" in response.json()["detail"]


async def test_generate_editor_only(client, reviewer_headers, editor_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    response = await client.post(f"/api/projects/{project_id}/generate", headers=reviewer_headers)
    assert response.status_code == 403
```

- [ ] **Step 2: 运行确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_generation_api.py -v
```

Expected: FAIL（404）。

- [ ] **Step 3: 实现**

`app/api/generation.py`：

```python
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import require_role
from app.config import settings
from app.database import get_db
from app.models.content import ContentAsset, ContentProject, Source, User
from app.services.generation import ContentGenerator, DeepSeekGenerator, GenerationValidationError, parse_model_output, validate_generation
from app.services.retrieval import select_evidence

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}", tags=["generation"])


def get_generator() -> ContentGenerator:
    if not settings.deepseek_api_key:
        raise HTTPException(status_code=422, detail="未配置 DeepSeek API Key")
    return DeepSeekGenerator(settings.deepseek_api_key, settings.deepseek_base_url, settings.deepseek_model)


@router.get("/assets")
async def list_assets(project_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("editor"))) -> list[dict]:
    assets = list((await db.scalars(select(ContentAsset).where(ContentAsset.project_id == project_id))).all())
    return [_serialize(asset) for asset in assets]


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_assets(project_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("editor")), generator: ContentGenerator = Depends(get_generator)) -> list[dict]:
    project = await db.get(ContentProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    sources = list((await db.scalars(select(Source).where(Source.project_id == project_id))).all())
    if not sources:
        raise HTTPException(status_code=422, detail="需补充资料")
    evidence = select_evidence([(s.id, s.content) for s in sources], [project.theme, project.audience], settings.max_evidence_chunks)
    if not evidence:
        raise HTTPException(status_code=422, detail="需补充资料")
    allowed = {item.source_id: item.text for item in evidence}
    try:
        raw = await generator.generate(project.theme, project.audience, [{"source_id": k, "text": v} for k, v in allowed.items()])
        results = validate_generation(parse_model_output(raw), allowed)
    except GenerationValidationError as error:
        logger.warning("生成内容校验失败: %s", error)
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.error("内容生成失败: %s", error, exc_info=True)
        raise HTTPException(status_code=502, detail="内容生成失败，请稍后重试") from error
    assets = [ContentAsset(project_id=project_id, kind=kind, content=content, citations=citations) for kind, content, citations in results]
    db.add_all(assets)
    await db.commit()
    for asset in assets:
        await db.refresh(asset)
    await record_audit(db, user.username, "generate_assets", "project", project_id, detail={"kinds": sorted(a.kind for a in assets)})
    return [_serialize(asset) for asset in assets]


def _serialize(asset: ContentAsset) -> dict:
    return {"id": asset.id, "kind": asset.kind, "status": asset.status, "content": asset.content, "citations": asset.citations}
```

`app/api/router.py` 追加：

```python
from app.api import generation as generation_api
api_router.include_router(generation_api.router)
```

- [ ] **Step 4: 修改 conftest 注入 Fake**

在 `tests/conftest.py` 的 `client` fixture 里，在 `app.dependency_overrides[get_db] = override_db` 之后追加：

```python
    from app.api.generation import get_generator
    from app.services.generation import FakeGenerator
    app.dependency_overrides[get_generator] = lambda: FakeGenerator()
```

- [ ] **Step 5: 运行确认通过**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_generation_api.py tests/test_smoke.py -v
```

Expected: 全部 passed。

- [ ] **Step 5: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench/backend
git commit -m 'feat(workbench): 证据约束一键生成 API 与拒答规则'
```

---

### Task 6: 编辑、提交与审核（状态机＋审计快照）

**Files:**
- Create: `content-workbench/backend/app/api/assets.py`
- Modify: `content-workbench/backend/app/api/router.py`
- Test: `content-workbench/backend/tests/test_assets.py`

- [ ] **Step 1: 写失败测试**

`tests/test_assets.py`：

```python
from tests.helpers import setup_project_with_source


async def _draft_asset(client, editor_headers) -> dict:
    project_id = await setup_project_with_source(client, editor_headers)
    assets = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()
    return assets[0]


async def test_edit_draft(client, editor_headers):
    asset = await _draft_asset(client, editor_headers)
    content = dict(asset["content"])
    content["summary"] = "人工润色后的摘要"
    response = await client.put(f"/api/assets/{asset['id']}", json={"content": content}, headers=editor_headers)
    assert response.status_code == 200 and response.json()["content"]["summary"] == "人工润色后的摘要"


async def test_edit_approved_resets_to_draft(client, editor_headers, reviewer_headers):
    asset = await _draft_asset(client, editor_headers)
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    await client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "approved"}, headers=reviewer_headers)
    response = await client.put(f"/api/assets/{asset['id']}", json={"content": asset["content"]}, headers=editor_headers)
    assert response.status_code == 200 and response.json()["status"] == "draft"


async def test_edit_pending_review_rejected(client, editor_headers):
    asset = await _draft_asset(client, editor_headers)
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    response = await client.put(f"/api/assets/{asset['id']}", json={"content": asset["content"]}, headers=editor_headers)
    assert response.status_code == 409


async def test_reviewer_only(client, editor_headers):
    asset = await _draft_asset(client, editor_headers)
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    response = await client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "approved"}, headers=editor_headers)
    assert response.status_code == 403


async def test_review_rejected_with_comment(client, editor_headers, reviewer_headers):
    asset = await _draft_asset(client, editor_headers)
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    response = await client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "rejected", "comment": "标题不准确"}, headers=reviewer_headers)
    assert response.status_code == 200 and response.json()["status"] == "rejected"
    assert (await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)).status_code == 200
```

- [ ] **Step 2: 运行确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_assets.py -v
```

Expected: FAIL。

- [ ] **Step 3: 实现**

`app/api/assets.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import get_current_user, require_role
from app.database import get_db
from app.models.content import ContentAsset, ReviewRecord, User
from app.services.generation import GenerationValidationError, validate_kind_content

router = APIRouter(prefix="/assets", tags=["assets"])


class EditPayload(BaseModel):
    content: dict


class ReviewPayload(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    comment: str = ""


async def _load_asset(db: AsyncSession, asset_id: str) -> ContentAsset:
    asset = await db.get(ContentAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="资产不存在")
    return asset


@router.put("/{asset_id}")
async def edit_asset(asset_id: str, payload: EditPayload, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("editor"))) -> dict:
    asset = await _load_asset(db, asset_id)
    if asset.status == "pending_review":
        raise HTTPException(status_code=409, detail="审核中不可编辑")
    try:
        validate_kind_content(asset.kind, payload.content)
    except GenerationValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    before = asset.content
    asset.content = payload.content
    reset = asset.status == "approved"
    if reset:
        asset.status = "draft"
    await db.commit()
    await record_audit(db, user.username, "edit_asset", "asset", asset.id, detail={"before": before, "after": payload.content, "status_reset": reset})
    return {"id": asset.id, "kind": asset.kind, "status": asset.status, "content": asset.content}


@router.post("/{asset_id}/submit")
async def submit_asset(asset_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("editor"))) -> dict:
    asset = await _load_asset(db, asset_id)
    if asset.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=409, detail="当前状态不可提交审核")
    asset.status = "pending_review"
    await db.commit()
    await record_audit(db, user.username, "submit_asset", "asset", asset.id)
    return {"id": asset.id, "status": asset.status}


@router.post("/{asset_id}/reviews")
async def review_asset(asset_id: str, payload: ReviewPayload, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("reviewer"))) -> dict:
    asset = await _load_asset(db, asset_id)
    if asset.status != "pending_review":
        raise HTTPException(status_code=409, detail="资产不在审核中")
    asset.status = payload.decision
    db.add(ReviewRecord(asset_id=asset_id, decision=payload.decision, comment=payload.comment, reviewer=user.username))
    await db.commit()
    await record_audit(db, user.username, "review_asset", "asset", asset.id, detail={"decision": payload.decision, "comment": payload.comment})
    return {"id": asset.id, "status": asset.status}


@router.get("/{asset_id}/citations")
async def get_citations(asset_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    asset = await _load_asset(db, asset_id)
    return asset.citations
```

`app/api/router.py` 追加：

```python
from app.api import assets as assets_api
api_router.include_router(assets_api.router)
```

- [ ] **Step 4: 运行确认通过**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_assets.py -v
```

Expected: 6 passed。

- [ ] **Step 5: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench/backend
git commit -m 'feat(workbench): 资产编辑、提交与审核状态机'
```

---

### Task 7: 导出渲染器与下载 API

**Files:**
- Create: `content-workbench/backend/app/export/__init__.py`
- Create: `content-workbench/backend/app/export/renderers.py`
- Modify: `content-workbench/backend/app/api/assets.py`（追加下载端点）
- Test: `content-workbench/backend/tests/test_export.py`
- Test: `content-workbench/backend/tests/test_download.py`

- [ ] **Step 1: 写失败测试**

`tests/test_export.py`：

```python
from app.export.renderers import render_html, render_markdown


def test_render_announcement():
    content = {"title": "T", "summary": "S", "body": "B", "actions": ["A1"]}
    assert "# T" in render_markdown("announcement", content)
    assert "<h1>T</h1>" in render_html("announcement", content)


def test_render_faq():
    content = {"items": [{"question": "Q", "answer": "A"}]}
    assert "Q" in render_markdown("faq", content)
    assert "<dt>Q</dt>" in render_html("faq", content)


def test_render_poster():
    content = {"headline": "H", "subhead": "S", "selling_points": ["P"], "cta": "C"}
    assert "H" in render_markdown("poster", content)
    assert "H</h1>" in render_html("poster", content)
```

`tests/test_download.py`：

```python
from tests.helpers import setup_project_with_source


async def _approved_asset(client, editor_headers, reviewer_headers) -> dict:
    project_id = await setup_project_with_source(client, editor_headers)
    assets = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()
    asset = assets[0]
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    await client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "approved"}, headers=reviewer_headers)
    return asset


async def test_download_approved(client, editor_headers, reviewer_headers):
    asset = await _approved_asset(client, editor_headers, reviewer_headers)
    response = await client.get(f"/api/assets/{asset['id']}/download?format=markdown", headers=editor_headers)
    assert response.status_code == 200 and "attachment" in response.headers.get("content-disposition", "")


async def test_download_draft_rejected(client, editor_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    asset = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()[0]
    response = await client.get(f"/api/assets/{asset['id']}/download?format=markdown", headers=editor_headers)
    assert response.status_code == 409
```

- [ ] **Step 2: 运行确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_export.py tests/test_download.py -v
```

Expected: FAIL。

- [ ] **Step 3: 实现**

`app/export/renderers.py`：

```python
from html import escape


def render_markdown(kind: str, content: dict) -> str:
    if kind == "announcement":
        lines = [f"# {content['title']}", "", content["summary"], "", content["body"], "", "## 行动项"]
        lines += [f"- {action}" for action in content["actions"]]
        return "\n".join(lines)
    if kind == "faq":
        lines = ["# FAQ", ""]
        for item in content["items"]:
            lines += [f"## {item['question']}", item["answer"], ""]
        return "\n".join(lines)
    lines = [f"# {content['headline']}", "", content["subhead"], ""]
    lines += [f"- {point}" for point in content["selling_points"]]
    lines += ["", content["cta"]]
    return "\n".join(lines)


def render_html(kind: str, content: dict) -> str:
    if kind == "announcement":
        actions = "".join(f"<li>{escape(a)}</li>" for a in content["actions"])
        return f"<h1>{escape(content['title'])}</h1><p>{escape(content['summary'])}</p><p>{escape(content['body']).replace(chr(10), '<br>')}</p><h2>行动项</h2><ul>{actions}</ul>"
    if kind == "faq":
        items = "".join(f"<dt>{escape(i['question'])}</dt><dd>{escape(i['answer'])}</dd>" for i in content["items"])
        return f"<h1>FAQ</h1><dl>{items}</dl>"
    points = "".join(f"<li>{escape(p)}</li>" for p in content["selling_points"])
    return f"<div style='border:1px solid #ccc;padding:16px'><h1>{escape(content['headline'])}</h1><p>{escape(content['subhead'])}</p><ul>{points}</ul><p><strong>{escape(content['cta'])}</strong></p></div>"
```

在 `app/api/assets.py` 顶部追加 import：`from fastapi import Response` 和 `from app.export.renderers import render_html, render_markdown`。

在 `app/api/assets.py` 末尾追加：

```python
@router.get("/{asset_id}/download")
async def download_asset(asset_id: str, format: str = "markdown", db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    asset = await _load_asset(db, asset_id)
    if asset.status != "approved":
        raise HTTPException(status_code=409, detail="资产尚未通过审核")
    if format == "markdown":
        text = render_markdown(asset.kind, asset.content)
        media = "text/markdown; charset=utf-8"
        filename = f"{asset.kind}.md"
    elif format == "html":
        text = render_html(asset.kind, asset.content)
        media = "text/html; charset=utf-8"
        filename = f"{asset.kind}.html"
    else:
        raise HTTPException(status_code=422, detail="不支持的格式")
    await record_audit(db, user.username, "download_asset", "asset", asset.id, detail={"format": format})
    return Response(content=text, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
```

- [ ] **Step 4: 运行确认通过**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_export.py tests/test_download.py -v
```

Expected: 5 passed。

- [ ] **Step 5: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench/backend
git commit -m 'feat(workbench): Markdown/HTML 导出渲染与下载 API'
```

---

### Task 8: 发布适配器与模拟交付任务

**Files:**
- Create: `content-workbench/backend/app/services/publisher.py`
- Create: `content-workbench/backend/app/api/delivery.py`
- Modify: `content-workbench/backend/app/api/router.py`
- Test: `content-workbench/backend/tests/test_delivery.py`

- [ ] **Step 1: 写失败测试**

`tests/test_delivery.py`：

```python
import uuid
from tests.helpers import setup_project_with_source


async def _approved_asset(client, editor_headers, reviewer_headers) -> dict:
    project_id = await setup_project_with_source(client, editor_headers)
    assets = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()
    asset = assets[0]
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    await client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "approved"}, headers=reviewer_headers)
    return asset


async def test_create_delivery_approved(client, editor_headers, reviewer_headers):
    asset = await _approved_asset(client, editor_headers, reviewer_headers)
    response = await client.post(f"/api/assets/{asset['id']}/deliveries", headers=editor_headers)
    assert response.status_code == 201 and response.json()["status"] == "completed"


async def test_delivery_draft_rejected(client, editor_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    asset = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()[0]
    response = await client.post(f"/api/assets/{asset['id']}/deliveries", headers=editor_headers)
    assert response.status_code == 409


async def test_list_deliveries(client, editor_headers, reviewer_headers):
    asset = await _approved_asset(client, editor_headers, reviewer_headers)
    await client.post(f"/api/assets/{asset['id']}/deliveries", headers=editor_headers)
    response = await client.get("/api/deliveries", headers=editor_headers)
    assert response.status_code == 200 and len(response.json()) == 1
```

- [ ] **Step 2: 运行确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_delivery.py -v
```

Expected: FAIL（404）。

- [ ] **Step 3: 实现**

`app/services/publisher.py`：

```python
from typing import Protocol
import uuid


class PublisherAdapter(Protocol):
    async def publish(self, asset) -> str: ...
    async def status(self, task_id: str) -> str: ...


class MockPublisher:
    async def publish(self, asset) -> str:
        return uuid.uuid4().hex

    async def status(self, task_id: str) -> str:
        return "completed"


ADAPTERS: dict[str, PublisherAdapter] = {"mock": MockPublisher()}
```

`app/api/delivery.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import get_current_user, require_role
from app.database import get_db
from app.models.content import ContentAsset, DeliveryTask, User
from app.services.publisher import ADAPTERS

router = APIRouter(prefix="/assets", tags=["delivery"])


async def _load_asset(db: AsyncSession, asset_id: str) -> ContentAsset:
    asset = await db.get(ContentAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="资产不存在")
    return asset


@router.post("/{asset_id}/deliveries", status_code=201)
async def create_delivery(asset_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("editor")), channel: str = "mock") -> dict:
    asset = await _load_asset(db, asset_id)
    if asset.status != "approved":
        raise HTTPException(status_code=409, detail="资产尚未通过审核")
    adapter = ADAPTERS.get(channel)
    if adapter is None:
        raise HTTPException(status_code=422, detail="未知发布渠道")
    task_id = await adapter.publish(asset)
    db.add(DeliveryTask(id=task_id, asset_id=asset_id, channel=channel, status="completed"))
    await db.commit()
    await record_audit(db, user.username, "create_delivery", "asset", asset_id, detail={"channel": channel, "task_id": task_id})
    return {"asset_id": asset_id, "task_id": task_id, "status": "completed"}


@router.get("/deliveries")
async def list_deliveries(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    tasks = list((await db.scalars(select(DeliveryTask).order_by(DeliveryTask.created_at.desc()))).all())
    return [{"id": t.id, "asset_id": t.asset_id, "channel": t.channel, "status": t.status, "created_at": str(t.created_at)} for t in tasks]
```

`app/api/router.py` 追加：

```python
from app.api import delivery as delivery_api
api_router.include_router(delivery_api.router)
```

- [ ] **Step 4: 运行确认通过**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_delivery.py -v
```

Expected: 3 passed。

- [ ] **Step 5: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench/backend
git commit -m 'feat(workbench): 模拟发布适配器与交付任务'
```

---

### Task 9: 审计查询与后端收尾

**Files:**
- Create: `content-workbench/backend/app/api/audit.py`
- Modify: `content-workbench/backend/app/api/router.py`
- Test: `content-workbench/backend/tests/test_audit.py`

- [ ] **Step 1: 写失败测试**

`tests/test_audit.py`：

```python
from tests.helpers import setup_project_with_source


async def test_audit_reviewer_only(client, editor_headers, reviewer_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)
    assert (await client.get("/api/audit", headers=reviewer_headers)).status_code == 200
    assert (await client.get("/api/audit", headers=editor_headers)).status_code == 403


async def test_audit_records_edit_snapshot(client, editor_headers, reviewer_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    asset = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()[0]
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    await client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "approved"}, headers=reviewer_headers)
    new_content = dict(asset["content"])
    new_content["summary"] = "改"
    await client.put(f"/api/assets/{asset['id']}", json={"content": new_content}, headers=editor_headers)
    rows = (await client.get("/api/audit", headers=reviewer_headers)).json()
    edit_rows = [r for r in rows if r["action"] == "edit_asset"]
    assert edit_rows and edit_rows[0]["detail"]["status_reset"] is True
```

- [ ] **Step 2: 运行确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_audit.py -v
```

Expected: FAIL。

- [ ] **Step 3: 实现**

`app/api/audit.py`：

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.database import get_db
from app.models.content import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit(db: AsyncSession = Depends(get_db), _: _ = Depends(require_role("reviewer"))) -> list[dict]:
    logs = list((await db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100))).all())
    return [{"id": log.id, "actor": log.actor, "action": log.action, "object_type": log.object_type, "object_id": log.object_id, "detail": log.detail, "created_at": str(log.created_at)} for log in logs]
```

`app/api/router.py` 追加：

```python
from app.api import audit as audit_api
api_router.include_router(audit_api.router)
```

- [ ] **Step 4: 运行确认通过**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_audit.py -v
```

Expected: 2 passed。

- [ ] **Step 5: 后端全量测试与 Commit**

```powershell
.\venv\Scripts\python.exe -m pytest tests -v
```

Expected: 全部 backend tests passed。

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench/backend
git commit -m 'feat(workbench): 审计查询与后端全量收尾'
```

---

### Task 10: 前端骨架

**Files:**
- Create: `content-workbench/frontend/package.json`
- Create: `content-workbench/frontend/vite.config.ts`
- Create: `content-workbench/frontend/tsconfig.json`
- Create: `content-workbench/frontend/tsconfig.node.json`
- Create: `content-workbench/frontend/index.html`
- Create: `content-workbench/frontend/env.d.ts`
- Create: `content-workbench/frontend/src/main.ts`
- Create: `content-workbench/frontend/src/App.vue`
- Create: `content-workbench/frontend/src/api/client.ts`
- Create: `content-workbench/frontend/src/stores/auth.ts`
- Create: `content-workbench/frontend/src/router/index.ts`
- Create: `content-workbench/frontend/.gitignore`

- [ ] **Step 1: 创建目录与基础配置**

```powershell
mkdir content-workbench\frontend\src\api, content-workbench\frontend\src\stores, content-workbench\frontend\src\router, content-workbench\frontend\src\views
```

`package.json`：

```json
{
  "name": "content-workbench-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build"
  },
  "dependencies": {
    "@element-plus/icons-vue": "^2.3.2",
    "axios": "^1.7.9",
    "element-plus": "^2.14.7",
    "pinia": "^2.2.6",
    "vue": "^3.5.13",
    "vue-router": "^4.5.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.4",
    "typescript": "^5.6.3",
    "vite": "^5.4.11",
    "vue-tsc": "^2.2.0"
  }
}
```

`vite.config.ts`：

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } }
  }
})
```

`tsconfig.json`：

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

`tsconfig.node.json`：

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

`index.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>内容生产发布工作台</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

`env.d.ts`：

```typescript
/// <reference types="vite/client" />
```

`.gitignore`：

```
node_modules/
dist/
*.local
```

- [ ] **Step 2: API 客户端、Pinia 认证状态、路由**

`src/api/client.ts`：

```typescript
import axios from 'axios'

export const api = axios.create({ baseURL: '/api', headers: { 'Content-Type': 'application/json' } })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
```

`src/stores/auth.ts`：

```typescript
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const username = ref(localStorage.getItem('username') || '')
  const role = ref(localStorage.getItem('role') || '')
  const isEditor = computed(() => role.value === 'editor')
  const isReviewer = computed(() => role.value === 'reviewer')

  async function login(usernameValue: string, password: string) {
    const { data } = await api.post('/auth/login', { username: usernameValue, password })
    token.value = data.token
    username.value = data.username
    role.value = data.role
    localStorage.setItem('token', data.token)
    localStorage.setItem('username', data.username)
    localStorage.setItem('role', data.role)
  }

  function logout() {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
  }

  return { token, username, role, isEditor, isReviewer, login, logout }
})
```

`src/router/index.ts`：

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import ProjectListView from '../views/ProjectListView.vue'
import SourceCenterView from '../views/SourceCenterView.vue'
import WorkspaceView from '../views/WorkspaceView.vue'
import ReviewView from '../views/ReviewView.vue'
import DeliveryView from '../views/DeliveryView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView },
    { path: '/', redirect: '/projects' },
    { path: '/projects', component: ProjectListView, meta: { role: 'editor' } },
    { path: '/projects/:id/sources', component: SourceCenterView, meta: { role: 'editor' } },
    { path: '/projects/:id/workspace', component: WorkspaceView, meta: { role: 'editor' } },
    { path: '/review', component: ReviewView, meta: { role: 'reviewer' } },
    { path: '/delivery', component: DeliveryView },
  ],
})

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  if (!auth.token && to.path !== '/login') return next('/login')
  if (to.meta.role && auth.role !== to.meta.role) return next('/login')
  next()
})

export default router
```

- [ ] **Step 3: 入口与布局**

`src/main.ts`：

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'

createApp(App).use(createPinia()).use(ElementPlus).use(router).mount('#app')
```

`src/App.vue`：

```vue
<script setup lang="ts">
import { useAuthStore } from './stores/auth'
import { useRoute, useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

function logout() {
  auth.logout()
  router.push('/login')
}

const editorMenus = [
  { path: '/projects', label: '项目列表' },
  { path: '/delivery', label: '发布任务' },
]
const reviewerMenus = [
  { path: '/review', label: '审核工作台' },
  { path: '/delivery', label: '发布与审计' },
]
const menus = auth.isEditor ? editorMenus : reviewerMenus
</script>

<template>
  <el-container v-if="auth.token" style="height: 100vh">
    <el-header style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e4e7ed">
      <strong>内容生产发布工作台</strong>
      <el-space>
        <span>{{ auth.username }}（{{ auth.role }}）</span>
        <el-button size="small" @click="logout">退出</el-button>
      </el-space>
    </el-header>
    <el-container>
      <el-aside width="180px" style="border-right:1px solid #e4e7ed">
        <el-menu :default-active="route.path" router>
          <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">{{ m.label }}</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
  <router-view v-else />
</template>
```

- [ ] **Step 4: 安装与构建检查**

```powershell
cd content-workbench\frontend
npm install
npm run build
```

Expected: build 成功。

- [ ] **Step 5: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench/frontend
git commit -m 'feat(workbench): 前端骨架、路由与 Pinia 认证'
```

---

### Task 11: 登录页

**Files:**
- Create: `content-workbench/frontend/src/views/LoginView.vue`

- [ ] **Step 1: 实现登录页**

`src/views/LoginView.vue`：

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const form = ref({ username: '', password: '' })
const loading = ref(false)

async function submit() {
  loading.value = true
  try {
    await auth.login(form.value.username, form.value.password)
    router.push(auth.isEditor ? '/projects' : '/review')
  } catch (error) {
    ElMessage.error('登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="height:100vh;display:flex;align-items:center;justify-content:center">
    <el-card title="内容生产发布工作台" style="width:360px">
      <h2 style="text-align:center">登录</h2>
      <el-form label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" @keydown.enter="submit" />
        </el-form-item>
        <el-button type="primary" style="width:100%" :loading="loading" @click="submit">登录</el-button>
      </el-form>
      <p style="color:#999;font-size:12px;margin-top:12px">测试账号：editor/editor123（编辑）、reviewer/review123（审核）</p>
    </el-card>
  </div>
</template>
```

- [ ] **Step 2: 构建检查**

```powershell
cd content-workbench\frontend
npm run build
```

Expected: build 成功。

- [ ] **Step 3: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench/frontend
git commit -m 'feat(workbench): 登录页'
```

---

### Task 12: 项目列表与资料中心

**Files:**
- Create: `content-workbench/frontend/src/views/ProjectListView.vue`
- Create: `content-workbench/frontend/src/views/SourceCenterView.vue`

- [ ] **Step 1: 项目列表页**

`src/views/ProjectListView.vue`：

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'

const router = useRouter()
const projects = ref<any[]>([])
const dialog = ref(false)
const form = ref({ name: '', theme: '', audience: '', tone: '' })
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    projects.value = (await api.get('/projects')).data
  } finally { loading.value = false }
}

async function create() {
  await api.post('/projects', form.value)
  ElMessage.success('创建成功')
  dialog.value = false
  form.value = { name: '', theme: '', audience: '', tone: '' }
  await load()
}

async function remove(id: string) {
  await api.delete(`/projects/${id}`)
  ElMessage.success('删除成功')
  await load()
}

onMounted(load)
</script>

<template>
  <section>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>项目列表</h2>
      <el-button type="primary" @click="dialog = true">新建项目</el-button>
    </div>
    <el-table v-loading="loading" :data="projects" border>
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="theme" label="主题" />
      <el-table-column prop="audience" label="受众" />
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button size="small" @click="router.push(`/projects/${row.id}/sources`)">资料</el-button>
          <el-button size="small" type="primary" @click="router.push(`/projects/${row.id}/workspace`)">工作台</el-button>
          <el-button size="small" type="danger" @click="remove(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dialog" title="新建项目" width="500px">
      <el-form label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="主题"><el-input v-model="form.theme" type="textarea" /></el-form-item>
        <el-form-item label="受众"><el-input v-model="form.audience" /></el-form-item>
        <el-form-item label="语气"><el-input v-model="form.tone" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </section>
</template>
```

- [ ] **Step 2: 资料中心页**

`src/views/SourceCenterView.vue`：

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'

const route = useRoute()
const router = useRouter()
const projectId = route.params.id as string
const sources = ref<any[]>([])
const content = ref('')
const name = ref('')
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    sources.value = (await api.get(`/projects/${projectId}/sources`)).data
  } finally { loading.value = false }
}

async function add() {
  if (!name.value || !content.value) return
  await api.post(`/projects/${projectId}/sources`, { name: name.value, content: content.value })
  ElMessage.success('已添加')
  name.value = ''
  content.value = ''
  await load()
}

async function remove(sourceId: string) {
  await api.delete(`/projects/${projectId}/sources/${sourceId}`)
  await load()
}

onMounted(load)
</script>

<template>
  <section>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>资料中心</h2>
      <el-button @click="router.push('/projects')">返回列表</el-button>
    </div>
    <el-card title="粘贴资料" style="margin-bottom:16px">
      <el-input v-model="name" placeholder="资料名称" style="margin-bottom:8px" />
      <el-input v-model="content" type="textarea" :rows="6" placeholder="粘贴产品文档、操作手册等文本" />
      <el-button type="primary" style="margin-top:8px" @click="add">添加资料</el-button>
    </el-card>
    <el-table v-loading="loading" :data="sources" border>
      <el-table-column prop="name" label="资料名" />
      <el-table-column prop="created_at" label="创建时间" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button size="small" type="danger" @click="remove(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>
```

- [ ] **Step 3: 构建检查**

```powershell
cd content-workbench\frontend
npm run build
```

Expected: build 成功。

- [ ] **Step 4: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench/frontend
git commit -m 'feat(workbench): 项目列表与资料中心页面'
```

---

### Task 13: 创作工作台（一键生成＋类型化编辑＋提交审核）

**Files:**
- Create: `content-workbench/frontend/src/views/WorkspaceView.vue`

- [ ] **Step 1: 实现创作工作台**

`src/views/WorkspaceView.vue`：

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'

const route = useRoute()
const router = useRouter()
const projectId = route.params.id as string
const assets = ref<any[]>([])
const activeKind = ref('announcement')
const loading = ref(false)
const generating = ref(false)
const kinds = [
  { key: 'announcement', label: '公告' },
  { key: 'faq', label: 'FAQ' },
  { key: 'poster', label: '海报文案' },
]

async function load() {
  loading.value = true
  try {
    assets.value = (await api.get(`/projects/${projectId}/assets`)).data
  } finally { loading.value = false }
}

async function generate() {
  generating.value = true
  try {
    await api.post(`/projects/${projectId}/generate`)
    ElMessage.success('生成成功')
    await load()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '生成失败')
  } finally { generating.value = false }
}

function currentAsset(kind: string) {
  return assets.value.find((a) => a.kind === kind)
}

async function submit(kind: string) {
  const asset = currentAsset(kind)
  if (!asset) return
  await api.post(`/assets/${asset.id}/submit`)
  ElMessage.success('已提交审核')
  await load()
}

async function updateContent(kind: string, content: any) {
  const asset = currentAsset(kind)
  if (!asset) return
  await api.put(`/assets/${asset.id}`, { content })
  ElMessage.success('已保存')
  await load()
}

onMounted(load)
</script>

<template>
  <section>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>创作工作台</h2>
      <el-space>
        <el-button @click="router.push(`/projects/${projectId}/sources`)">资料中心</el-button>
        <el-button type="primary" :loading="generating" @click="generate">一键生成</el-button>
      </el-space>
    </div>
    <el-tabs v-model="activeKind" v-loading="loading">
      <el-tab-pane v-for="k in kinds" :key="k.key" :label="k.label" :name="k.key">
        <AssetEditor v-if="currentAsset(k.key)" :asset="currentAsset(k.key)" @save="(c) => updateContent(k.key, c)" @submit="submit(k.key)" />
        <el-empty v-else description="点击右上角一键生成" />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>
```

- [ ] **Step 2: 创建类型化编辑器组件**

`src/views/WorkspaceView.vue` 的 `AssetEditor` 组件需要内联定义：由于单文件内组件在 Vue SFC 中需单独注册，这里拆分为独立文件更简洁。

Create `content-workbench/frontend/src/views/AssetEditor.vue`：

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ asset: any }>()
const emit = defineEmits<{ save: [content: any]; submit: [] }>()
const local = ref<any>({})

watch(() => props.asset, (a) => { local.value = JSON.parse(JSON.stringify(a.content || {})) }, { immediate: true })

function addFaq() {
  if (!local.value.items) local.value.items = []
  local.value.items.push({ question: '', answer: '', source_ids: [] })
}

function removeFaq(index: number) {
  local.value.items.splice(index, 1)
}
</script>

<template>
  <el-card>
    <template #header>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span>状态：{{ asset.status }}</span>
        <el-space>
          <el-button size="small" @click="emit('save', local)">保存</el-button>
          <el-button v-if="asset.status === 'draft' || asset.status === 'rejected'" size="small" type="primary" @click="emit('submit')">提交审核</el-button>
        </el-space>
      </div>
    </template>

    <div v-if="asset.kind === 'announcement'">
      <el-form label-width="80px">
        <el-form-item label="标题"><el-input v-model="local.title" /></el-form-item>
        <el-form-item label="摘要"><el-input v-model="local.summary" type="textarea" /></el-form-item>
        <el-form-item label="正文"><el-input v-model="local.body" type="textarea" :rows="6" /></el-form-item>
        <el-form-item label="行动项">
          <div v-for="(_, i) in local.actions" :key="i" style="display:flex;gap:8px;margin-bottom:8px;width:100%">
            <el-input v-model="local.actions[i]" />
            <el-button size="small" @click="local.actions.splice(i, 1)">删除</el-button>
          </div>
          <el-button size="small" @click="local.actions.push('')">添加行动项</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div v-else-if="asset.kind === 'faq'">
      <el-button size="small" @click="addFaq">添加问答</el-button>
      <div v-for="(item, i) in local.items" :key="i" style="margin-top:12px;border:1px solid #e4e7ed;padding:12px;border-radius:4px">
        <el-form label-width="60px">
          <el-form-item label="问题"><el-input v-model="item.question" /></el-form-item>
          <el-form-item label="答案"><el-input v-model="item.answer" type="textarea" :rows="3" /></el-form-item>
        </el-form>
        <el-button size="small" type="danger" @click="removeFaq(i)">删除</el-button>
      </div>
    </div>

    <div v-else-if="asset.kind === 'poster'">
      <el-form label-width="80px">
        <el-form-item label="主标题"><el-input v-model="local.headline" /></el-form-item>
        <el-form-item label="副标题"><el-input v-model="local.subhead" /></el-form-item>
        <el-form-item label="卖点">
          <div v-for="(_, i) in local.selling_points" :key="i" style="display:flex;gap:8px;margin-bottom:8px;width:100%">
            <el-input v-model="local.selling_points[i]" />
            <el-button size="small" @click="local.selling_points.splice(i, 1)">删除</el-button>
          </div>
          <el-button size="small" @click="local.selling_points.push('')">添加卖点</el-button>
        </el-form-item>
        <el-form-item label="行动号召"><el-input v-model="local.cta" /></el-form-item>
      </el-form>
      <el-card style="margin-top:16px;background:#f5f7fa">
        <h3 style="margin:0">{{ local.headline }}</h3>
        <p style="color:#666">{{ local.subhead }}</p>
        <ul><li v-for="(p, i) in local.selling_points" :key="i">{{ p }}</li></ul>
        <p><strong>{{ local.cta }}</strong></p>
      </el-card>
    </div>
  </el-card>
</template>
```

在 `WorkspaceView.vue` 中导入 `AssetEditor`：

```vue
<script setup lang="ts">
import AssetEditor from './AssetEditor.vue'
// ...
</script>
```

- [ ] **Step 3: 构建检查**

```powershell
cd content-workbench\frontend
npm run build
```

Expected: build 成功。

- [ ] **Step 4: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench/frontend
git commit -m 'feat(workbench): 创作工作台与类型化编辑器'
```

---

### Task 14: 审核工作台

**Files:**
- Create: `content-workbench/frontend/src/views/ReviewView.vue`

- [ ] **Step 1: 实现审核工作台**

`src/views/ReviewView.vue`：

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'

const pending = ref<any[]>([])
const drawer = ref(false)
const selected = ref<any>(null)
const comment = ref('')
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/projects/dummy/assets') // 占位，见下方说明
    pending.value = data.filter((a: any) => a.status === 'pending_review')
  } finally { loading.value = false }
}

async function load() {
  loading.value = true
  try {
    pending.value = (await api.get('/assets/pending')).data
  } finally { loading.value = false }
}

async function review(assetId: string, decision: string) {
  await api.post(`/assets/${assetId}/reviews`, { decision, comment: comment.value })
  ElMessage.success(decision === 'approved' ? '已通过' : '已驳回')
  comment.value = ''
  await load()
}

function showCitations(asset: any) {
  selected.value = asset
  drawer.value = true
}

onMounted(load)
</script>

<template>
  <section>
    <h2>审核工作台</h2>
    <el-table v-loading="loading" :data="pending" border>
      <el-table-column prop="project_name" label="项目" />
      <el-table-column prop="kind" label="类型" />
      <el-table-column label="操作" width="260">
        <template #default="{ row }">
          <el-button size="small" @click="showCitations(row)">查看引用</el-button>
          <el-button size="small" type="success" @click="review(row.id, 'approved')">通过</el-button>
          <el-button size="small" type="danger" @click="review(row.id, 'rejected')">驳回</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="drawer" title="证据引用" width="600px">
      <div v-for="(c, i) in selected?.citations" :key="i" style="margin-bottom:12px;border-left:3px solid #409eff;padding-left:8px">
        <p style="margin:0;color:#666;font-size:12px">来源：{{ c.source_id }}</p>
        <p>{{ c.text }}</p>
      </div>
      <el-input v-model="comment" placeholder="审核意见（驳回时必填）" type="textarea" :rows="3" />
    </el-dialog>
  </section>
</template>
```

- [ ] **Step 2: 后端新增跨项目待审核列表端点**

在 `app/api/assets.py` 顶部追加 `ContentProject` import：

```python
from app.models.content import ContentAsset, ContentProject, ReviewRecord, User
```

在 `app/api/assets.py` 中，**在第一个动态路由 `@router.put("/{asset_id}")` 之前**追加：

```python
@router.get("/pending")
async def list_pending_assets(db: AsyncSession = Depends(get_db), _: User = Depends(require_role("reviewer"))) -> list[dict]:
    rows = await db.execute(
        select(ContentAsset, ContentProject.name)
        .join(ContentProject, ContentAsset.project_id == ContentProject.id)
        .where(ContentAsset.status == "pending_review")
        .order_by(ContentAsset.created_at.desc())
    )
    return [{"id": a.id, "kind": a.kind, "project_name": name, "content": a.content, "citations": a.citations} for a, name in rows]
```

- [ ] **Step 3: 写失败测试**

`tests/test_review_api.py`：

```python
from tests.helpers import setup_project_with_source


async def test_pending_list_reviewer_only(client, editor_headers, reviewer_headers):
    assert (await client.get("/assets/pending", headers=editor_headers)).status_code == 403
    response = await client.get("/assets/pending", headers=reviewer_headers)
    assert response.status_code == 200 and response.json() == []


async def test_pending_list_shows_submitted(client, editor_headers, reviewer_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    assets = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()
    await client.post(f"/assets/{assets[0]['id']}/submit", headers=editor_headers)
    response = await client.get("/assets/pending", headers=reviewer_headers)
    assert len(response.json()) == 1
```

- [ ] **Step 4: 运行确认通过**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_review_api.py -v
```

Expected: 2 passed。

- [ ] **Step 5: 构建检查**

```powershell
cd content-workbench\frontend
npm run build
```

Expected: build 成功。

- [ ] **Step 6: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench
git commit -m 'feat(workbench): 审核工作台与待审资产列表端点'
```

---

### Task 15: 发布与审计页面

**Files:**
- Create: `content-workbench/frontend/src/views/DeliveryView.vue`

- [ ] **Step 1: 后端新增已审核资产列表端点**

在 `app/api/assets.py` 中，**在第一个动态路由 `@router.put("/{asset_id}")` 之前**追加：

```python
@router.get("/approved")
async def list_approved_assets(db: AsyncSession = Depends(get_db), _: User = Depends(require_role("editor"))) -> list[dict]:
    rows = await db.execute(
        select(ContentAsset, ContentProject.name)
        .join(ContentProject, ContentAsset.project_id == ContentProject.id)
        .where(ContentAsset.status == "approved")
        .order_by(ContentAsset.created_at.desc())
    )
    return [{"id": a.id, "kind": a.kind, "project_name": name, "content": a.content, "citations": a.citations} for a, name in rows]
```

- [ ] **Step 2: 写 /assets/approved 测试**

`tests/test_approved_api.py`：

```python
from tests.helpers import setup_project_with_source


async def test_approved_list_editor_only(client, editor_headers, reviewer_headers):
    assert (await client.get("/assets/approved", headers=reviewer_headers)).status_code == 403
    response = await client.get("/assets/approved", headers=editor_headers)
    assert response.status_code == 200 and response.json() == []


async def test_approved_list_shows_approved(client, editor_headers, reviewer_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    assets = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()
    await client.post(f"/assets/{assets[0]['id']}/submit", headers=editor_headers)
    await client.post(f"/assets/{assets[0]['id']}/reviews", json={"decision": "approved"}, headers=reviewer_headers)
    response = await client.get("/assets/approved", headers=editor_headers)
    assert len(response.json()) == 1
```

运行：

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_approved_api.py -v
```

Expected: 2 passed。

- [ ] **Step 3: 实现发布与审计页**

`src/views/DeliveryView.vue`：

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const activeTab = ref(auth.isEditor ? 'approved' : 'deliveries')
const approved = ref<any[]>([])
const deliveries = ref<any[]>([])
const audit = ref<any[]>([])
const loading = ref(false)

async function loadApproved() {
  if (!auth.isEditor) return
  approved.value = (await api.get('/assets/approved')).data
}

async function loadDeliveries() {
  deliveries.value = (await api.get('/deliveries')).data
}

async function loadAudit() {
  if (!auth.isReviewer) return
  audit.value = (await api.get('/audit')).data
}

async function refresh() {
  loading.value = true
  try {
    await Promise.all([loadApproved(), loadDeliveries(), loadAudit()])
  } finally { loading.value = false }
}

async function download(asset: any, format: string) {
  const response = await api.get(`/assets/${asset.id}/download?format=${format}`, { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const a = document.createElement('a')
  a.href = url
  a.download = `${asset.kind}.${format === 'markdown' ? 'md' : 'html'}`
  a.click()
  window.URL.revokeObjectURL(url)
}

async function publish(asset: any) {
  await api.post(`/assets/${asset.id}/deliveries`)
  ElMessage.success('模拟发布完成')
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <section v-loading="loading">
    <h2>{{ auth.isEditor ? '发布任务' : '发布与审计' }}</h2>
    <el-tabs v-model="activeTab">
      <el-tab-pane v-if="auth.isEditor" label="已审核资产" name="approved">
        <el-table :data="approved" border>
          <el-table-column prop="project_name" label="项目" />
          <el-table-column prop="kind" label="类型" />
          <el-table-column label="下载" width="180">
            <template #default="{ row }">
              <el-button size="small" @click="download(row, 'markdown')">Markdown</el-button>
              <el-button size="small" @click="download(row, 'html')">HTML</el-button>
            </template>
          </el-table-column>
          <el-table-column label="发布" width="120">
            <template #default="{ row }">
              <el-button size="small" type="success" @click="publish(row)">模拟发布</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="发布任务" name="deliveries">
        <el-table :data="deliveries" border>
          <el-table-column prop="id" label="任务 ID" />
          <el-table-column prop="asset_id" label="资产 ID" />
          <el-table-column prop="channel" label="渠道" />
          <el-table-column prop="status" label="状态" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane v-if="auth.isReviewer" label="审计日志" name="audit">
        <el-table :data="audit" border>
          <el-table-column prop="created_at" label="时间" />
          <el-table-column prop="actor" label="操作者" />
          <el-table-column prop="action" label="动作" />
          <el-table-column prop="object_type" label="对象类型" />
          <el-table-column prop="object_id" label="对象 ID" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>
```

- [ ] **Step 4: 构建检查**

```powershell
cd content-workbench\frontend
npm run build
```

Expected: build 成功。

- [ ] **Step 5: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench
git commit -m 'feat(workbench): 发布与审计页面及已审核资产端点'
```

---

### Task 16: README、启动脚本与最终验证

**Files:**
- Create: `content-workbench/README.md`
- Create: `content-workbench/backend/.env.example`
- Modify: `content-workbench/frontend/package.json`（可选：确认 build 脚本）

- [ ] **Step 1: README 与示例环境变量**

`README.md`：

```markdown
# 内容生产发布工作台

输入活动主题、产品文档、操作手册等，一键产出公告、FAQ、海报文案，经人工审核后下载或创建模拟发布任务。

## 启动

```powershell
cd content-workbench/backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
# 配置环境变量：拷贝 .env.example 为 .env，填入 DEEPSEEK_API_KEY
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

cd ../frontend
npm install
npm run dev
```

前端访问 http://localhost:5173/，后端 API 文档 http://127.0.0.1:8000/docs。

测试账号：
- editor / editor123（编辑者：创建项目、贴资料、生成、编辑、下载、发布）
- reviewer / review123（审核者：查看引用、通过/驳回、查看审计日志）

## 验证

```powershell
cd content-workbench/backend
.\venv\Scripts\python.exe -m pytest tests -v

cd ../frontend
npm run build
```
```

`backend/.env.example`：

```
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

- [ ] **Step 2: 后端全量测试**

```powershell
cd content-workbench\backend
.\venv\Scripts\python.exe -m pytest tests -v
```

Expected: 全部 passed。

- [ ] **Step 3: 前端构建**

```powershell
cd content-workbench\frontend
npm run build
```

Expected: build 成功。

- [ ] **Step 4: 冒烟清单（手动，在前后端都启动后执行）**

1. 用 editor 登录，新建项目，粘贴资料，点击一键生成 → 公告/FAQ/海报文案均出现且带引用。
2. 编辑公告摘要，保存后状态保持 draft；点击提交审核 → 状态变为 pending_review。
3. 用 reviewer 登录，审核工作台看到该条，点击查看引用能看到原文片段；点击通过 → 状态 approved。
4. 切回 editor，进入发布与审计页，下载 Markdown 文件，点击模拟发布 → 任务列表出现 completed 任务。
5. 切回 reviewer，查看审计日志，能看到 generate_assets、edit_asset、submit_asset、review_asset、download_asset、create_delivery 等记录。
6. 测试拒答：editor 新建一个与资料无关的项目主题，点击生成 → 提示"需补充资料"，无脏数据。
7. 测试合规：approved 后再次编辑该资产 → 状态自动回落 draft，发布按钮与下载按钮不可用。

- [ ] **Step 5: Commit**

```powershell
cd D:\StudyProjects\ai-practice
git add content-workbench
git commit -m 'docs(workbench): README、环境示例与冒烟清单'
```

---

## 计划自审

- **规格覆盖检查**：所有 P0 需求均有对应任务：项目/资料管理（Task 2/12）、一键生成（Task 3-5/13）、编辑（Task 6/13）、审核门禁+角色分离（Task 2/6/14）、生成依据可追溯（Task 3/5/14）、审计日志（Task 1/6/9/15）、Markdown/HTML 下载（Task 7/15）、模拟发布适配器（Task 8/15）。
- **占位符扫描**：无 TBD/TODO/"后续再实现"。所有步骤包含完整代码、命令与预期输出。
- **类型一致性**：资产状态字段统一为 `draft/pending_review/approved/rejected`；角色统一 `editor/reviewer`；生成器协议与依赖名称 `get_generator`、`ContentGenerator`、`FakeGenerator` 前后一致；citations 结构统一为 `{source_id, text}`。
- **隐含边界明确**：
  - `pending_review` 状态锁定编辑；编辑 approved 回落 draft。
  - 模型输出约定 `{"assets": [...]}`。
  - 海报导出仅提供文案（Markdown/HTML），视觉模板在前端预览。
  - 静态路由 `/assets/pending`、`/assets/approved` 均注册在动态 `/{asset_id}` 之前，避免路径被错误捕获。
  - `/delivery` 页面为登录后共享，按角色显隐：editor 看到"已审核资产"（下载/发布）和"发布任务"；reviewer 看到"发布任务"和"审计日志"。
  - 下载使用 axios blob + objectURL，确保 Bearer Token 被携带。
  - 前端验证通过 `npm run build` + 手动冒烟清单，不引入组件测试框架。

## 执行交接

计划已完成并保存至 `docs/superpowers/plans/2026-10-13-content-generation-workbench.md`。

两种执行方式：

1. **Subagent-Driven（推荐）**：每任务派一个干净子代理执行，我在任务间审阅结果。适合想要严格 TDD 与频繁检查点。
2. **Inline Execution**：在当前会话内按顺序批量执行，我在关键任务后暂停确认。适合想要更快推进。

请选择执行方式。

