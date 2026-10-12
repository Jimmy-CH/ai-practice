from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.content import ContentAsset

router = APIRouter(prefix="/assets", tags=["delivery"])


@router.post("/{asset_id}/reviews")
async def review_asset(asset_id: str, payload: dict[str, str], db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    asset = await db.get(ContentAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="资产不存在")
    decision = payload.get("decision")
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="无效的审核结论")
    asset.status = decision
    await db.commit()
    return {"id": asset.id, "status": asset.status}


@router.post("/{asset_id}/deliveries", status_code=201)
async def create_mock_delivery(asset_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    asset = await db.get(ContentAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="资产不存在")
    if asset.status != "approved":
        raise HTTPException(status_code=409, detail="资产尚未通过审核")
    return {"asset_id": asset.id, "status": "completed"}


@router.get("/{asset_id}/download")
async def download_asset(asset_id: str, format: str, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    asset = await db.get(ContentAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="资产不存在")
    if asset.status != "approved":
        raise HTTPException(status_code=409, detail="资产尚未通过审核")
    return {"format": format, "content": asset.content}
