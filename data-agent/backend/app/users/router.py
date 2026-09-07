from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user, require_role
from app.users.models import User, Role
from app.users.schemas import UserOut, UpdateRoleRequest, UpdateActiveRequest
from app.users.service import (
    get_all_users, update_user_role, update_user_active, delete_user, get_user_by_id,
)

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


@router.put("/{user_id}/active", response_model=UserOut)
async def toggle_user_active(
    user_id: int,
    req: UpdateActiveRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """启用/禁用用户（仅 admin）。"""
    if user_id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能禁用自己的账号")
    user = await update_user_active(db, user_id, req.is_active)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    return _user_to_out(user)


@router.delete("/{user_id}")
async def remove_user(
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """删除用户（仅 admin）。"""
    if user_id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能删除自己")
    target = await get_user_by_id(db, user_id)
    if target and target.role and target.role.name == "admin":
        result = await db.execute(
            select(func.count(User.id)).join(Role).where(Role.name == "admin")
        )
        admin_count = result.scalar()
        if admin_count <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能删除最后一个管理员")
    deleted = await delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    return {"message": "用户已删除"}
