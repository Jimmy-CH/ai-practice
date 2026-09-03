import logging
import random
import string

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import select
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
    get_user_by_id, get_role_by_name, generate_sms_code, save_sms_code,
    verify_sms_code, create_oauth_user,
)
from app.users.models import User as UserModel

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
        random_username = f"phone_{req.phone[-4:]}_{''.join(random.choices(string.digits, k=4))}"
        viewer_role = await get_role_by_name(db, "viewer")
        user = UserModel(phone=req.phone, username=random_username, role_id=viewer_role.id)
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
