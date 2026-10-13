from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import get_current_user, require_role
from app.database import get_db
from app.models.content import ContentAsset, DeliveryTask, User
from app.services.publisher import ADAPTERS

router = APIRouter(tags=["delivery"])


async def _load_asset(db: AsyncSession, asset_id: str) -> ContentAsset:
    asset = await db.get(ContentAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="资产不存在")
    return asset


@router.post("/assets/{asset_id}/deliveries", status_code=201)
async def create_delivery(asset_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("editor")), channel: str = "mock") -> dict:
    asset = await _load_asset(db, asset_id)
    if asset.status != "approved":
        raise HTTPException(status_code=409, detail="资产尚未通过审核")
    adapter = ADAPTERS.get(channel)
    if adapter is None:
        raise HTTPException(status_code=422, detail="未知发布渠道")
    task_id = await adapter.publish(asset)
    db.add(DeliveryTask(id=task_id, asset_id=asset_id, channel=channel, status="completed"))
    await db.commit()
    await record_audit(db, user.username, "create_delivery", "asset", asset_id, detail={"channel": channel, "task_id": task_id})
    return {"asset_id": asset_id, "task_id": task_id, "status": "completed"}


@router.get("/deliveries")
async def list_deliveries(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    tasks = list((await db.scalars(select(DeliveryTask).order_by(DeliveryTask.created_at.desc()))).all())
    return [{"id": t.id, "asset_id": t.asset_id, "channel": t.channel, "status": t.status, "created_at": str(t.created_at)} for t in tasks]
