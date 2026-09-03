# 用户管理与 RBAC 权限控制 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Data Analysis Agent 后端增加用户注册/登录、JWT 认证、OAuth 第三方登录（GitHub + 微信）和角色级 RBAC 权限控制。

**Architecture:** 新增 `app/auth/` 和 `app/users/` 两个模块。`auth/` 负责 JWT 签发验证、密码哈希、OAuth 流程和权限校验依赖注入；`users/` 负责用户数据模型和业务逻辑。通过 FastAPI `Depends()` 机制将认证和权限校验注入到所有受保护的接口。

**Tech Stack:** FastAPI, SQLAlchemy 2.0 Async, python-jose, passlib[bcrypt], Authlib, httpx

**设计文档:** `docs/superpowers/specs/2026-09-03-user-auth-rbac-design.md`

---

### Task 1: 安装依赖与配置

**Files:**
- Modify: `requirements.txt`
- Modify: `app/config.py`
- Modify: `.env`

- [ ] **Step 1: 添加新依赖到 requirements.txt**

在 `requirements.txt` 末尾追加：

```
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
authlib==1.3.2
httpx==0.27.2
```

- [ ] **Step 2: 安装依赖**

Run: `pip install -r requirements.txt`

- [ ] **Step 3: 更新 config.py**

在 `Settings` 类中追加以下字段：

```python
# JWT
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# GitHub OAuth
GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")

# WeChat OAuth
WECHAT_APP_ID: str = os.getenv("WECHAT_APP_ID", "")
WECHAT_APP_SECRET: str = os.getenv("WECHAT_APP_SECRET", "")
```

- [ ] **Step 4: 更新 .env**

在 `.env` 末尾追加：

```
SECRET_KEY=dev-secret-change-me
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
WECHAT_APP_ID=
WECHAT_APP_SECRET=
```

- [ ] **Step 5: 提交**

```bash
git add requirements.txt app/config.py .env
git commit -m "feat: add auth dependencies and config"
```

---

### Task 2: 数据模型

**Files:**
- Create: `app/users/__init__.py`
- Create: `app/users/models.py`

- [ ] **Step 1: 创建 users 模块**

创建空文件 `app/users/__init__.py`。

- [ ] **Step 2: 创建数据模型 `app/users/models.py`**

```python
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(200), default="")
    permissions: Mapped[str] = mapped_column(Text, default="[]")  # JSON list

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    role: Mapped["Role"] = relationship(back_populates="users", lazy="selectin")
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_login: Mapped[str | None] = mapped_column(String(100), nullable=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="oauth_accounts")
```

- [ ] **Step 3: 确保模型被导入**

在 `app/main.py` 的 `from app.database import engine, Base` 行之后追加：

```python
import app.users.models  # noqa: F401 — 确保模型注册到 Base.metadata
```

- [ ] **Step 4: 提交**

```bash
git add app/users/ app/main.py
git commit -m "feat: add User, Role, OAuthAccount data models"
```

---

### Task 3: 认证服务（JWT + 密码）

**Files:**
- Create: `app/auth/__init__.py`
- Create: `app/auth/service.py`

- [ ] **Step 1: 创建 auth 模块**

创建空文件 `app/auth/__init__.py`。

- [ ] **Step 2: 创建认证服务 `app/auth/service.py`**

```python
import json
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """解码 JWT，失败抛出 JWTError。"""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def parse_role_permissions(permissions_json: str) -> list[str]:
    return json.loads(permissions_json)
```

- [ ] **Step 3: 提交**

```bash
git add app/auth/
git commit -m "feat: add JWT and password auth service"
```

---

### Task 4: Pydantic Schemas

**Files:**
- Create: `app/auth/schemas.py`
- Create: `app/users/schemas.py`

- [ ] **Step 1: 创建认证 schemas `app/auth/schemas.py`**

```python
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    email: str | None = None
    phone: str | None = None


class LoginRequest(BaseModel):
    username_or_phone: str
    password: str


class SMSLoginRequest(BaseModel):
    phone: str
    code: str


class SMSSendRequest(BaseModel):
    phone: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
```

