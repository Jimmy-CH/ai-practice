# AI 运营物料智能生成助手编辑与审核工作流实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `ai-material-generator` 中增加编辑与审核工作流：后端引入 SQLite + JWT + 资产状态机，前端引入 Router + Pinia + 登录/列表/编辑/审核页面。

**Architecture:** 后端基于 FastAPI + SQLAlchemy 2.0 async + aiosqlite 持久化 `User` 与 `MaterialAsset`；前端基于 Vue3 + Element Plus + Pinia 管理登录态，Vue Router 控制页面权限。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 async, aiosqlite, passlib, python-jose, Vue3, TypeScript, Element Plus, Pinia, Vue Router.

---

## Task 1: 后端依赖与数据库基础设施

**Files:**
- Modify: `ai-material-generator/backend/requirements.txt`
- Create: `ai-material-generator/backend/app/database.py`
- Create: `ai-material-generator/backend/app/models/__init__.py`
- Create: `ai-material-generator/backend/app/models/base.py`
- Modify: `ai-material-generator/backend/app/config.py`
- Modify: `ai-material-generator/backend/pytest.ini`

- [ ] **Step 1: 添加数据库与认证依赖**

```text
sqlalchemy[asyncio]==2.0.40
aiosqlite==0.21.0
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.4.0
```

追加到 `requirements.txt`。

- [ ] **Step 2: 创建数据库引擎与 session**

`app/database.py`:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = "sqlite+aiosqlite:///./materials.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 3: 创建模型包**

`app/models/__init__.py` 初始为空。

`app/models/base.py`:

```python
from app.database import Base
```

- [ ] **Step 4: 扩展 config 添加 JWT 配置**

`app/config.py`:

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env" if Path(".env").exists() else None,
        env_file_encoding="utf-8",
    )
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    secret_key: str = "dev-secret-key-change-in-production"
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"


settings = Settings()
```

- [ ] **Step 5: 修改 pytest.ini 支持异步数据库测试**

`pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

- [ ] **Step 6: 安装依赖并验证**

```bash
cd ai-material-generator/backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Expected: 安装成功，无报错。

- [ ] **Step 7: Commit**

```bash
git add requirements.txt app/database.py app/models/ app/config.py pytest.ini
git commit -m "chore: add async sqlite and auth dependencies"
```

---

## Task 2: 用户模型与认证

**Files:**
- Create: `ai-material-generator/backend/app/models/user.py`
- Create: `ai-material-generator/backend/app/schemas/auth.py`
- Create: `ai-material-generator/backend/app/services/security.py`
- Create: `ai-material-generator/backend/app/services/auth_service.py`
- Create: `ai-material-generator/backend/app/api/auth.py`
- Modify: `ai-material-generator/backend/app/main.py`

- [ ] **Step 1: 创建 User 模型**

`app/models/user.py`:

```python
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="editor", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: 创建认证 schema**

`app/schemas/auth.py`:

```python
from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True
```

- [ ] **Step 3: 创建安全工具**

`app/services/security.py`:

```python
from datetime import datetime, timedelta, timezone
from typing import Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
```

- [ ] **Step 4: 创建认证服务**

`app/services/auth_service.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.security import verify_password, get_password_hash


async def authenticate_user(session: AsyncSession, username: str, password: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def seed_users(session: AsyncSession) -> None:
    result = await session.execute(select(User).limit(1))
    if result.scalar_one_or_none() is not None:
        return
    users = [
        User(username="editor", password_hash=get_password_hash("editor123"), role="editor"),
        User(username="reviewer", password_hash=get_password_hash("reviewer123"), role="reviewer"),
    ]
    session.add_all(users)
    await session.commit()
```

- [ ] **Step 5: 创建认证路由**

`app/api/auth.py`:

```python
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.auth import Token, UserOut
from app.services.auth_service import authenticate_user
from app.services.security import create_access_token, decode_token
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> UserOut:
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证失败")
    from sqlalchemy import select
    from app.models.user import User
    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    return UserOut.model_validate(user)


@router.get("/me", response_model=UserOut)
async def me(current_user: UserOut = Depends(get_current_user)):
    return current_user
```

- [ ] **Step 6: 注册路由与启动时种子**

`app/main.py`:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.generator import router as generator_router
from app.api.auth import router as auth_router
from app.database import engine, Base, AsyncSessionLocal
from app.services.auth_service import seed_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_users(session)
    yield


