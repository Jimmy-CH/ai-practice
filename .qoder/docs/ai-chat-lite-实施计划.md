# ai-chat-lite 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `ai-chat-lite` 子项目，交付 FastAPI + httpx 直连 SSE 的多轮聊天后端与纯原生 HTML/JS 前端，支持 JWT 认证、多会话、断点续传、停止生成。

**Architecture:** 发起消息与订阅流解耦：POST 落库并启动后台任务消费上游 httpx 流，GET SSE 端点按 `seq` 从进程内 buffer 订阅/续传，POST stop 取消任务。前端用 fetch + ReadableStream 解析标准 SSE 事件。

**Tech Stack:** Python 3.11 · FastAPI · Uvicorn · httpx · SQLAlchemy 2.0 async · SQLite(aiosqlite) · python-jose · passlib+bcrypt 4.0.1 · pytest/pytest-asyncio · 原生 HTML/CSS/JS（零构建链）

**设计依据:** `.qoder/docs/ai-chat-lite-设计说明.md`（本计划实现其第 3-13 节）

**代码根目录:** `D:\StudyProjects\ai-practice\ai-chat-lite`

---

## 文件结构总览

```
ai-chat-lite/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py            # 环境变量（显式 load .env）
│   │   ├── database.py          # async engine / session / Base / init_db
│   │   ├── core/__init__.py
│   │   ├── core/security.py     # bcrypt + JWT + get_current_user
│   │   ├── core/sse.py          # SSE 事件编码
│   │   ├── models/{__init__,user,conversation,message}.py
│   │   ├── schemas/{__init__,user,conversation,message}.py
│   │   ├── services/{__init__,user_service,conversation_service,chat_service,llm_client,stream_manager}.py
│   │   ├── api/{__init__,router,auth,users,conversations,messages}.py
│   │   └── main.py
│   ├── tests/{conftest,test_health,test_auth,test_conversations,test_llm_client,test_stream_manager,test_stream}.py
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── .env.example
│   └── README.md
├── frontend/{index.html,styles.css,app.js,markdown.js}
└── README.md
```

---

### Task 1: 项目骨架、配置、数据库与健康检查

**Files:**
- Create: `ai-chat-lite/backend/requirements.txt`
- Create: `ai-chat-lite/backend/pytest.ini`
- Create: `ai-chat-lite/backend/.env.example`
- Create: `ai-chat-lite/backend/app/__init__.py`（空）
- Create: `ai-chat-lite/backend/app/config.py`
- Create: `ai-chat-lite/backend/app/database.py`
- Create: `ai-chat-lite/backend/app/main.py`
- Create: `ai-chat-lite/backend/tests/conftest.py`
- Test: `ai-chat-lite/backend/tests/test_health.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_health.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

```python
# tests/conftest.py
import os
import tempfile
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="ai-chat-lite-test-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(_TMP_DIR) / 'test.db'}"
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import Base, engine
from app.main import app
from app.services import stream_manager as stream_manager_module


@pytest.fixture(autouse=True)
async def clean_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    stream_manager_module.manager.reset()
    yield
    stream_manager_module.manager.reset()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd ai-chat-lite/backend && venv\Scripts\python.exe -m pytest tests/test_health.py -q`
Expected: FAIL（`ModuleNotFoundError: app` 或 404）

- [ ] **Step 3: 写最小实现**

```python
# app/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


class Settings:
    PROJECT_NAME: str = "AI Chat Lite"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./lite.db")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    MAX_CONTEXT_MESSAGES: int = int(os.getenv("MAX_CONTEXT_MESSAGES", "20"))
    STREAM_TIMEOUT_SECONDS: int = int(os.getenv("STREAM_TIMEOUT_SECONDS", "120"))
    HEARTBEAT_SECONDS: int = int(os.getenv("HEARTBEAT_SECONDS", "15"))
    FLUSH_INTERVAL_SECONDS: float = float(os.getenv("FLUSH_INTERVAL_SECONDS", "0.5"))
    SYSTEM_PROMPT: str = os.getenv("SYSTEM_PROMPT", "你是一个乐于助人的中文助手。")
    FRONTEND_DIR: Path = BASE_DIR.parent / "frontend"


settings = Settings()
```

```python
# app/database.py
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_fk(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async def init_db() -> None:
    from app.models import conversation, message, user  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

```python
# app/main.py
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
api_router = APIRouter(prefix="/api")


@api_router.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(api_router)
```

```ini
# requirements.txt
fastapi==0.141.1
uvicorn[standard]==0.52.4
httpx==0.28.1
sqlalchemy[asyncio]==2.0.52
aiosqlite==0.22.1
python-jose[cryptography]==3.5.0
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
python-dotenv==1.2.3
pytest==9.1.1
pytest-asyncio==1.3.0
```

```ini
# pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

```ini
# .env.example
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
SECRET_KEY=change-me
DATABASE_URL=sqlite+aiosqlite:///./lite.db
MAX_CONTEXT_MESSAGES=20
STREAM_TIMEOUT_SECONDS=120
HEARTBEAT_SECONDS=15
FLUSH_INTERVAL_SECONDS=0.5
SYSTEM_PROMPT=你是一个乐于助人的中文助手。
```

- [ ] **Step 4: 建 venv 装依赖并跑测试**

Run: `cd ai-chat-lite/backend && python -m venv venv && venv\Scripts\pip.exe install -r requirements.txt && venv\Scripts\python.exe -m pytest tests/test_health.py -q`
Expected: `1 passed`

- [ ] **Step 5: 提交**

```bash
git add ai-chat-lite/backend && git commit -m "feat(ai-chat-lite): 项目骨架、配置与数据库初始化"
```

---

### Task 2: 用户认证（模型 / bcrypt / JWT / 注册登录 me）

**Files:**
- Create: `app/models/user.py`
- Create: `app/core/security.py`
- Create: `app/schemas/user.py`
- Create: `app/services/user_service.py`
- Create: `app/api/auth.py`
- Create: `app/api/users.py`
- Create: `app/api/router.py`
- Modify: `app/main.py`（改为 include api_router）
- Test: `tests/test_auth.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_auth.py
import pytest
from httpx import AsyncClient

REGISTER = {"username": "alice", "password": "secret123"}


async def _register_and_login(client: AsyncClient, username="alice", password="secret123"):
    await client.post("/api/auth/register", json={"username": username, "password": password})
    resp = await client.post("/api/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]


async def test_register_and_login(client: AsyncClient):
    resp = await client.post("/api/auth/register", json=REGISTER)
    assert resp.status_code == 201
    assert resp.json()["username"] == "alice"

    resp = await client.post("/api/auth/login", json=REGISTER)
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert resp.json()["access_token"]


async def test_duplicate_username(client: AsyncClient):
    await client.post("/api/auth/register", json=REGISTER)
    resp = await client.post("/api/auth/register", json=REGISTER)
    assert resp.status_code == 400


async def test_wrong_password(client: AsyncClient):
    await client.post("/api/auth/register", json=REGISTER)
    resp = await client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


async def test_me_requires_token(client: AsyncClient):
    assert (await client.get("/api/users/me")).status_code == 401


async def test_me_ok(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"


async def test_long_password_truncated_not_crash(client: AsyncClient):
    pwd = "a" * 100
    assert (await client.post("/api/auth/register", json={"username": "bob", "password": pwd})).status_code == 201
    assert (await client.post("/api/auth/login", json={"username": "bob", "password": pwd})).status_code == 200
```

- [ ] **Step 2: 运行确认失败**

Run: `venv\Scripts\python.exe -m pytest tests/test_auth.py -q`
Expected: FAIL（404 / 无 users 表 / 无 security 模块）

- [ ] **Step 3: 写实现**

```python
# app/models/user.py
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)
```

```python
# app/core/security.py
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db  # 需在 database.py 增加 get_db 依赖
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password.encode("utf-8")[:72].decode("utf-8", "ignore"))


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password.encode("utf-8")[:72].decode("utf-8", "ignore"), hashed)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未提供认证凭据", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="认证凭据无效或已过期", headers={"WWW-Authenticate": "Bearer"})
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
```

```python
# app/database.py 追加
async def get_db():
    async with async_session_factory() as session:
        yield session