- [ ] **Step 2: 创建用户 schemas `app/users/schemas.py`**

```python
from datetime import datetime
from pydantic import BaseModel


class UserOut(BaseModel):
    id: int
    username: str
    email: str | None
    phone: str | None
    avatar_url: str | None
    is_active: bool
    role_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleOut(BaseModel):
    id: int
    name: str
    description: str
    permissions: list[str]

    model_config = {"from_attributes": True}


class UpdateRoleRequest(BaseModel):
    role_id: int
```

- [ ] **Step 3: 提交**

```bash
git add app/auth/schemas.py app/users/schemas.py
git commit -m "feat: add auth and user pydantic schemas"
```

---

### Task 5: 认证依赖注入

**Files:**
- Create: `app/auth/dependencies.py`

- [ ] **Step 1: 创建依赖注入 `app/auth/dependencies.py`**

```python
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.service import decode_token
from app.users.models import User

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT 中解析当前用户。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: int = payload.get("sub")
        token_type: str = payload.get("type")
        if user_id is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_role(*role_names: str):
    """角色权限校验依赖。"""
    async def _checker(current_user: User = Depends(get_current_user)):
        if current_user.role.name not in role_names and "*" not in _get_user_permissions(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要角色: {', '.join(role_names)}",
            )
        return current_user
    return _checker


def _get_user_permissions(user: User) -> list[str]:
    import json
    try:
        return json.loads(user.role.permissions)
    except (json.JSONDecodeError, AttributeError):
        return []
```

- [ ] **Step 2: 提交**

```bash
git add app/auth/dependencies.py
git commit -m "feat: add get_current_user and require_role dependencies"
```

---

### Task 6: 用户服务

**Files:**
- Create: `app/users/service.py`

- [ ] **Step 1: 创建用户服务 `app/users/service.py`**

```python
import json
import logging
import random
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import User, Role
from app.auth.service import hash_password

logger = logging.getLogger(__name__)

# 内存验证码存储（生产环境应替换为 Redis）
_sms_store: dict[str, str] = {}


async def get_role_by_name(db: AsyncSession, name: str) -> Role | None:
    result = await db.execute(select(Role).where(Role.name == name))
    return result.scalar_one_or_none()


async def register_user(
    db: AsyncSession,
    username: str,
    password: str,
    email: str | None = None,
    phone: str | None = None,
) -> User:
    """注册新用户，默认 viewer 角色。"""
    viewer_role = await get_role_by_name(db, "viewer")
    if viewer_role is None:
        raise ValueError("viewer 角色不存在，请先初始化角色数据")

    user = User(
        username=username,
        hashed_password=hash_password(password),
        email=email,
        phone=phone,
        role_id=viewer_role.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info(f"新用户注册: {username}")
    return user


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    result = await db.execute(select(User).where(User.phone == phone))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_all_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User))
    return list(result.scalars().all())


async def update_user_role(db: AsyncSession, user_id: int, role_id: int) -> User | None:
    user = await get_user_by_id(db, user_id)
    if user is None:
        return None
    user.role_id = role_id
    await db.commit()
    await db.refresh(user)
    return user


def generate_sms_code() -> str:
    return "".join(random.choices(string.digits, k=6))


def save_sms_code(phone: str, code: str) -> None:
    _sms_store[phone] = code
    logger.info(f"[SMS] 向 {phone} 发送验证码: {code}")


def verify_sms_code(phone: str, code: str) -> bool:
    stored = _sms_store.pop(phone, None)
    return stored == code


async def create_oauth_user(
    db: AsyncSession,
    provider: str,
    provider_user_id: str,
    provider_login: str | None,
    access_token: str,
) -> User:
    """第三方 OAuth 自动注册用户。"""
    viewer_role = await get_role_by_name(db, "viewer")
    random_username = f"{provider}_{provider_user_id[:8]}"
    user = User(
        username=random_username,
        role_id=viewer_role.id,
    )
    db.add(user)
    await db.flush()

    from app.users.models import OAuthAccount
    oauth = OAuthAccount(
        user_id=user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_login=provider_login,
        access_token=access_token,
    )
    db.add(oauth)
    await db.commit()
    await db.refresh(user)
    logger.info(f"OAuth 新用户: {provider}/{provider_login}")
    return user
```