app = FastAPI(title="AI 运营物料智能生成助手", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api")
app.include_router(generator_router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 7: 验证后端启动**

```bash
cd ai-material-generator/backend
.\venv\Scripts\activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Expected: `GET http://127.0.0.1:8000/api/health` 返回 200。

- [ ] **Step 8: Commit**

```bash
git add app/models/user.py app/schemas/auth.py app/services/security.py app/services/auth_service.py app/api/auth.py app/main.py
git commit -m "feat: add JWT auth and seed users"
```

---

## Task 3: 资产模型与 CRUD API

**Files:**
- Create: `ai-material-generator/backend/app/models/material_asset.py`
- Create: `ai-material-generator/backend/app/schemas/material.py`
- Create: `ai-material-generator/backend/app/services/material_service.py`
- Create: `ai-material-generator/backend/app/api/materials.py`
- Modify: `ai-material-generator/backend/app/main.py`

- [ ] **Step 1: 创建 MaterialAsset 模型**

`app/models/material_asset.py`:

```python
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class MaterialAsset(Base):
    __tablename__ = "material_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    material_type: Mapped[str] = mapped_column(String(64), nullable=False)
    audience: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    source_title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    analysis: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner: Mapped["User"] = relationship("User", back_populates="assets")
```

- [ ] **Step 2: 更新 User 关系**

`app/models/user.py` 添加：

```python
from sqlalchemy.orm import relationship

class User(Base):
    ...
    assets: Mapped[list["MaterialAsset"]] = relationship("MaterialAsset", back_populates="owner")
```

- [ ] **Step 3: 创建 schema**

`app/schemas/material.py`:

```python
from datetime import datetime
from pydantic import BaseModel, Field


class MaterialCreate(BaseModel):
    title: str
    content: str
    material_type: str
    audience: str
    source_title: str = ""
    analysis: str = "{}"


class MaterialUpdate(BaseModel):
    title: str
    content: str
    material_type: str
    audience: str


class MaterialOut(BaseModel):
    id: int
    owner_id: int
    title: str
    content: str
    material_type: str
    audience: str
    status: str
    source_title: str
    analysis: str
    review_comment: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReviewAction(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    comment: str = ""
```

- [ ] **Step 4: 创建服务层**

`app/services/material_service.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.material_asset import MaterialAsset
from app.schemas.material import MaterialCreate, MaterialUpdate, ReviewAction


async def create_material(session: AsyncSession, owner_id: int, data: MaterialCreate) -> MaterialAsset:
    asset = MaterialAsset(owner_id=owner_id, **data.model_dump())
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return asset


async def get_material(session: AsyncSession, material_id: int) -> MaterialAsset | None:
    return await session.get(MaterialAsset, material_id)


async def list_materials(session: AsyncSession, owner_id: int | None = None, status: str | None = None) -> list[MaterialAsset]:
    stmt = select(MaterialAsset)
    if owner_id is not None:
        stmt = stmt.where(MaterialAsset.owner_id == owner_id)
    if status:
        stmt = stmt.where(MaterialAsset.status == status)
    stmt = stmt.order_by(MaterialAsset.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_material(session: AsyncSession, asset: MaterialAsset, data: MaterialUpdate) -> MaterialAsset:
    for field in ["title", "content", "material_type", "audience"]:
        setattr(asset, field, getattr(data, field))
    if asset.status == "approved":
        asset.status = "draft"
    await session.commit()
    await session.refresh(asset)
    return asset


async def delete_material(session: AsyncSession, asset: MaterialAsset) -> None:
    await session.delete(asset)
    await session.commit()


async def submit_for_review(session: AsyncSession, asset: MaterialAsset) -> MaterialAsset:
    if asset.status not in ("draft", "rejected"):
        raise ValueError("只能提交草稿或被驳回的资产")
    asset.status = "pending_review"
    asset.review_comment = None
    await session.commit()
    await session.refresh(asset)
    return asset


async def review_material(session: AsyncSession, asset: MaterialAsset, action: ReviewAction) -> MaterialAsset:
    if asset.status != "pending_review":
        raise ValueError("只能审核待审核状态的资产")
    if action.action == "approve":
        asset.status = "approved"
        asset.review_comment = action.comment or None
    else:
        asset.status = "rejected"
        asset.review_comment = action.comment or None
    await session.commit()
    await session.refresh(asset)
    return asset
```

- [ ] **Step 5: 创建路由**

`app/api/materials.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.material_asset import MaterialAsset
from app.schemas.auth import UserOut
from app.schemas.material import MaterialCreate, MaterialOut, MaterialUpdate, ReviewAction
from app.api.auth import get_current_user
from app.services import material_service as svc

router = APIRouter(prefix="/materials", tags=["materials"])


def require_editor(user: UserOut) -> None:
    if user.role != "editor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要 editor 角色")


def require_reviewer(user: UserOut) -> None:
    if user.role != "reviewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要 reviewer 角色")


def require_owner(asset: MaterialAsset, user: UserOut) -> None:
    if asset.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该资产")


@router.get("", response_model=list[MaterialOut])
async def list_materials(
    status: str | None = Query(None),
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    owner_id = user.id if user.role == "editor" else None
    return await svc.list_materials(db, owner_id=owner_id, status=status)


@router.get("/pending", response_model=list[MaterialOut])
async def pending_list(user: UserOut = Depends(require_reviewer), db: AsyncSession = Depends(get_db)):
    return await svc.list_materials(db, status="pending_review")


@router.get("/approved", response_model=list[MaterialOut])
async def approved_list(user: UserOut = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await svc.list_materials(db, status="approved")


@router.get("/{material_id}", response_model=MaterialOut)
async def get_material(
    material_id: int,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await svc.get_material(db, material_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    if user.role == "editor":
        require_owner(asset, user)
    return asset


@router.post("", response_model=MaterialOut)
async def create_material(
    data: MaterialCreate,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_editor(user)
    return await svc.create_material(db, user.id, data)


@router.put("/{material_id}", response_model=MaterialOut)
async def update_material(
    material_id: int,
    data: MaterialUpdate,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_editor(user)
    asset = await svc.get_material(db, material_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    require_owner(asset, user)
    if asset.status == "pending_review":
        raise HTTPException(status_code=400, detail="待审核资产不可编辑")
    return await svc.update_material(db, asset, data)


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: int,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_editor(user)
    asset = await svc.get_material(db, material_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    require_owner(asset, user)
    if asset.status not in ("draft", "rejected"):
        raise HTTPException(status_code=400, detail="只能删除草稿或被驳回资产")
    await svc.delete_material(db, asset)


@router.post("/{material_id}/submit", response_model=MaterialOut)
async def submit_material(
    material_id: int,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_editor(user)
    asset = await svc.get_material(db, material_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    require_owner(asset, user)
    try:
        return await svc.submit_for_review(db, asset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{material_id}/reviews", response_model=MaterialOut)
async def review_material(
    material_id: int,
    action: ReviewAction,
    user: UserOut = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
):
    asset = await svc.get_material(db, material_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    try:
        return await svc.review_material(db, asset, action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 6: 注册 materials 路由**

`app/main.py` 添加：

```python
from app.api.materials import router as materials_router
app.include_router(materials_router, prefix="/api")
```

- [ ] **Step 7: 验证 API 可用**

启动后端，用临时脚本验证：

```python
import httpx
r = httpx.post("http://127.0.0.1:8000/api/auth/login", data={"username":"editor","password":"editor123"})
print(r.status_code, r.json())
token = r.json()["access_token"]
r2 = httpx.get("http://127.0.0.1:8000/api/materials", headers={"Authorization": f"Bearer {token}"})
print(r2.status_code, r2.json())
```

Expected: login 200，materials 返回空列表 200。

- [ ] **Step 8: Commit**

```bash
git add app/models/material_asset.py app/schemas/material.py app/services/material_service.py app/api/materials.py app/main.py
git commit -m "feat: add material asset CRUD and review endpoints"
```

---

## Task 4: 下载 API 与生成接口保存资产

**Files:**
- Modify: `ai-material-generator/backend/app/api/materials.py`
- Modify: `ai-material-generator/backend/app/api/generator.py`
- Create: `ai-material-generator/backend/app/schemas/generation.py`

- [ ] **Step 1: 添加下载端点**

在 `app/api/materials.py` 追加：

```python
from fastapi.responses import PlainTextResponse


@router.get("/{material_id}/download")
async def download_material(
    material_id: int,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await svc.get_material(db, material_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    if user.role == "editor":
        require_owner(asset, user)
    if asset.status != "approved":
        raise HTTPException(status_code=400, detail="仅已审核通过的资产可下载")
    return PlainTextResponse(
        content=asset.content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=material_{asset.id}.md"},
    )
```

- [ ] **Step 2: 创建 generation schema**

`app/schemas/generation.py`:

```python
from pydantic import BaseModel


class SaveFromGenerationRequest(BaseModel):
    title: str
    content: str
    material_type: str
    audience: str
    source_title: str = ""
    analysis: str = "{}"
```

- [ ] **Step 3: 扩展 generator 路由保存资产**

`app/api/generator.py` 修改：

```python
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.auth import UserOut
from app.schemas.generation import SaveFromGenerationRequest
from app.schemas.material import MaterialOut
from app.api.auth import get_current_user
from app.services import material_service as material_svc
...

@router.post("/materials/from-generation", response_model=MaterialOut)
async def save_from_generation(
    data: SaveFromGenerationRequest,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "editor":
        raise HTTPException(status_code=403, detail="需要 editor 角色")
    from app.schemas.material import MaterialCreate
    return await material_svc.create_material(db, user.id, MaterialCreate(**data.model_dump()))
```

- [ ] **Step 4: 验证下载端点**

创建 approved 资产后访问 `/api/materials/{id}/download`，Expected: 200，content-type text/markdown。

- [ ] **Step 5: Commit**

```bash
git add app/api/materials.py app/api/generator.py app/schemas/generation.py
git commit -m "feat: add material download and save-from-generation endpoints"
```

---

## Task 5: 后端测试

**Files:**
- Create: `ai-material-generator/backend/tests/conftest.py`
- Create: `ai-material-generator/backend/tests/test_auth.py`
- Create: `ai-material-generator/backend/tests/test_materials.py`
- Create: `ai-material-generator/backend/tests/test_download.py`

- [ ] **Step 1: 创建测试 fixtures**

`tests/conftest.py`:

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.database import Base, get_db
from app.services.auth_service import seed_users

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await seed_users(session)
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def editor_token(client):
    r = await client.post("/api/auth/login", data={"username": "editor", "password": "editor123"})
    return r.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def reviewer_token(client):
    r = await client.post("/api/auth/login", data={"username": "reviewer", "password": "reviewer123"})
    return r.json()["access_token"]
```

- [ ] **Step 2: 编写认证测试**

`tests/test_auth.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_login_success(client):
    r = await client.post("/api/auth/login", data={"username": "editor", "password": "editor123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["role"] == "editor"


@pytest.mark.asyncio
async def test_login_failure(client):
    r = await client.post("/api/auth/login", data={"username": "editor", "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_success(client, editor_token):
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {editor_token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "editor"
```

- [ ] **Step 3: 编写资产测试**

`tests/test_materials.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_create_material(client, editor_token):
    r = await client.post(
        "/api/materials",
        json={"title": "t", "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_editor_cannot_see_others_materials(client, editor_token, reviewer_token):
    r = await client.post(
        "/api/materials",
        json={"title": "t", "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 200
    editor_list = await client.get("/api/materials", headers={"Authorization": f"Bearer {editor_token}"})
    assert len(editor_list.json()) == 1
    reviewer_list = await client.get("/api/materials", headers={"Authorization": f"Bearer {reviewer_token}"})
    assert len(reviewer_list.json()) == 1


@pytest.mark.asyncio
async def test_submit_and_approve_flow(client, editor_token, reviewer_token):
    r = await client.post(
        "/api/materials",
        json={"title": "t", "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    mid = r.json()["id"]
    r = await client.post(f"/api/materials/{mid}/submit", headers={"Authorization": f"Bearer {editor_token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "pending_review"
    r = await client.post(
        f"/api/materials/{mid}/reviews",
        json={"action": "approve", "comment": "ok"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_approved_edit_fallback_to_draft(client, editor_token, reviewer_token):
    r = await client.post(
        "/api/materials",
        json={"title": "t", "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    mid = r.json()["id"]
    await client.post(f"/api/materials/{mid}/submit", headers={"Authorization": f"Bearer {editor_token}"})
    await client.post(
        f"/api/materials/{mid}/reviews",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    r = await client.put(
        f"/api/materials/{mid}",
        json={"title": "t2", "content": "c2", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_pending_material_cannot_be_edited(client, editor_token):
    r = await client.post(
        "/api/materials",
        json={"title": "t", "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    mid = r.json()["id"]
    await client.post(f"/api/materials/{mid}/submit", headers={"Authorization": f"Bearer {editor_token}"})
    r = await client.put(
        f"/api/materials/{mid}",
        json={"title": "t2", "content": "c2", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 400
```

- [ ] **Step 4: 编写下载测试**

`tests/test_download.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_only_approved_can_download(client, editor_token):
    r = await client.post(
        "/api/materials",
        json={"title": "t", "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    mid = r.json()["id"]
    r = await client.get(f"/api/materials/{mid}/download", headers={"Authorization": f"Bearer {editor_token}"})
    assert r.status_code == 400
```

- [ ] **Step 5: 运行测试**

```bash
cd ai-material-generator/backend
pytest -q
```

Expected: 全部通过。

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_auth.py tests/test_materials.py tests/test_download.py
git commit -m "test: add auth, material workflow and download tests"
```

---

## Task 6: 前端依赖与路由/Pinia

**Files:**
- Modify: `ai-material-generator/frontend/package.json`
- Modify: `ai-material-generator/frontend/src/main.ts`
- Create: `ai-material-generator/frontend/src/router/index.ts`
- Create: `ai-material-generator/frontend/src/stores/auth.ts`
- Create: `ai-material-generator/frontend/src/api/auth.ts`
- Create: `ai-material-generator/frontend/src/api/materials.ts`
- Modify: `ai-material-generator/frontend/src/App.vue`

- [ ] **Step 1: 安装依赖**

```bash
cd ai-material-generator/frontend
npm install vue-router@4.5.0 pinia@3.0.1
```

- [ ] **Step 2: 更新 package.json**

Expected: `package.json` 中 dependencies 新增 `vue-router` 与 `pinia`。

- [ ] **Step 3: 创建 auth store**

`src/stores/auth.ts`:

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const role = ref<string | null>(localStorage.getItem('role'))

  const isLoggedIn = computed(() => !!token.value)
  const isEditor = computed(() => role.value === 'editor')
  const isReviewer = computed(() => role.value === 'reviewer')

  function setAuth(newToken: string, newRole: string) {
    token.value = newToken
    role.value = newRole
    localStorage.setItem('token', newToken)
    localStorage.setItem('role', newRole)
  }

  function logout() {
    token.value = null
    role.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('role')
  }

  return { token, role, isLoggedIn, isEditor, isReviewer, setAuth, logout }
})
```

- [ ] **Step 4: 创建 API client 扩展**

`src/api/auth.ts`:

```typescript
import client from './client'

export interface LoginPayload {
  username: string
  password: string
}

export function login(payload: LoginPayload) {
  const params = new URLSearchParams()
  params.append('username', payload.username)
  params.append('password', payload.password)
  return client.post('/auth/login', params, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
}

export function me() {
  return client.get('/auth/me')
}
```

`src/api/materials.ts`:

```typescript
import client from './client'

export interface Material {
  id: number
  title: string
  content: string
  material_type: string
  audience: string
  status: string
  review_comment: string | null
  created_at: string
  updated_at: string
}

export function listMaterials(status?: string) {
  return client.get('/materials', { params: status ? { status } : {} })
}

export function getMaterial(id: number) {
  return client.get(`/materials/${id}`)
}

export function createMaterial(data: Partial<Material>) {
  return client.post('/materials', data)
}

export function updateMaterial(id: number, data: Partial<Material>) {
  return client.put(`/materials/${id}`, data)
}

export function submitMaterial(id: number) {
  return client.post(`/materials/${id}/submit`)
}

export function reviewMaterial(id: number, action: 'approve' | 'reject', comment: string = '') {
  return client.post(`/materials/${id}/reviews`, { action, comment })
}

export function listPending() {
  return client.get('/materials/pending')
}

export function listApproved() {
  return client.get('/materials/approved')
}

export function downloadMaterial(id: number) {
  return client.get(`/materials/${id}/download`, { responseType: 'blob' })
}

export function saveFromGeneration(data: {
  title: string
  content: string
  material_type: string
  audience: string
  source_title: string
  analysis: string
}) {
  return client.post('/materials/from-generation', data)
}
```

- [ ] **Step 5: 更新 client 注入 token**

`src/api/client.ts` 当前为：

```typescript
import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

export default client
```

更新为读取 store 中的 token：

```typescript
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const client = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const auth = useAuthStore()
      auth.logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
```

- [ ] **Step 6: 创建路由**

`src/router/index.ts`:

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'
import GeneratorView from '@/views/GeneratorView.vue'
import MaterialListView from '@/views/MaterialListView.vue'
import MaterialEditorView from '@/views/MaterialEditorView.vue'
import ReviewView from '@/views/ReviewView.vue'
import ApprovedListView from '@/views/ApprovedListView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/', component: GeneratorView, meta: { role: 'editor' } },
    { path: '/materials', component: MaterialListView },
    { path: '/materials/:id/edit', component: MaterialEditorView, meta: { role: 'editor' } },
    { path: '/review', component: ReviewView, meta: { role: 'reviewer' } },
    { path: '/approved', component: ApprovedListView },
  ],
})

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    return next('/login')
  }
  if (to.meta.role === 'editor' && !auth.isEditor) {
    return next('/login')
  }
  if (to.meta.role === 'reviewer' && !auth.isReviewer) {
    return next('/login')
  }
  next()
})

