from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user, require_role
from app.users.models import User
from app.users.schemas import UserOut, UpdateRoleRequest
from app.users.service import get_all_users, update_user_role

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
