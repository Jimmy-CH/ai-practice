from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.auth import UserOut
from app.schemas.analysis import AnalysisOut, AnalysisUpdate
from app.api.auth import get_current_user
from app.services import analysis_service as svc

router = APIRouter()


@router.get("/{source_title}", response_model=AnalysisOut)
async def get_analysis(
    source_title: str,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis = await svc.get_analysis_by_title(db, user.id, source_title)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="解析结果不存在")
    return analysis.to_dict()


@router.put("/{analysis_id}", response_model=AnalysisOut)
async def update_analysis(
    analysis_id: int,
    data: AnalysisUpdate,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis = await svc.get_analysis(db, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="解析结果不存在")
    if analysis.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限修改")
    updated = await svc.update_analysis(db, analysis, data)
    return updated.to_dict()