export default router
```

- [ ] **Step 7: 更新 main.ts**

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './styles/index.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
app.use(ElementPlus)
app.mount('#app')
```

- [ ] **Step 8: 更新 App.vue**

`src/App.vue`:

```vue
<template>
  <router-view />
</template>
```

- [ ] **Step 9: 创建占位视图**

创建空文件以保证 TypeScript 编译通过：
- `src/views/LoginView.vue`
- `src/views/MaterialListView.vue`
- `src/views/MaterialEditorView.vue`
- `src/views/ReviewView.vue`
- `src/views/ApprovedListView.vue`

每个文件初始内容：

```vue
<template>
  <div>placeholder</div>
</template>
```

- [ ] **Step 10: Commit**

```bash
git add package.json package-lock.json src/main.ts src/router src/stores src/api/auth.ts src/api/materials.ts src/App.vue src/views/LoginView.vue src/views/MaterialListView.vue src/views/MaterialEditorView.vue src/views/ReviewView.vue src/views/ApprovedListView.vue
git commit -m "feat: add vue-router, pinia and auth api layer"
```

---

## Task 7: 登录页

**Files:**
- Modify: `ai-material-generator/frontend/src/views/LoginView.vue`

- [ ] **Step 1: 实现登录 UI**

```vue
<template>
  <div class="login-page">
    <el-card class="login-card" title="AI 运营物料智能生成助手">
      <h2>登录</h2>
      <el-form :model="form" label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="editor 或 reviewer" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="editor123 / reviewer123" />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading">登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { login } from '@/api/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function handleLogin() {
  loading.value = true
  try {
    const res = await login(form)
    const { access_token, role } = res.data
    auth.setAuth(access_token, role)
    ElMessage.success('登录成功')
    if (role === 'reviewer') {
      router.push('/review')
    } else {
      router.push('/')
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
}
.login-card {
  width: 360px;
}
</style>
```

