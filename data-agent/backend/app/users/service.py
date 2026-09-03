import logging
import random
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import User, Role, OAuthAccount
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