- [ ] **Step 2: 提交**

```bash
git add app/users/service.py
git commit -m "feat: add user service with registration and SMS code"
```

---

### Task 7: OAuth 客户端

**Files:**
- Create: `app/auth/oauth.py`

- [ ] **Step 1: 创建 OAuth 配置 `app/auth/oauth.py`**

```python
from authlib.integrations.httpx_client import AsyncOAuth2Client
from app.config import settings


def get_github_client() -> AsyncOAuth2Client:
    return AsyncOAuth2Client(
        client_id=settings.GITHUB_CLIENT_ID,
        client_secret=settings.GITHUB_CLIENT_SECRET,
    )


GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USERINFO_URL = "https://api.github.com/user"


async def github_exchange_code(code: str) -> dict:
    """用授权码换取 GitHub access_token 和用户信息。"""
    async with get_github_client() as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        access_token = token_data["access_token"]

        userinfo_resp = await client.get(
            GITHUB_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        user_info = userinfo_resp.json()

    return {
        "provider": "github",
        "provider_user_id": str(user_info["id"]),
        "provider_login": user_info.get("login"),
        "avatar_url": user_info.get("avatar_url"),
        "access_token": access_token,
    }


WECHAT_AUTHORIZE_URL = "https://open.weixin.qq.com/connect/qrconnect"
WECHAT_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
WECHAT_USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"


async def wechat_exchange_code(code: str) -> dict:
    """用授权码换取微信 access_token 和用户信息。"""
    import httpx

    params = {
        "appid": settings.WECHAT_APP_ID,
        "secret": settings.WECHAT_APP_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        token_resp = await client.get(WECHAT_TOKEN_URL, params=params)
        token_data = token_resp.json()
        access_token = token_data["access_token"]
        openid = token_data["openid"]

        userinfo_resp = await client.get(
            WECHAT_USERINFO_URL,
            params={"access_token": access_token, "openid": openid},
        )
        user_info = userinfo_resp.json()

    return {
        "provider": "wechat",
        "provider_user_id": user_info["openid"],
        "provider_login": user_info.get("nickname"),
        "avatar_url": user_info.get("headimgurl"),
        "access_token": access_token,
    }


OAUTH_PROVIDERS = {
    "github": {
        "exchange": github_exchange_code,
        "authorize_url": GITHUB_AUTHORIZE_URL,
    },
    "wechat": {
        "exchange": wechat_exchange_code,
        "authorize_url": WECHAT_AUTHORIZE_URL,
    },
}
```

- [ ] **Step 2: 提交**

```bash
git add app/auth/oauth.py
git commit -m "feat: add GitHub and WeChat OAuth clients"
```

---

### Task 8: 认证 API 路由

**Files:**
- Create: `app/api/auth.py`

- [ ] **Step 1: 创建认证路由 `app/api/auth.py`**