- [ ] **Step 2: 构建验证**

```bash
cd ai-material-generator/frontend
npm run build
```

Expected: 构建通过。

- [ ] **Step 3: Commit**

```bash
git add src/views/LoginView.vue
git commit -m "feat: add login view"
```

---

## Task 8: 资产列表页

**Files:**
- Modify: `ai-material-generator/frontend/src/views/MaterialListView.vue`
- Modify: `ai-material-generator/frontend/src/App.vue`（可选，添加导航）

- [ ] **Step 1: 实现资产列表**

```vue
<template>
  <div class="page">
    <el-page-header title="资产列表" @back="$router.back" />
    <el-table :data="materials" style="margin-top: 20px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="material_type" label="类型" width="120" />
      <el-table-column prop="audience" label="受众" width="120" />
      <el-table-column prop="status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button v-if="canEdit(row)" size="small" @click="$router.push(`/materials/${row.id}/edit`)">编辑</el-button>
          <el-button v-if="canSubmit(row)" size="small" type="primary" @click="submit(row.id)">提交审核</el-button>
          <el-button v-if="canDelete(row)" size="small" type="danger" @click="remove(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listMaterials, submitMaterial, deleteMaterial } from '@/api/materials'
import type { Material } from '@/api/materials'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const materials = ref<Material[]>([])

function statusType(status: string) {
  const map: Record<string, string> = { draft: 'info', pending_review: 'warning', approved: 'success', rejected: 'danger' }
  return map[status] || 'info'
}
function statusLabel(status: string) {
  const map: Record<string, string> = { draft: '草稿', pending_review: '待审核', approved: '已通过', rejected: '已驳回' }
  return map[status] || status
}
function canEdit(row: Material) {
  return auth.isEditor && row.status !== 'pending_review'
}
function canSubmit(row: Material) {
  return auth.isEditor && (row.status === 'draft' || row.status === 'rejected')
}
function canDelete(row: Material) {
  return auth.isEditor && (row.status === 'draft' || row.status === 'rejected')
}

async function load() {
  const res = await listMaterials()
  materials.value = res.data
}
async function submit(id: number) {
  await submitMaterial(id)
  ElMessage.success('已提交审核')
  load()
}
async function remove(id: number) {
  await ElMessageBox.confirm('确认删除？', '提示', { type: 'warning' })
  await deleteMaterial(id)
  ElMessage.success('已删除')
  load()
}
onMounted(load)
</script>

<style scoped>
.page { padding: 20px; }
</style>
```