```

```python
# app/schemas/user.py
from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=6, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

```python
# app/services/user_service.py
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User


async def register(db: AsyncSession, username: str, password: str) -> User:
    exists = await db.scalar(select(User).where(User.username == username))
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login(db: AsyncSession, username: str, password: str) -> str:
    user = await db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return create_access_token(user.id)
```

```python
# app/api/auth.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await user_service.register(db, payload.username, payload.password)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    token = await user_service.login(db, payload.username, payload.password)
    return TokenResponse(access_token=token)
```

```python
# app/api/users.py
from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
```

```python
# app/api/router.py
from fastapi import APIRouter

from app.api import auth, users

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)


@api_router.get("/health")
async def health():
    return {"status": "ok"}
```

`app/main.py` 改为 `from app.api.router import api_router` 并 `app.include_router(api_router)`，删除 main 内的 health 定义。

- [ ] **Step 4: 跑测试**

Run: `venv\Scripts\python.exe -m pytest tests/test_auth.py tests/test_health.py -q`
Expected: `7 passed`

- [ ] **Step 5: 提交**

```bash
git add ai-chat-lite/backend && git commit -m "feat(ai-chat-lite): 用户注册登录与 JWT 鉴权"
```

---

### Task 3: 会话与消息模型、会话 CRUD

**Files:**
- Create: `app/models/conversation.py`, `app/models/message.py`
- Create: `app/schemas/conversation.py`, `app/schemas/message.py`
- Create: `app/services/conversation_service.py`
- Create: `app/api/conversations.py`
- Modify: `app/api/router.py`
- Test: `tests/test_conversations.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_conversations.py
from tests.test_auth import _register_and_login


async def _auth_headers(client, username="alice"):
    token = await _register_and_login(client, username)
    return {"Authorization": f"Bearer {token}"}


async def test_create_and_list_conversations(client):
    headers = await _auth_headers(client)
    resp = await client.post("/api/conversations", headers=headers)
    assert resp.status_code == 201
    cid = resp.json()["id"]
    assert resp.json()["title"] == "新对话"

    resp = await client.get("/api/conversations", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [c["id"] for c in items] == [cid]
    assert items[0]["running"] is False


async def test_conversation_isolation_404(client):
    alice = await _auth_headers(client, "alice")
    bob = await _auth_headers(client, "bob")
    cid = (await client.post("/api/conversations", headers=alice)).json()["id"]
    assert (await client.get(f"/api/conversations/{cid}/messages", headers=bob)).status_code == 404
    assert (await client.delete(f"/api/conversations/{cid}", headers=bob)).status_code == 404


async def test_delete_cascades_messages(client):
    from sqlalchemy import select
    from app.database import async_session_factory
    from app.models.message import Message

    headers = await _auth_headers(client)
    cid = (await client.post("/api/conversations", headers=headers)).json()["id"]
    async with async_session_factory() as db:
        db.add(Message(conversation_id=cid, role="user", content="hi", status="done"))
        await db.commit()
    assert (await client.delete(f"/api/conversations/{cid}", headers=headers)).status_code == 204
    async with async_session_factory() as db:
        assert (await db.scalar(select(Message).where(Message.conversation_id == cid))) is None
```

- [ ] **Step 2: 运行确认失败**

Run: `venv\Scripts\python.exe -m pytest tests/test_conversations.py -q`
Expected: FAIL（404 / 无模型）

- [ ] **Step 3: 写实现**

```python
# app/models/conversation.py
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(60), default="新对话", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    messages = relationship("Message", cascade="all, delete-orphan", passive_deletes=True)
```

```python
# app/models/message.py
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="done", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
```

```python
# app/schemas/conversation.py
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
```

```python
# app/schemas/message.py
from datetime import datetime

from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    status: str
    error: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageList(BaseModel):
    items: list[MessageOut]


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class SendMessageResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
```

```python
# app/services/conversation_service.py
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User


async def create(db: AsyncSession, user: User) -> Conversation:
    conv = Conversation(user_id=user.id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def list_by_user(db: AsyncSession, user: User) -> list[Conversation]:
    result = await db.scalars(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
    )
    return list(result)


async def get_owned(db: AsyncSession, user: User, conversation_id: int) -> Conversation:
    conv = await db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


async def delete(db: AsyncSession, user: User, conversation_id: int) -> None:
    conv = await get_owned(db, user, conversation_id)
    await db.delete(conv)
    await db.commit()


async def list_messages(db: AsyncSession, user: User, conversation_id: int) -> list[Message]:
    await get_owned(db, user, conversation_id)
    result = await db.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id))
    return list(result)
```

