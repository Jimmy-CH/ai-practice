from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.material_asset import MaterialAsset
from app.schemas.auth import UserOut
from app.schemas.material import MaterialCreate, MaterialOut, MaterialUpdate, ReviewAction
from app.api.auth import get_current_user
from app.services import material_service as svc

router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("", response_model=list[MaterialOut])
async def list_materials(
    status: str | None = Query(None),
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    owner_id = user.id if user.role == "editor" else None
    return await svc.list_materials(db, owner_id=owner_id, status=status)


@router.get("/pending", response_model=list[MaterialOut])
async def pending_list(
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "reviewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要 reviewer 角色")
    return await svc.list_materials(db, status="pending_review")


@router.get("/approved", response_model=list[MaterialOut])
async def approved_list(
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    if user.role == "editor" and asset.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该资产")
    return asset


@router.post("", response_model=MaterialOut)
async def create_material(
    data: MaterialCreate,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "editor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要 editor 角色")
    return await svc.create_material(db, user.id, data)


@router.put("/{material_id}", response_model=MaterialOut)
async def update_material(
    material_id: int,
    data: MaterialUpdate,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "editor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要 editor 角色")
    asset = await svc.get_material(db, material_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    if asset.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该资产")
    if asset.status == "pending_review":
        raise HTTPException(status_code=400, detail="待审核资产不可编辑")
    return await svc.update_material(db, asset, data)


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: int,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "editor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要 editor 角色")
    asset = await svc.get_material(db, material_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    if asset.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该资产")
    if asset.status not in ("draft", "rejected"):
        raise HTTPException(status_code=400, detail="只能删除草稿或被驳回资产")
    await svc.delete_material(db, asset)


@router.post("/{material_id}/submit", response_model=MaterialOut)
async def submit_material(
    material_id: int,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "editor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要 editor 角色")
    asset = await svc.get_material(db, material_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    if asset.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该资产")
    try:
        return await svc.submit_for_review(db, asset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{material_id}/reviews", response_model=MaterialOut)
async def review_material(
    material_id: int,
    action: ReviewAction,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "reviewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要 reviewer 角色")
    asset = await svc.get_material(db, material_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    try:
        return await svc.review_material(db, asset, action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{material_id}/download")
async def download_material(
    material_id: int,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await svc.get_material(db, material_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    if user.role == "editor" and asset.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该资产")
    if asset.status != "approved":
        raise HTTPException(status_code=400, detail="仅已审核通过的资产可下载")
    return PlainTextResponse(
        content=asset.content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=material_{asset.id}.md"},
    )
