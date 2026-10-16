from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.auth import UserOut
from app.api.auth import get_current_user
from app.services import generated_material_service as gm_svc
from app.models.generated_material import GeneratedMaterial

router = APIRouter()


class GeneratedMaterialUpdate(BaseModel):
    content: str


@router.put("/{generated_material_id}")
async def update_generated_material(
    generated_material_id: int,
    data: GeneratedMaterialUpdate,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gm = await gm_svc.get_generated_material_by_id(db, generated_material_id)
    if gm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="生成记录不存在")
    if gm.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限修改")
    updated = await gm_svc.update_generated_material(db, gm, data.content)
    return {**updated.to_dict(), "cached": True}