```python
# app/api/conversations.py
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.conversation import ConversationList, ConversationOut
from app.schemas.message import MessageList
from app.services import conversation_service
from app.services.stream_manager import manager

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await conversation_service.create(db, user)


@router.get("", response_model=ConversationList)
async def list_conversations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    items = await conversation_service.list_by_user(db, user)
    return ConversationList(
        items=[ConversationOut.model_validate(c).model_copy(update={"running": manager.has_running(c.id)}) for c in items]
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await manager.cancel_conversation(conversation_id)
    await conversation_service.delete(db, user, conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{conversation_id}/messages", response_model=MessageList)
async def list_messages(conversation_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    items = await conversation_service.list_messages(db, user, conversation_id)
    return MessageList(items=items)
```

> 注：`manager` 在 Task 5 实现；Task 3 先创建 `app/services/stream_manager.py` 的最小桩（`has_running -> False`、`cancel_conversation -> None`），Task 5 补齐。

- [ ] **Step 4: 跑测试**

Run: `venv\Scripts\python.exe -m pytest tests/test_conversations.py -q`
Expected: `3 passed`

- [ ] **Step 5: 提交**

```bash
git add ai-chat-lite/backend && git commit -m "feat(ai-chat-lite): 会话与消息模型及会话 CRUD"
```

---

### Task 4: httpx 上游流客户端

**Files:**
- Create: `app/services/llm_client.py`
- Test: `tests/test_llm_client.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_llm_client.py
import json

import httpx
import pytest

from app.services import llm_client


def _sse_line(content: str, done: bool = False) -> bytes:
    if done:
        return b"data: [DONE]\n\n"
    payload = {"choices": [{"delta": {"content": content}}]}
    return f"data: {json.dumps(payload)}\n\n".encode()


def _install_transport(handler):
    llm_client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://upstream")


async def test_collects_deltas_across_chunk_boundaries():
    body = _sse_line("你") + b": keepalive\n\n" + _sse_line("好") + _sse_line("", done=True)

    async def handler(request: httpx.Request) -> httpx.Response:
        async def gen():
            for i in range(0, len(body), 7):   # 故意在 JSON 中间切块
                yield body[i:i + 7]
        return httpx.Response(200, content=gen())

    _install_transport(handler)
    chunks = [c async for c in llm_client.stream_chat([{"role": "user", "content": "hi"}])]
    assert chunks == ["你", "好"]


async def test_http_error_raises_upstream_http():
    async def handler(request):
        return httpx.Response(500, text="boom")

    _install_transport(handler)
    with pytest.raises(llm_client.UpstreamError) as exc:
        [c async for c in llm_client.stream_chat([{"role": "user", "content": "hi"}])]
    assert exc.value.code == "upstream_http"
    assert "500" in exc.value.message


async def test_bad_json_raises_upstream_parse():
    async def handler(request):
        return httpx.Response(200, content=b"data: {not-json}\n\n")

    _install_transport(handler)
    with pytest.raises(llm_client.UpstreamError) as exc:
        [c async for c in llm_client.stream_chat([{"role": "user", "content": "hi"}])]
    assert exc.value.code == "upstream_parse"
```

- [ ] **Step 2: 运行确认失败**

Run: `venv\Scripts\python.exe -m pytest tests/test_llm_client.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

```python
# app/services/llm_client.py
import json
from collections.abc import AsyncIterator

import httpx

from app.config import settings


class UpstreamError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


_client: httpx.AsyncClient | None = None


def init_client() -> None:
    global _client
    _client = httpx.AsyncClient(
        base_url=settings.DEEPSEEK_BASE_URL,
        timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
    )


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def stream_chat(messages: list[dict], model: str | None = None) -> AsyncIterator[str]:
    client = _client
    if client is None:
        init_client()
        client = _client
    payload = {
        "model": model or settings.DEEPSEEK_MODEL,
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
    }
    headers = {"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}", "Accept": "text/event-stream"}
    try:
        async with client.stream("POST", "/chat/completions", json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                body = (await resp.aread()).decode("utf-8", "replace")[:300]
                raise UpstreamError("upstream_http", f"HTTP {resp.status_code}: {body}")
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content")
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    raise UpstreamError("upstream_parse", data[:300])
                if delta:
                    yield delta
    except UpstreamError:
        raise
    except (httpx.HTTPError, OSError) as exc:
        raise UpstreamError("upstream_network", f"{type(exc).__name__}: {exc}") from exc
```

- [ ] **Step 4: 跑测试**

Run: `venv\Scripts\python.exe -m pytest tests/test_llm_client.py -q`
Expected: `3 passed`

- [ ] **Step 5: 提交**

```bash
git add ai-chat-lite/backend && git commit -m "feat(ai-chat-lite): httpx 逐行消费上游 SSE 流"
```

---

### Task 5: SSE 编码与流任务管理（start / subscribe / stop / 续传）

**Files:**
- Create: `app/core/sse.py`
- Create: `app/services/stream_manager.py`（替换 Task 3 的最小桩）
- Test: `tests/test_stream_manager.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_stream_manager.py
import asyncio

import pytest
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services import llm_client
from app.services.stream_manager import manager


def _parse(event_text: str) -> tuple[str, dict]:
    lines = [l for l in event_text.split("\n") if l]
    event = next(l[7:] for l in lines if l.startswith("event: "))
    data = next(l[6:] for l in lines if l.startswith("data: "))
    import json
    return event, json.loads(data)


async def _seed_message(status="streaming"):
    async with async_session_factory() as db:
        user = User(username=f"u{asyncio.get_event_loop().time()}", password_hash="x")
        db.add(user)
        await db.flush()
        conv = Conversation(user_id=user.id)
        db.add(conv)
        await db.flush()
        msg = Message(conversation_id=conv.id, role="assistant", content="", status=status)
        db.add(msg)
        await db.commit()
        return user.id, conv.id, msg.id


async def test_normal_stream_and_persist(monkeypatch):
    async def fake_stream(messages, model=None):
        for d in ["你", "好"]:
            yield d
    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)

    _, conv_id, mid = await _seed_message()
    manager.start(mid, conv_id, 1, [{"role": "user", "content": "hi"}])
    session = manager.get(mid)
    events = [e async for e in manager.subscribe(session, -1)]

    parsed = [_parse(e) for e in events if not e.startswith(":")]
    assert [e for e, _ in parsed] == ["delta", "delta", "done"]
    assert parsed[0][1]["seq"] == 0 and parsed[1][1]["content"] == "好"
    assert parsed[-1][1]["status"] == "done"

    async with async_session_factory() as db:
        msg = await db.get(Message, mid)
        assert msg.status == "done" and msg.content == "你好"