```python
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.service import (
    verify_password, create_access_token, create_refresh_token, decode_token,
)
from app.auth.schemas import (
    RegisterRequest, LoginRequest, SMSLoginRequest, SMSSendRequest,
    TokenResponse, RefreshRequest,
)
from app.auth.oauth import OAUTH_PROVIDERS
from app.users.models import User, OAuthAccount
from app.users.service import (
    register_user, get_user_by_username, get_user_by_phone,
    get_user_by_id, generate_sms_code, save_sms_code, verify_sms_code,
    create_oauth_user,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户名密码注册。"""
    existing = await get_user_by_username(db, req.username)
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "用户名已存在")
    if req.phone:
        existing_phone = await get_user_by_phone(db, req.phone)
        if existing_phone:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "手机号已注册")
    try:
        user = await register_user(db, req.username, req.password, req.email, req.phone)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return {"id": user.id, "username": user.username}


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户名/手机号 + 密码登录。"""
    user = await get_user_by_username(db, req.username_or_phone)
    if user is None:
        user = await get_user_by_phone(db, req.username_or_phone)
    if user is None or not user.hashed_password:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已被禁用")
    return _tokens_for_user(user)


@router.post("/sms/send")
async def send_sms(req: SMSSendRequest):
    """发送短信验证码（模拟）。"""
    code = generate_sms_code()
    save_sms_code(req.phone, code)
    return {"message": "验证码已发送"}


@router.post("/login/sms", response_model=TokenResponse)
async def login_sms(req: SMSLoginRequest, db: AsyncSession = Depends(get_db)):
    """手机号 + 验证码登录。"""
    if not verify_sms_code(req.phone, req.code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "验证码错误或已过期")
    user = await get_user_by_phone(db, req.phone)
    if user is None:
        # 自动注册
        from app.users.service import get_role_by_name
        import random, string
        random_username = f"phone_{req.phone[-4:]}_{''.join(random.choices(string.digits, k=4))}"
        viewer_role = await get_role_by_name(db, "viewer")
        user = User(phone=req.phone, username=random_username, role_id=viewer_role.id)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已被禁用")
    return _tokens_for_user(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """刷新 access_token。"""
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "无效的 refresh_token")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "无效的 refresh_token")
    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已禁用")
    return _tokens_for_user(user)


@router.get("/oauth/{provider}/authorize")
async def oauth_authorize(provider: str):
    """获取第三方授权 URL。"""
    if provider not in OAUTH_PROVIDERS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不支持的登录方式: {provider}")
    authorize_url = OAUTH_PROVIDERS[provider]["authorize_url"]
    if provider == "github":
        from app.config import settings
        return {
            "authorize_url": (
                f"{authorize_url}?client_id={settings.GITHUB_CLIENT_ID}"
                f"&scope=user:email&redirect_uri=/api/auth/oauth/github/callback"
            )
        }
    elif provider == "wechat":
        from app.config import settings
        return {
            "authorize_url": (
                f"{authorize_url}?appid={settings.WECHAT_APP_ID}"
                f"&redirect_uri=/api/auth/oauth/wechat/callback&response_type=code&scope=snsapi_login"
            )
        }


@router.get("/oauth/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(provider: str, code: str, db: AsyncSession = Depends(get_db)):
    """第三方 OAuth 回调。"""
    if provider not in OAUTH_PROVIDERS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不支持的登录方式: {provider}")

    oauth_info = await OAUTH_PROVIDERS[provider]["exchange"](code)

    # 查找是否已绑定
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == oauth_info["provider_user_id"],
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        user = await get_user_by_id(db, existing.user_id)
        existing.access_token = oauth_info["access_token"]
        await db.commit()
    else:
        user = await create_oauth_user(
            db,
            provider=provider,
            provider_user_id=oauth_info["provider_user_id"],
            provider_login=oauth_info["provider_login"],
            access_token=oauth_info["access_token"],
        )
        if oauth_info.get("avatar_url"):
            user.avatar_url = oauth_info["avatar_url"]
            await db.commit()
            await db.refresh(user)

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已被禁用")
    return _tokens_for_user(user)


def _tokens_for_user(user) -> TokenResponse:
    token_data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )
```

- [ ] **Step 2: 提交**

```bash
git add app/api/auth.py
git commit -m "feat: add auth API routes (register, login, SMS, OAuth, refresh)"
```

---

### Task 9: 用户管理 API 路由

**Files:**
- Create: `app/users/router.py`