- [ ] **Step 2: 构建验证**

```bash
npm run build
```

Expected: 构建通过。

- [ ] **Step 3: Commit**

```bash
git add src/views/MaterialListView.vue
git commit -m "feat: add material list view"
```

---

## Task 9: 资产编辑器页

**Files:**
- Modify: `ai-material-generator/frontend/src/views/MaterialEditorView.vue`

- [ ] **Step 1: 实现编辑器 UI**

```vue
<template>
  <div class="page">
    <el-page-header title="编辑资产" @back="$router.push('/materials')" />
    <el-form :model="form" label-position="top" style="margin-top: 20px">
      <el-form-item label="标题">
        <el-input v-model="form.title" />
      </el-form-item>
      <el-form-item label="类型">
        <el-input v-model="form.material_type" disabled />
      </el-form-item>
      <el-form-item label="受众">
        <el-input v-model="form.audience" disabled />
      </el-form-item>
      <el-form-item label="内容 (Markdown)">
        <el-input v-model="form.content" type="textarea" :rows="20" />
      </el-form-item>
      <el-button type="primary" @click="save">保存</el-button>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMaterial, updateMaterial } from '@/api/materials'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const form = reactive({ title: '', content: '', material_type: '', audience: '' })

async function load() {
  const res = await getMaterial(id)
  Object.assign(form, res.data)
}
async function save() {
  await updateMaterial(id, { title: form.title, content: form.content, material_type: form.material_type, audience: form.audience })
  ElMessage.success('保存成功')
  router.push('/materials')
}
onMounted(load)
</script>

<style scoped>
.page { padding: 20px; }
</style>
```