async def test_upstream_error_emits_error_event(monkeypatch):
    async def failing(messages, model=None):
        yield "A"
        raise llm_client.UpstreamError("upstream_network", "ReadError: boom")
    monkeypatch.setattr(llm_client, "stream_chat", failing)

    _, conv_id, mid = await _seed_message()
    manager.start(mid, conv_id, 1, [{"role": "user", "content": "hi"}])
    events = [_parse(e)[0] async for e in manager.subscribe(manager.get(mid), -1) if not e.startswith(":")]
    assert events == ["delta", "error"]

    async with async_session_factory() as db:
        msg = await db.get(Message, mid)
        assert msg.status == "failed" and msg.content == "A" and "boom" in (msg.error or "")


async def test_stop_persists_partial_content(monkeypatch):
    gate = asyncio.Event()

    async def slow(messages, model=None):
        yield "A"
        await gate.wait()
        yield "B"
    monkeypatch.setattr(llm_client, "stream_chat", slow)

    _, conv_id, mid = await _seed_message()
    manager.start(mid, conv_id, 1, [{"role": "user", "content": "hi"}])
    session = manager.get(mid)
    agen = manager.subscribe(session, -1)
    assert "A" in await agen.__anext__()
    await manager.stop(mid)
    rest = [_parse(e) async for e in agen if not e.startswith(":")]
    assert rest[-1][1]["status"] == "stopped"

    async with async_session_factory() as db:
        msg = await db.get(Message, mid)
        assert msg.status == "stopped" and msg.content == "A"


async def test_resume_from_skips_received(monkeypatch):
    gate = asyncio.Event()

    async def slow(messages, model=None):
        yield "A"
        yield "B"
        await gate.wait()
        yield "C"
    monkeypatch.setattr(llm_client, "stream_chat", slow)

    _, conv_id, mid = await _seed_message()
    manager.start(mid, conv_id, 1, [{"role": "user", "content": "hi"}])
    session = manager.get(mid)
    await asyncio.sleep(0.05)
    events = [_parse(e) async for e in manager.subscribe(session, 1)]
    assert [d["seq"] for _, d in events if _ == "delta"] == [2]


async def test_heartbeat_emits_ping(monkeypatch):
    monkeypatch.setattr(settings, "HEARTBEAT_SECONDS", 0.05)
    gate = asyncio.Event()

    async def slow(messages, model=None):
        yield "A"
        await gate.wait()
    monkeypatch.setattr(llm_client, "stream_chat", slow)

    _, conv_id, mid = await _seed_message()
    manager.start(mid, conv_id, 1, [{"role": "user", "content": "hi"}])
    session = manager.get(mid)
    agen = manager.subscribe(session, 0)
    assert (await agen.__anext__()).startswith(": ping")
    await manager.stop(mid)
```

> 测试结束用 fixture 的 `manager.reset()` 兜底，避免跨用例泄漏。

- [ ] **Step 2: 运行确认失败**

Run: `venv\Scripts\python.exe -m pytest tests/test_stream_manager.py -q`
Expected: FAIL（无 sse / stream_manager 桩无 start）

- [ ] **Step 3: 写实现**

```python
# app/core/sse.py
import json

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def format_event(event: str, data: dict, event_id: int | None = None) -> str:
    lines = [f"event: {event}"]
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append("data: " + json.dumps(data, ensure_ascii=False))
    return "\n".join(lines) + "\n\n"
```

```python
# app/services/stream_manager.py
import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.config import settings
from app.core.sse import format_event
from app.database import async_session_factory, utcnow
from app.models.conversation import Conversation
from app.models.message import Message
from app.services import llm_client

SESSION_TTL_SECONDS = 600


@dataclass
class StreamSession:
    message_id: int
    conversation_id: int
    owner_id: int
    status: str = "running"
    parts: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    waiters: set[asyncio.Event] = field(default_factory=set)
    task: asyncio.Task | None = None
    finished_at: float | None = None
    last_flush: float = 0.0
    unflushed: int = 0

    @property
    def content(self) -> str:
        return "".join(self.parts)

    @property
    def last_seq(self) -> int:
        return len(self.parts) - 1


