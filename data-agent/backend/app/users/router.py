from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user, require_role
from app.users.models import User, Role
from app.users.schemas import (
    UserOut, UpdateRoleRequest, UpdateActiveRequest, UpdateProfileRequest,
    ChangePasswordRequest, ProfileStatsOut,
)
from app.users.service import (
    get_all_users, update_user_role, update_user_active, delete_user, get_user_by_id,
    update_profile, change_password,
)
from app.models.query import SavedQuery
from app.models.share import SharedQuery
from app.models.datasource import DataSource
from app.models.audit import AuditLog

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return _user_to_out(current_user)


@router.get("/me/stats", response_model=ProfileStatsOut)
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的个人数据统计。"""
    # 查询次数（从审计日志）
    q_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.user_id == current_user.id, AuditLog.action == "query"
        )
    )
    total_queries = q_result.scalar() or 0

    # 收藏查询数
    sq_result = await db.execute(
        select(func.count()).select_from(SavedQuery).where(SavedQuery.user_id == current_user.id)
    )
    saved_queries = sq_result.scalar() or 0

    # 分享链接数
    sh_result = await db.execute(
        select(func.count()).select_from(SharedQuery).where(SharedQuery.user_id == current_user.id)
    )
    shared_links = sh_result.scalar() or 0

    # 数据源数
    ds_result = await db.execute(
        select(func.count()).select_from(DataSource).where(DataSource.uploaded_by == current_user.id)
    )
    data_sources = ds_result.scalar() or 0

    return ProfileStatsOut(
        total_queries=total_queries,
        saved_queries=saved_queries,
        shared_links=shared_links,
        data_sources=data_sources,
    )


@router.put("/me", response_model=UserOut)
async def update_me(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新当前用户个人信息。"""
    user = await update_profile(db, current_user.id, req.email, req.phone)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    return _user_to_out(user)


@router.put("/me/password")
async def change_my_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改当前用户密码。"""
    if len(req.new_password) < 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "新密码至少 6 位")
    ok = await change_password(db, current_user.id, req.old_password, req.new_password)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "旧密码不正确")
    return {"message": "密码已修改"}


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