- [ ] **Step 1: 创建用户路由 `app/users/router.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user, require_role
from app.users.models import User
from app.users.schemas import UserOut, RoleOut, UpdateRoleRequest
from app.users.service import get_all_users, get_user_by_id, update_user_role

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return _user_to_out(current_user)


@router.get("/", response_model=list[UserOut])
async def list_users(
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """获取所有用户列表（仅 admin）。"""
    users = await get_all_users(db)
    return [_user_to_out(u) for u in users]


@router.put("/{user_id}/role", response_model=UserOut)
async def change_user_role(
    user_id: int,
    req: UpdateRoleRequest,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """修改用户角色（仅 admin）。"""
    user = await update_user_role(db, user_id, req.role_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    return _user_to_out(user)


def _user_to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        role_name=user.role.name if user.role else "",
        created_at=user.created_at,
    )
```

- [ ] **Step 2: 提交**

```bash
git add app/users/router.py
git commit -m "feat: add user management API routes"
```

---

### Task 10: 路由集成与 Agent 保护

**Files:**
- Modify: `app/api/router.py`
- Modify: `app/api/agent.py`

- [ ] **Step 1: 更新 `app/api/router.py`**

```python
from fastapi import APIRouter
from app.api import agent, auth
from app.users import router as users_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users_router.router)
api_router.include_router(agent.router)
```

- [ ] **Step 2: 给 Agent 接口加权限保护**

修改 `app/api/agent.py`，在文件顶部追加导入，并给两个接口添加依赖：

在 import 区追加：
```python
from app.auth.dependencies import require_role
from app.users.models import User
from fastapi import Depends
```

修改 `query` 接口签名：
```python
@router.post("/query", response_model=AgentQueryResponse)
async def query(
    request: AgentQueryRequest,
    _current_user: User = Depends(require_role("admin", "editor")),
):
```

修改 `get_schemas` 接口签名：
```python
@router.get("/schemas", response_model=SchemasResponse)
async def get_schemas(
    _current_user: User = Depends(require_role("admin", "editor", "viewer")),
):
```

- [ ] **Step 3: 提交**

```bash
git add app/api/router.py app/api/agent.py
git commit -m "feat: wire up routes and protect agent endpoints with RBAC"
```

---

### Task 11: 角色初始化脚本

**Files:**
- Modify: `seed_data.py`

- [ ] **Step 1: 在 seed_data.py 中追加角色初始化**

在 `seed()` 函数开头（`Base.metadata.create_all` 之后）追加：

```python
    # 初始化角色
    import json
    roles_data = [
        ("admin", "超级管理员", json.dumps(["*"])),
        ("editor", "编辑者", json.dumps(["agent:query", "agent:schemas"])),
        ("viewer", "查看者", json.dumps(["agent:schemas"])),
    ]
    for name, desc, perms in roles_data:
        role = Role(name=name, description=desc, permissions=perms)
        session.add(role)
    session.flush()
    print(f"已创建 {len(roles_data)} 个角色")
```

同时在文件顶部的 import 区追加：
```python
from app.users.models import Product, Order, OrderItem, Role
```

（原来只导入了 Product, Order, OrderItem，需追加 Role）

- [ ] **Step 2: 运行 seed 脚本**

Run: `python seed_data.py`
Expected: 输出包含 "已创建 3 个角色" 和 "已插入 21 个商品, 100 个订单"

- [ ] **Step 3: 提交**

```bash
git add seed_data.py
git commit -m "feat: add role initialization to seed script"
```

---

### Task 12: 更新 README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 在 README 中追加认证相关说明**

在 "API 接口" 章节之前，插入新章节：

```markdown
## 认证与权限

### 获取 Token

```bash
# 注册
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "123456"}'

# 登录
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username_or_phone": "testuser", "password": "123456"}'
```

### 使用 Token

所有 `/api/agent/*` 和 `/api/users/*` 接口需要在请求头中携带 Token：

```bash
curl http://localhost:8000/api/agent/schemas \
  -H "Authorization: Bearer <your_access_token>"
```

### 角色说明

| 角色 | 权限 |
|------|------|
| admin | 所有操作 |
| editor | Agent 查询 + 查看表结构 |
| viewer | 仅查看表结构 |
```

- [ ] **Step 2: 提交**

```bash
git add README.md
git commit -m "docs: update README with auth and RBAC info"
```