class StreamManager:
    def __init__(self) -> None:
        self._sessions: dict[int, StreamSession] = {}

    def get(self, message_id: int) -> StreamSession | None:
        return self._sessions.get(message_id)

    def has_running(self, conversation_id: int) -> bool:
        return any(
            s.conversation_id == conversation_id and s.status == "running"
            for s in self._sessions.values()
        )

    def start(self, message_id: int, conversation_id: int, owner_id: int, prompt: list[dict]) -> StreamSession:
        session = StreamSession(message_id=message_id, conversation_id=conversation_id, owner_id=owner_id)
        self._sessions[message_id] = session
        session.task = asyncio.create_task(self._run(session, prompt))
        return session

    async def stop(self, message_id: int) -> StreamSession | None:
        session = self._sessions.get(message_id)
        if session is None:
            return None
        await self._cancel(session)
        return session

    async def cancel_conversation(self, conversation_id: int) -> None:
        for session in list(self._sessions.values()):
            if session.conversation_id == conversation_id and session.status == "running":
                await self._cancel(session)

    async def _cancel(self, session: StreamSession) -> None:
        if session.status != "running" or session.task is None:
            return
        session.task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(session.task), timeout=5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    async def subscribe(self, session: StreamSession, resume_from: int = -1) -> AsyncIterator[str]:
        cursor = max(resume_from, -1)
        waiter = asyncio.Event()
        session.waiters.add(waiter)
        try:
            while True:
                for seq in range(cursor + 1, len(session.parts)):
                    yield format_event("delta", {"seq": seq, "content": session.parts[seq]}, event_id=seq)
                cursor = max(cursor, len(session.parts) - 1)
                if session.status != "running":
                    yield self._terminal_event(session)
                    return
                try:
                    await asyncio.wait_for(waiter.wait(), timeout=settings.HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                waiter.clear()
        finally:
            session.waiters.discard(waiter)

    def _terminal_event(self, session: StreamSession) -> str:
        if session.status == "failed":
            return format_event(
                "error",
                {
                    "message_id": session.message_id,
                    "status": "failed",
                    "code": session.error_code or "internal",
                    "message": session.error_message or "生成失败",
                },
            )
        return format_event(
            "done",
            {"message_id": session.message_id, "status": session.status, "content": session.content},
        )

    async def _run(self, session: StreamSession, prompt: list[dict]) -> None:
        try:
            async with asyncio.timeout(settings.STREAM_TIMEOUT_SECONDS):
                async for delta in llm_client.stream_chat(prompt):
                    session.parts.append(delta)
                    session.unflushed += 1
                    await self._maybe_flush(session)
                    self._notify(session)
            session.status = "done"
        except asyncio.TimeoutError:
            session.status = "failed"
            session.error_code = "timeout"
            session.error_message = f"生成超时（{settings.STREAM_TIMEOUT_SECONDS}s）"
        except asyncio.CancelledError:
            session.status = "stopped"
        except llm_client.UpstreamError as exc:
            session.status = "failed"
            session.error_code = exc.code
            session.error_message = exc.message
        except Exception as exc:  # 兜底：任何异常都转成 error 事件，不向前端泄漏堆栈
            session.status = "failed"
            session.error_code = "internal"
            session.error_message = f"{type(exc).__name__}: {exc}"
        finally:
            await self._flush(session, final=True)
            session.finished_at = time.monotonic()
            self._notify(session)
            asyncio.create_task(self._cleanup_later(session))

    async def _maybe_flush(self, session: StreamSession) -> None:
        if session.unflushed >= 20 or time.monotonic() - session.last_flush >= settings.FLUSH_INTERVAL_SECONDS:
            await self._flush(session)

    async def _flush(self, session: StreamSession, final: bool = False) -> None:
        try:
            async with async_session_factory() as db:
                msg = await db.get(Message, session.message_id)
                if msg is None:
                    return
                msg.content = session.content
                msg.status = session.status
                msg.error = session.error_message if session.status == "failed" else None
                msg.updated_at = utcnow()
                if final:
                    conv = await db.get(Conversation, session.conversation_id)
                    if conv is not None:
                        conv.updated_at = utcnow()
                await db.commit()
        finally:
            session.last_flush = time.monotonic()
            session.unflushed = 0

    def _notify(self, session: StreamSession) -> None:
        for waiter in list(session.waiters):
            waiter.set()

    async def _cleanup_later(self, session: StreamSession) -> None:
        await asyncio.sleep(SESSION_TTL_SECONDS)
        if self._sessions.get(session.message_id) is session:
            self._sessions.pop(session.message_id, None)

    def shutdown(self) -> None:
        for session in self._sessions.values():
            if session.task is not None and not session.task.done():
                session.task.cancel()
        self._sessions.clear()

    def reset(self) -> None:
        self.shutdown()


manager = StreamManager()
```

- [ ] **Step 4: 跑测试**

Run: `venv\Scripts\python.exe -m pytest tests/test_stream_manager.py -q`
Expected: `5 passed`

- [ ] **Step 5: 提交**

```bash
git add ai-chat-lite/backend && git commit -m "feat(ai-chat-lite): 流任务管理、SSE 编码与断点续传"
```

---

### Task 6: 消息接口（发消息 / 订阅 / 停止 / 裁剪 / 409）

**Files:**
- Create: `app/services/chat_service.py`
- Create: `app/api/messages.py`
- Modify: `app/api/conversations.py`（新增 `POST /{id}/messages`）
- Modify: `app/api/router.py`
- Test: `tests/test_stream.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_stream.py
import asyncio
import json

import pytest
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models.message import Message
from app.services import llm_client, chat_service
from app.services.stream_manager import manager
from tests.test_auth import _register_and_login


async def _setup(client, username="alice"):
    token = await _register_and_login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    cid = (await client.post("/api/conversations", headers=headers)).json()["id"]
    return headers, cid


async def _collect(response):
    events = []
    current = {}
    async for line in response.aiter_lines():
        if line.startswith("event: "):
            current["event"] = line[7:]
        elif line.startswith("data: "):
            current["data"] = json.loads(line[6:])
        elif line == "":
            if current:
                events.append(current)
                current = {}
    return events


async def test_normal_stream_persists(client, monkeypatch):
    async def fake_stream(messages, model=None):
        for d in ["你", "好"]:
            yield d
    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)

    headers, cid = await _setup(client)
    resp = await client.post(f"/api/conversations/{cid}/messages", json={"content": "你好"}, headers=headers)
    assert resp.status_code == 201
    mid = resp.json()["assistant_message"]["id"]

    async with client.stream("GET", f"/api/messages/{mid}/stream", headers=headers) as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        events = await _collect(stream)

    assert [e["event"] for e in events] == ["delta", "delta", "done"]
    assert events[-1]["data"]["content"] == "你好"

    async with async_session_factory() as db:
        msg = await db.get(Message, mid)
        assert msg.status == "done" and msg.content == "你好"


async def test_upstream_failure_emits_error_and_marks_failed(client, monkeypatch):
    async def failing(messages, model=None):
        yield "A"
        raise llm_client.UpstreamError("upstream_http", "HTTP 500")
    monkeypatch.setattr(llm_client, "stream_chat", failing)

    headers, cid = await _setup(client)
    mid = (await client.post(f"/api/conversations/{cid}/messages", json={"content": "hi"}, headers=headers)).json()["assistant_message"]["id"]
    async with client.stream("GET", f"/api/messages/{mid}/stream", headers=headers) as stream:
        events = await _collect(stream)
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["code"] == "upstream_http"


