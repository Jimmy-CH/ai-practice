from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import AuditLog


async def record_audit(db: AsyncSession, actor: str, action: str, object_type: str, object_id: str, detail: dict | None = None) -> None:
    db.add(AuditLog(actor=actor, action=action, object_type=object_type, object_id=object_id, detail=detail))
    await db.commit()