- [ ] **Step 2: 构建验证**

```bash
npm run build
```

- [ ] **Step 3: Commit**

```bash
git add src/views/MaterialEditorView.vue
git commit -m "feat: add material editor view"
```

---

## Task 10: 审核工作台

**Files:**
- Modify: `ai-material-generator/frontend/src/views/ReviewView.vue`

- [ ] **Step 1: 实现审核 UI**

```vue
<template>
  <div class="page">
    <h2>审核工作台</h2>
    <el-table :data="materials" style="margin-top: 20px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="material_type" label="类型" />
      <el-table-column prop="audience" label="受众" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" type="success" @click="approve(row.id)">通过</el-button>
          <el-button size="small" type="danger" @click="reject(row.id)">驳回</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dialogVisible" title="审核意见">
      <el-input v-model="comment" type="textarea" :rows="4" placeholder="选填" />
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmReview">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listPending, reviewMaterial } from '@/api/materials'
import type { Material } from '@/api/materials'

const materials = ref<Material[]>([])
const dialogVisible = ref(false)
const comment = ref('')
const pendingAction = ref<{ id: number; action: 'approve' | 'reject' } | null>(null)

async function load() {
  const res = await listPending()
  materials.value = res.data
}
function approve(id: number) {
  pendingAction.value = { id, action: 'approve' }
  dialogVisible.value = true
}
function reject(id: number) {
  pendingAction.value = { id, action: 'reject' }
  dialogVisible.value = true
}
async function confirmReview() {
  if (!pendingAction.value) return
  await reviewMaterial(pendingAction.value.id, pendingAction.value.action, comment.value)
  ElMessage.success('审核完成')
  dialogVisible.value = false
  comment.value = ''
  load()
}
onMounted(load)
</script>

<style scoped>
.page { padding: 20px; }
</style>
```