async def test_stop_returns_done_stopped(client, monkeypatch):
    gate = asyncio.Event()

    async def slow(messages, model=None):
        yield "A"
        await gate.wait()
    monkeypatch.setattr(llm_client, "stream_chat", slow)

    headers, cid = await _setup(client)
    mid = (await client.post(f"/api/conversations/{cid}/messages", json={"content": "hi"}, headers=headers)).json()["assistant_message"]["id"]

    async with client.stream("GET", f"/api/messages/{mid}/stream", headers=headers) as stream:
        gen = stream.aiter_lines()
        assert "delta" in await gen.__anext__()
        stop_resp = await client.post(f"/api/messages/{mid}/stop", headers=headers)
        assert stop_resp.json()["status"] == "stopped"
        rest = await _collect(stream)
    assert rest[-1]["event"] == "done" and rest[-1]["data"]["status"] == "stopped"


async def test_resume_from_skips_received(client, monkeypatch):
    gate = asyncio.Event()

    async def slow(messages, model=None):
        yield "A"
        yield "B"
        await gate.wait()
        yield "C"
    monkeypatch.setattr(llm_client, "stream_chat", slow)

    headers, cid = await _setup(client)
    mid = (await client.post(f"/api/conversations/{cid}/messages", json={"content": "hi"}, headers=headers)).json()["assistant_message"]["id"]
    await asyncio.sleep(0.1)
    gate.set()

    async with client.stream("GET", f"/api/messages/{mid}/stream?resume_from=1", headers=headers) as stream:
        events = await _collect(stream)
    seqs = [e["data"]["seq"] for e in events if e["event"] == "delta"]
    assert seqs == [2]


async def test_resume_out_of_range_400(client, monkeypatch):
    async def fake_stream(messages, model=None):
        yield "A"
    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)
    headers, cid = await _setup(client)
    mid = (await client.post(f"/api/conversations/{cid}/messages", json={"content": "hi"}, headers=headers)).json()["assistant_message"]["id"]
    await asyncio.sleep(0.1)
    resp = await client.get(f"/api/messages/{mid}/stream?resume_from=99", headers=headers)
    assert resp.status_code == 400


async def test_concurrency_409(client, monkeypatch):
    gate = asyncio.Event()

    async def slow(messages, model=None):
        yield "A"
        await gate.wait()
    monkeypatch.setattr(llm_client, "stream_chat", slow)

    headers, cid = await _setup(client)
    await client.post(f"/api/conversations/{cid}/messages", json={"content": "one"}, headers=headers)
    resp = await client.post(f"/api/conversations/{cid}/messages", json={"content": "two"}, headers=headers)
    assert resp.status_code == 409


async def test_context_trimming_payload(client, monkeypatch):
    captured = {}
    started = asyncio.Event()

    async def fake_stream(messages, model=None):
        captured["messages"] = messages
        started.set()
        yield "ok"
    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)
    monkeypatch.setattr(settings, "MAX_CONTEXT_MESSAGES", 3)

    headers, cid = await _setup(client)
    for i in range(6):
        mid = (await client.post(f"/api/conversations/{cid}/messages", json={"content": f"q{i}"}, headers=headers)).json()["assistant_message"]["id"]
        await asyncio.sleep(0.05)

    await asyncio.wait_for(started.wait(), timeout=2)
    assert captured["messages"][0]["role"] == "system"
    assert len(captured["messages"]) == 4   # system + 最近 3 条
    assert captured["messages"][-1]["content"] == "q5"


async def test_terminal_without_session_synthesizes_done(client, monkeypatch):
    async def fake_stream(messages, model=None):
        yield "A"
    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)
    headers, cid = await _setup(client)
    mid = (await client.post(f"/api/conversations/{cid}/messages", json={"content": "hi"}, headers=headers)).json()["assistant_message"]["id"]
    await asyncio.sleep(0.1)
    manager.reset()   # 模拟会话已被清理 / 进程重启
    async with client.stream("GET", f"/api/messages/{mid}/stream", headers=headers) as stream:
        events = await _collect(stream)
    assert events[-1]["event"] == "done" and events[-1]["data"]["status"] == "done"


async def test_recover_stale_streaming(client):
    headers, cid = await _setup(client)
    async with async_session_factory() as db:
        msg = Message(conversation_id=cid, role="assistant", content="partial", status="streaming")
        db.add(msg)
        await db.commit()
        mid = msg.id
    await chat_service.recover_stale_streaming()
    async with async_session_factory() as db:
        msg = await db.get(Message, mid)
        assert msg.status == "failed" and "重启" in (msg.error or "")


async def test_other_user_message_404(client, monkeypatch):
    async def fake_stream(messages, model=None):
        yield "A"
    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)
    alice_headers, cid = await _setup(client, "alice")
    bob_headers, _ = await _setup(client, "bob")
    mid = (await client.post(f"/api/conversations/{cid}/messages", json={"content": "hi"}, headers=alice_headers)).json()["assistant_message"]["id"]
    resp = await client.get(f"/api/messages/{mid}/stream", headers=bob_headers)
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `venv\Scripts\python.exe -m pytest tests/test_stream.py -q`
Expected: FAIL（无 chat_service / messages 路由）

- [ ] **Step 3: 写实现**

```python
# app/services/chat_service.py
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory, utcnow
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services import conversation_service
from app.services.stream_manager import manager


async def build_prompt(db: AsyncSession, conversation_id: int) -> list[dict]:
    rows = await db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role.in_(["user", "assistant"]),
            Message.status.in_(["done", "stopped"]),
        )
        .order_by(Message.id.desc())
        .limit(settings.MAX_CONTEXT_MESSAGES)
    )
    history = list(reversed(list(rows)))
    return [{"role": "system", "content": settings.SYSTEM_PROMPT}] + [
        {"role": m.role, "content": m.content} for m in history if m.content
    ]


async def send_message(db: AsyncSession, user: User, conversation_id: int, content: str) -> tuple[Message, Message]:
    conv = await conversation_service.get_owned(db, user, conversation_id)
    if manager.has_running(conv.id):
        raise HTTPException(status_code=409, detail="该会话正在生成回复，请稍候")

    user_msg = Message(conversation_id=conv.id, role="user", content=content, status="done")
    db.add(user_msg)
    if conv.title == "新对话":
        conv.title = " ".join(content.splitlines()).strip()[:20] or "新对话"
    conv.updated_at = utcnow()
    await db.flush()

    assistant_msg = Message(conversation_id=conv.id, role="assistant", content="", status="streaming")
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)

    prompt = await build_prompt(db, conv.id)
    manager.start(assistant_msg.id, conv.id, user.id, prompt)
    return user_msg, assistant_msg


async def recover_stale_streaming() -> None:
    async with async_session_factory() as db:
        await db.execute(
            update(Message)
            .where(Message.role == "assistant", Message.status == "streaming")
            .values(status="failed", error="服务重启中断", updated_at=utcnow())
        )
        await db.commit()
```

