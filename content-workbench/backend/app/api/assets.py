from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import get_current_user, require_role
from app.database import get_db
from app.models.content import ContentAsset, ContentProject, ReviewRecord, User
from app.export.renderers import render_html, render_markdown
from app.services.generation import GenerationValidationError, validate_kind_content

router = APIRouter(prefix="/assets", tags=["assets"])


class EditPayload(BaseModel):
    content: dict


class ReviewPayload(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    comment: str = ""


async def _load_asset(db: AsyncSession, asset_id: str) -> ContentAsset:
    asset = await db.get(ContentAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="资产不存在")
    return asset


@router.get("/pending")
async def list_pending_assets(db: AsyncSession = Depends(get_db), _: User = Depends(require_role("reviewer"))) -> list[dict]:
    rows = await db.execute(
        select(ContentAsset, ContentProject.name)
        .join(ContentProject, ContentAsset.project_id == ContentProject.id)
        .where(ContentAsset.status == "pending_review")
        .order_by(ContentAsset.created_at.desc())
    )
    return [{"id": a.id, "kind": a.kind, "project_name": name, "content": a.content, "citations": a.citations} for a, name in rows]


@router.get("/approved")
async def list_approved_assets(db: AsyncSession = Depends(get_db), _: User = Depends(require_role("editor"))) -> list[dict]:
    rows = await db.execute(
        select(ContentAsset, ContentProject.name)
        .join(ContentProject, ContentAsset.project_id == ContentProject.id)
        .where(ContentAsset.status == "approved")
        .order_by(ContentAsset.created_at.desc())
    )
    return [{"id": a.id, "kind": a.kind, "project_name": name, "content": a.content, "citations": a.citations} for a, name in rows]


@router.put("/{asset_id}")
async def edit_asset(asset_id: str, payload: EditPayload, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("editor"))) -> dict:
    asset = await _load_asset(db, asset_id)
    if asset.status == "pending_review":
        raise HTTPException(status_code=409, detail="审核中不可编辑")
    try:
        validate_kind_content(asset.kind, payload.content)
    except GenerationValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    before = asset.content
    asset.content = payload.content
    reset = asset.status == "approved"
    if reset:
        asset.status = "draft"
    await db.commit()
    await record_audit(db, user.username, "edit_asset", "asset", asset.id, detail={"before": before, "after": payload.content, "status_reset": reset})
    return {"id": asset.id, "kind": asset.kind, "status": asset.status, "content": asset.content}


@router.post("/{asset_id}/submit")
async def submit_asset(asset_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("editor"))) -> dict:
    asset = await _load_asset(db, asset_id)
    if asset.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=409, detail="当前状态不可提交审核")
    asset.status = "pending_review"
    await db.commit()
    await record_audit(db, user.username, "submit_asset", "asset", asset.id)
    return {"id": asset.id, "status": asset.status}


@router.post("/{asset_id}/reviews")
async def review_asset(asset_id: str, payload: ReviewPayload, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("reviewer"))) -> dict:
    asset = await _load_asset(db, asset_id)
    if asset.status != "pending_review":
        raise HTTPException(status_code=409, detail="资产不在审核中")
    asset.status = payload.decision
    db.add(ReviewRecord(asset_id=asset_id, decision=payload.decision, comment=payload.comment, reviewer=user.username))
    await db.commit()
    await record_audit(db, user.username, "review_asset", "asset", asset.id, detail={"decision": payload.decision, "comment": payload.comment})
    return {"id": asset.id, "status": asset.status}


@router.get("/{asset_id}/citations")
async def get_citations(asset_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    asset = await _load_asset(db, asset_id)
    return asset.citations


@router.get("/{asset_id}/download")
async def download_asset(asset_id: str, format: str = "markdown", db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    asset = await _load_asset(db, asset_id)
    if asset.status != "approved":
        raise HTTPException(status_code=409, detail="资产尚未通过审核")
    if format == "markdown":
        text = render_markdown(asset.kind, asset.content)
        media = "text/markdown; charset=utf-8"
        filename = f"{asset.kind}.md"
    elif format == "html":
        text = render_html(asset.kind, asset.content)
        media = "text/html; charset=utf-8"
        filename = f"{asset.kind}.html"
    else:
        raise HTTPException(status_code=422, detail="不支持的格式")
    await record_audit(db, user.username, "download_asset", "asset", asset.id, detail={"format": format})
    return Response(content=text, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
