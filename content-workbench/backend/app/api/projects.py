import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import require_role
from app.database import get_db
from app.models.content import ContentAsset, ContentProject, DeliveryTask, ReviewRecord, Source

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    theme: str
    audience: str = ""
    tone: str = ""


class ProjectOut(BaseModel):
    id: str
    name: str
    theme: str
    audience: str
    tone: str
    source_count: int
    model_config = {"from_attributes": True}


class SourceCreate(BaseModel):
    name: str
    content: str


class SourceOut(BaseModel):
    id: str
    project_id: str
    name: str
    content: str
    content_hash: str
    created_at: str
    model_config = {"from_attributes": True}


@router.post("", status_code=201, response_model=ProjectOut)
async def create_project(payload: ProjectCreate, user=Depends(require_role("editor")), db: AsyncSession = Depends(get_db)):
    project = ContentProject(**payload.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    await record_audit(db, user.username, "create_project", "project", project.id, detail=payload.model_dump())
    return ProjectOut(id=project.id, name=project.name, theme=project.theme, audience=project.audience, tone=project.tone, source_count=0)


@router.get("", response_model=list[ProjectOut])
async def list_projects(user=Depends(require_role("editor")), db: AsyncSession = Depends(get_db)):
    projects = (await db.scalars(select(ContentProject))).all()
    counts = {row.project_id: row.c for row in (await db.execute(select(Source.project_id, func.count(Source.id).label("c")).group_by(Source.project_id))).mappings()}
    return [
        ProjectOut(id=p.id, name=p.name, theme=p.theme, audience=p.audience, tone=p.tone, source_count=counts.get(p.id, 0))
        for p in projects
    ]


@router.post("/{project_id}/sources", status_code=201, response_model=SourceOut)
async def add_source(project_id: str, payload: SourceCreate, user=Depends(require_role("editor")), db: AsyncSession = Depends(get_db)):
    project = await db.get(ContentProject, project_id)
    if project is None:
        logger.warning("添加资料失败: 项目不存在 project_id=%s", project_id)
        raise HTTPException(status_code=404, detail="项目不存在")
    content_hash = hashlib.sha256(payload.content.encode()).hexdigest()
    existing = (await db.scalars(select(Source).where(Source.project_id == project_id, Source.content_hash == content_hash))).first()
    if existing is not None:
        logger.warning("添加资料重复: project_id=%s name=%s", project_id, payload.name)
        raise HTTPException(status_code=409, detail="资料内容重复")
    source = Source(
        project_id=project_id,
        name=payload.name,
        content=payload.content,
        content_hash=content_hash,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    await record_audit(db, user.username, "add_source", "source", source.id, detail={"project_id": project_id, "name": payload.name})
    return SourceOut(id=source.id, project_id=source.project_id, name=source.name, content=source.content, content_hash=source.content_hash, created_at=str(source.created_at))


@router.get("/{project_id}/sources", response_model=list[SourceOut])
async def list_sources(project_id: str, user=Depends(require_role("editor")), db: AsyncSession = Depends(get_db)):
    project = await db.get(ContentProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    sources = (await db.scalars(select(Source).where(Source.project_id == project_id))).all()
    return [SourceOut(id=s.id, project_id=s.project_id, name=s.name, content=s.content, content_hash=s.content_hash, created_at=str(s.created_at)) for s in sources]


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, user=Depends(require_role("editor")), db: AsyncSession = Depends(get_db)):
    project = await db.get(ContentProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    assets = list((await db.scalars(select(ContentAsset).where(ContentAsset.project_id == project_id))).all())
    for asset in assets:
        for row in (await db.scalars(select(ReviewRecord).where(ReviewRecord.asset_id == asset.id))).all():
            await db.delete(row)
        for row in (await db.scalars(select(DeliveryTask).where(DeliveryTask.asset_id == asset.id))).all():
            await db.delete(row)
        await db.delete(asset)
    for source in (await db.scalars(select(Source).where(Source.project_id == project_id))).all():
        await db.delete(source)
    await db.delete(project)
    await db.commit()
    await record_audit(db, user.username, "delete_project", "project", project_id)


@router.delete("/{project_id}/sources/{source_id}", status_code=204)
async def delete_source(project_id: str, source_id: str, user=Depends(require_role("editor")), db: AsyncSession = Depends(get_db)):
    project = await db.get(ContentProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    source = await db.get(Source, source_id)
    if source is None or source.project_id != project_id:
        raise HTTPException(status_code=404, detail="资料不存在")
    await db.delete(source)
    await db.commit()
    await record_audit(db, user.username, "delete_source", "source", source_id, detail={"project_id": project_id})