```python
# app/api/conversations.py 追加
from fastapi import status as http_status
from app.schemas.message import SendMessageRequest, SendMessageResponse
from app.services import chat_service


@router.post("/{conversation_id}/messages", response_model=SendMessageResponse, status_code=http_status.HTTP_201_CREATED)
async def send_message(
    conversation_id: int,
    payload: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_msg, assistant_msg = await chat_service.send_message(db, user, conversation_id, payload.content)
    return SendMessageResponse(user_message=user_msg, assistant_message=assistant_msg)
```

```python
# app/api/messages.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.sse import SSE_HEADERS, format_event
from app.database import get_db, utcnow
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services.stream_manager import manager

router = APIRouter(prefix="/messages", tags=["messages"])


async def _owned_message(db: AsyncSession, user: User, message_id: int) -> tuple[Message, Conversation]:
    msg = await db.get(Message, message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="消息不存在")
    conv = await db.get(Conversation, msg.conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="消息不存在")
    return msg, conv


@router.get("/{message_id}/stream")
async def stream_message(
    message_id: int,
    resume_from: int = -1,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg, _ = await _owned_message(db, user, message_id)
    session = manager.get(message_id)
    if session is None:
        async def terminal_only():
            if msg.status == "failed":
                yield format_event("error", {
                    "message_id": msg.id, "status": "failed",
                    "code": "internal", "message": msg.error or "生成失败",
                })
            else:
                yield format_event("done", {"message_id": msg.id, "status": msg.status, "content": msg.content})
        return StreamingResponse(terminal_only(), media_type="text/event-stream", headers=SSE_HEADERS)

    if resume_from < -1 or resume_from > session.last_seq:
        raise HTTPException(status_code=400, detail="resume_from 越界")
    return StreamingResponse(manager.subscribe(session, resume_from), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/{message_id}/stop")
async def stop_message(
    message_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg, _ = await _owned_message(db, user, message_id)
    session = await manager.stop(message_id)
    status = session.status if session is not None else msg.status
    return {"message_id": message_id, "status": status}
```

`app/api/router.py` 增加 `api_router.include_router(messages.router)`。

- [ ] **Step 4: 跑测试**

Run: `venv\Scripts\python.exe -m pytest tests/test_stream.py -q`
Expected: `10 passed`

- [ ] **Step 5: 提交**

```bash
git add ai-chat-lite/backend && git commit -m "feat(ai-chat-lite): 消息收发、SSE 订阅与停止生成"
```

---

### Task 7: 应用装配、启动恢复与静态托管

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_health.py`（追加静态托管断言）

- [ ] **Step 1: 追加失败测试**

```python
async def test_frontend_index_served(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "ai-chat-lite" in resp.text.lower()
```

- [ ] **Step 2: 写实现**

```python
# app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import settings
from app.database import init_db
from app.services import chat_service, llm_client
from app.services.stream_manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await chat_service.recover_stale_streaming()
    llm_client.init_client()
    yield
    manager.shutdown()
    await llm_client.close_client()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.include_router(api_router)
if settings.FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(settings.FRONTEND_DIR), html=True), name="frontend")
```

- [ ] **Step 3: 跑全量测试**

Run: `venv\Scripts\python.exe -m pytest -q`
Expected: 全部 passed（约 26 个）

- [ ] **Step 4: 提交**

```bash
git add ai-chat-lite/backend && git commit -m "feat(ai-chat-lite): 应用装配、启动恢复与静态托管"
```

---

### Task 8: 原生前端页面与样式

**Files:**
- Create: `ai-chat-lite/frontend/index.html`
- Create: `ai-chat-lite/frontend/styles.css`

- [ ] **Step 1: 写 index.html**

要求：`<title>AI Chat Lite</title>`；两个顶层 section：#auth-view（登录/注册切换、用户名/密码、错误提示）与 #app-view（aside 会话列表 + 新建按钮、main 消息滚动区、底部 textarea + 发送/停止按钮）；`<script src="/app.js" type="module">`、`<script src="/markdown.js">`。

- [ ] **Step 2: 写 styles.css**

要求：CSS 变量定义配色；flex 三栏布局（侧边栏 240px）；消息气泡 user 右对齐、assistant 左对齐；`.msg-status` 显示“已停止/生成失败”标记；响应式在 <768px 收起侧边栏；`#auth-view` 居中卡片。

- [ ] **Step 3: 浏览器验证**

Run: `venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`，访问 http://127.0.0.1:8000
Expected: 出现登录卡片，控制台无 404

---

### Task 9: 前端 SSE 解析、打字机与交互

**Files:**
- Create: `ai-chat-lite/frontend/app.js`
- Create: `ai-chat-lite/frontend/markdown.js`

- [ ] **Step 1: 写 markdown.js**

要求：导出 `window.renderMarkdown(text)`；先 `escapeHtml`，再按序处理围栏代码块 → 标题 → 加粗 → 行内码 → 无序列表 → 双换行转段落。不得执行原始 HTML。

- [ ] **Step 2: 写 app.js**

核心结构：

```js
const state = { token: localStorage.getItem('token') || '', conversations: [], currentId: null, messages: [], stream: null };

async function api(path, options = {}) { /* fetch + Bearer + 401 清 token */ }

function parseSSEBlock(block) { /* 返回 {event, id, data}，忽略 : 注释 */ }

async function openStream(mid, resumeFrom = -1) {
  const ctrl = new AbortController();
  state.stream = { mid, lastSeq: resumeFrom, ctrl, retries: 0 };
  const res = await fetch(`/api/messages/${mid}/stream?resume_from=${resumeFrom}`, {
    headers: { Authorization: `Bearer ${state.token}` }, signal: ctrl.signal,
  });
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, idx); buffer = buffer.slice(idx + 2);
      handleEvent(parseSSEBlock(block));
    }
  }
}
```

必须实现：rAF 批量追加、距底 80px 才滚动、done 后 markdown 渲染、error 显示红色标记、重连（1s/2s/4s，最多 3 次，带 lastSeq）、停止按钮先 POST stop 再 abort、切换运行中会话时从 -1 重订阅、删除会话二次确认、回车发送 Shift+Enter 换行。

