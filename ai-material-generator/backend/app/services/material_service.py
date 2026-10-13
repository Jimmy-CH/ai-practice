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
    else:
        asset.status = "rejected"
    asset.review_comment = action.comment or None
    await session.commit()
    await session.refresh(asset)
    return asset
