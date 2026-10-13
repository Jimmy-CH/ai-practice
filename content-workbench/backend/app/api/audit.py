from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.database import get_db
from app.models.content import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit(db: AsyncSession = Depends(get_db), _: object = Depends(require_role("reviewer"))) -> list[dict]:
    logs = list((await db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100))).all())
    return [{"id": log.id, "actor": log.actor, "action": log.action, "object_type": log.object_type, "object_id": log.object_id, "detail": log.detail, "created_at": str(log.created_at)} for log in logs]