- [ ] **Step 2: 构建验证**

```bash
npm run build
```

- [ ] **Step 3: Commit**

```bash
git add src/views/ReviewView.vue
git commit -m "feat: add review workbench view"
```

---

## Task 11: 已审核资产列表与下载

**Files:**
- Modify: `ai-material-generator/frontend/src/views/ApprovedListView.vue`

- [ ] **Step 1: 实现已审核列表**

```vue
<template>
  <div class="page">
    <h2>已审核资产</h2>
    <el-table :data="materials" style="margin-top: 20px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="material_type" label="类型" />
      <el-table-column prop="audience" label="受众" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="download(row)">下载 Markdown</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listApproved, downloadMaterial } from '@/api/materials'
import type { Material } from '@/api/materials'

const materials = ref<Material[]>([])
async function load() {
  const res = await listApproved()
  materials.value = res.data
}
async function download(row: Material) {
  const res = await downloadMaterial(row.id)
  const blob = new Blob([res.data], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${row.title}.md`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('开始下载')
}
onMounted(load)
</script>

<style scoped>
.page { padding: 20px; }
</style>
```

- [ ] **Step 2: 构建验证**

```bash
npm run build
```

- [ ] **Step 3: Commit**

```bash
git add src/views/ApprovedListView.vue
git commit -m "feat: add approved materials list and download"
```

---

## Task 12: GeneratorView 集成保存资产

**Files:**
- Modify: `ai-material-generator/frontend/src/views/GeneratorView.vue`
- Modify: `ai-material-generator/frontend/src/App.vue`

- [ ] **Step 1: 在 GeneratorView 添加"保存为草稿"按钮**

在生成结果展示区域，每个卡片添加：

```vue
<el-button size="small" type="primary" @click="saveAsDraft(item)">保存为草稿</el-button>
```

`saveAsDraft` 方法：

```typescript
import { saveFromGeneration } from '@/api/materials'
import { ElMessage } from 'element-plus'