- [ ] **Step 3: 浏览器联调**

Expected: 登录 → 新建会话 → 输入发送 → 打字机输出 → 停止生效 → 刷新恢复历史 → 断网重连补发。

---

### Task 10: README、根索引与全量验证

**Files:**
- Create: `ai-chat-lite/README.md`
- Modify: `README.md`（项目总览表与架构树各加一行）

- [ ] **Step 1: 写 ai-chat-lite/README.md**

内容：功能特性、技术栈、目录结构、启动步骤（venv、pip、.env、uvicorn）、API 表、SSE 事件示例、手动联调清单、常见问题（bcrypt 版本、无 Key 时的报错表现）。

- [ ] **Step 2: 更新根 README**

在项目总览表加入 `ai-chat-lite` 行；在架构树加入 `ai-chat-lite/` 两行；学习路径补一句。

- [ ] **Step 3: 全量回归**

Run: `cd ai-chat-lite/backend && venv\Scripts\python.exe -m pytest -q`
Expected: 全部 passed

- [ ] **Step 4: 真实接口冒烟（有 Key 时）**

Run: `venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`，浏览器完成一次真实对话并点击停止。
Expected: 逐字输出、停止后状态为“已停止”、刷新后内容保留。

- [ ] **Step 5: 提交**

```bash
git add ai-chat-lite README.md && git commit -m "docs(ai-chat-lite): 使用说明与根索引登记"
```

---

## 自审记录

- 规格覆盖：设计说明第 3-13 节均对应到 Task 1-10；非目标未排入任务。
- 类型一致性：`manager.start(message_id, conversation_id, owner_id, prompt)`、`manager.subscribe(session, resume_from)`、`llm_client.stream_chat(messages, model=None)`、`format_event(event, data, event_id=None)` 在各任务中签名一致。
- 依赖顺序：Task 3 的 `stream_manager` 桩在 Task 5 被完整替换；`chat_service` 依赖 Task 3 模型与 Task 5 管理器。
- 已知取舍：运行中消息以 buffer 为权威、终态以 DB 为权威；单进程假设，不做多实例。

---

## 实施记录（与计划的偏差）

实施已按本计划完成，单测与端到端冒烟均通过。以下为执行中发现的偏差，供后续维护参考：

1. **httpx 0.28 的 `ASGITransport` 会缓冲整个响应体**：源码里先 `await self.app(...)` 断言 `response_complete`，再一次性 `join(body_parts)`，因此进程内无法验证“边读 SSE 边并发 stop”的时序。Task 6 中此类断言改为顺序断言（先 sleep 再 POST stop，最后 GET stream 读终态）；实时语义由 `tests/test_stream_manager.py` 直接驱动 `subscribe()` 覆盖，真实逐块时序由 `scripts/e2e_stream_smoke.py` 对真实 uvicorn 验证。
2. **终态事件必须先落库**：新增 `StreamSession.finalized: asyncio.Event`，`subscribe()` 在发终止事件前 `await finalized.wait()`（超时 5s），`_run` 的 finally 中 flush 后才 set，避免客户端收到 done 时 DB 仍是 `streaming`。
3. **后台清理任务的创建方式**：`_cleanup_later` 必须用 `asyncio.create_task(...)` 再 `_track`，直接传协程会导致 teardown 时 `'coroutine' object has no attribute 'cancel'`。
4. **跨事件循环连接复用**：测试在多个事件循环间反复建表，需 `poolclass=NullPool`；fixture 前后都调用 `manager.ashutdown()`（cancel + gather）清理任务，否则出现 `no active connection` 噪音。
5. **bcrypt 72 字节截断的测试写法**：Pydantic 的 `max_length=64` 按字符计，超长密码用例改用 30 个汉字（90 字节）才能在合法请求内验证截断。
6. **数据库默认路径**：`DATABASE_URL` 默认改为按 `BASE_DIR` 计算的绝对路径（`config.DEFAULT_DATABASE_URL`），避免受启动目录影响。
7. **新增交付物**：`backend/scripts/fake_upstream.py`（假上游）与 `backend/scripts/e2e_stream_smoke.py`（30 项端到端断言），用于无真实 Key 时验证完整流式链路；`backend/.gitignore` 隔离 venv/数据库/环境文件；`.qoder/docs/README.md` 作为文档索引。
8. **前端静态资源测试**：`test_health.py` 原先断言首页包含 `ai-chat-lite` 字样，与页面标题 `AI Chat Lite` 不匹配，改为断言 `id="auth-view"` 与 `/app.js`，并新增三个静态资源可达性断言（共 36 项单测）。
9. **提交未执行**：按仓库约定，未经明确指示不自动 `git commit`；`.qoder/` 目录当前未被 gitignore 覆盖，若提交需只 `git add ai-chat-lite README.md`，勿 `git add .`。
10. **浏览器验收暴露的缺陷（已修）**：`StreamSession.status` 原设计用 `running`，而 `messages.status` 用 `streaming`，`_flush` 把前者直接写库 → 消息创建 0.5s 后 DB 变成 `running`。后果：① 前端刷新时按 `status == "streaming"` 判断是否重订阅永不成立，断点续传失效（气泡停在刷新那一刻、也不显示「生成中…」）；② `recover_stale_streaming()` 只收敛 `streaming`，重启后 `running` 消息永久无主。修复：会话状态词表统一为 `streaming/done/stopped/failed`，并在 `StreamSession` 上写明词表约束。回归：新增 `test_running_message_flushes_streaming_status`，并给 `e2e_stream_smoke.py` 加「停止前 DB 状态必须是 streaming」断言（共 37 项单测）。
11. **前端标题竞态（已修）**：`chatTitle` 只在 `refreshConversations()` 里赋值，而刷新时 `currentId` 为 null，导致刷新后标题短暂显示「新对话」。修复：`selectConversation()` 选中会话时直接用列表里的标题回填。
12. **假上游慢速模式**：`scripts/fake_upstream.py` 支持 `FAKE_DELAY_SECONDS`（每段间隔）与 `FAKE_REPEAT`（整段重复次数），浏览器验收时用 `0.5` + `4`（约 24s/条）才来得及观察停止与刷新续传。

