import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import get_current_user, require_role
from app.database import get_db
from app.models.content import ContentAsset, DeliveryTask, User
from app.services.publisher import ADAPTERS

logger = logging.getLogger(__name__)
router = APIRouter(tags=["delivery"])


async def _load_asset(db: AsyncSession, asset_id: str) -> ContentAsset:
    asset = await db.get(ContentAsset, asset_id)
    if asset is None:
        logger.warning("发布失败: 资产不存在 asset_id=%s", asset_id)
        raise HTTPException(status_code=404, detail="资产不存在")
    return asset


@router.post("/assets/{asset_id}/deliveries", status_code=201)
async def create_delivery(asset_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("editor")), channel: str = "mock") -> dict:
    asset = await _load_asset(db, asset_id)
    if asset.status != "approved":
        logger.warning("发布失败: 资产未通过审核 asset_id=%s status=%s", asset_id, asset.status)
        raise HTTPException(status_code=409, detail="资产尚未通过审核")
    adapter = ADAPTERS.get(channel)
    if adapter is None:
        logger.warning("发布失败: 未知渠道 channel=%s", channel)
        raise HTTPException(status_code=422, detail="未知发布渠道")
    try:
        task_id = await adapter.publish(asset)
    except Exception as error:
        logger.error("发布异常: asset_id=%s channel=%s error=%s", asset_id, channel, error, exc_info=True)
        raise HTTPException(status_code=502, detail="发布失败") from error
    db.add(DeliveryTask(id=task_id, asset_id=asset_id, channel=channel, status="completed"))
    await db.commit()
    logger.info("发布成功: asset_id=%s channel=%s task_id=%s", asset_id, channel, task_id)
    await record_audit(db, user.username, "create_delivery", "asset", asset_id, detail={"channel": channel, "task_id": task_id})
    return {"asset_id": asset_id, "task_id": task_id, "status": "completed"}


@router.get("/deliveries")
async def list_deliveries(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    tasks = list((await db.scalars(select(DeliveryTask).order_by(DeliveryTask.created_at.desc()))).all())
    return [{"id": t.id, "asset_id": t.asset_id, "channel": t.channel, "status": t.status, "created_at": str(t.created_at)} for t in tasks]