async function saveAsDraft(item: { title: string; content: string }) {
  if (!analysis.value) return
  await saveFromGeneration({
    title: item.title,
    content: item.content,
    material_type: currentMaterialType.value,
    audience: currentAudience.value,
    source_title: title.value,
    analysis: JSON.stringify(analysis.value),
  })
  ElMessage.success('已保存为草稿')
}
```

- [ ] **Step 2: 在 App.vue 添加顶部导航**

```vue
<template>
  <el-container direction="vertical" style="height: 100vh">
    <el-header v-if="auth.isLoggedIn" style="display: flex; align-items: center; gap: 16px; background: #fff; border-bottom: 1px solid #e4e7ed;">
      <router-link to="/">生成助手</router-link>
      <router-link v-if="auth.isEditor" to="/materials">我的资产</router-link>
      <router-link v-if="auth.isReviewer" to="/review">审核</router-link>
      <router-link to="/approved">已审核</router-link>
      <div style="flex: 1"></div>
      <span>{{ auth.role }}</span>
      <el-button size="small" @click="logout">退出</el-button>
    </el-header>
    <router-view />
  </el-container>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
function logout() {
  auth.logout()
  router.push('/login')
}
</script>
```

- [ ] **Step 3: 构建验证**

```bash
npm run build
```

- [ ] **Step 4: Commit**

```bash
git add src/views/GeneratorView.vue src/App.vue
git commit -m "feat: integrate save-to-draft into generator view and add nav"
```

---

## Task 13: Vite 代理配置

**Files:**
- Modify: `ai-material-generator/frontend/vite.config.ts`

- [ ] **Step 1: 添加代理**

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
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

- [ ] **Step 2: Commit**

```bash
git add vite.config.ts
git commit -m "chore: add vite dev proxy for backend api"
```

---

## Task 14: 端到端联调验证

- [ ] **Step 1: 启动后端**

```bash
cd ai-material-generator/backend
.\venv\Scripts\activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- [ ] **Step 2: 启动前端**

```bash
cd ai-material-generator/frontend
npm run dev
```

- [ ] **Step 3: 人工走查流程**

1. 访问 `http://localhost:5173/login`，用 editor 登录。
2. 进入生成页，输入标题和正文，点击解析/生成。
3. 选择某个结果点击"保存为草稿"。
4. 进入"我的资产"，点击"提交审核"。
5. 退出登录，用 reviewer 登录。
6. 进入"审核"，点击"通过"。
7. 进入"已审核"，点击"下载 Markdown"，确认下载成功。

- [ ] **Step 4: Commit 任何修复**

---

## Task 15: README 更新与最终验证

**Files:**
- Modify: `ai-material-generator/README.md`

- [ ] **Step 1: 在 README 中补充编辑审核流程说明**

新增章节：

```markdown
## 编辑与审核流程

1. editor 登录后生成物料，点击"保存为草稿"。
2. 在"我的资产"页面编辑内容，确认后点击"提交审核"。
3. reviewer 登录后进入"审核"页面，对资产进行"通过"或"驳回"。
4. 已通过资产在"已审核"页面可下载 Markdown。
5. 已 approved 资产被再次编辑后状态自动回落为 draft，需重新审核。

内置账号：
- editor / editor123
- reviewer / reviewer123
```

- [ ] **Step 2: 全量后端测试**

```bash
cd ai-material-generator/backend
pytest -q
```

Expected: 全部通过。

- [ ] **Step 3: 前端构建**

```bash
cd ai-material-generator/frontend
npm run build
```

Expected: 构建通过。

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update README with edit and review workflow"
```

---

## 完成

使用 `superpowers:finishing-a-development-branch` skill 完成本次开发分支。
