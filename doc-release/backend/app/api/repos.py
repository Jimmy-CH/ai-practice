from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import seed_data
from app.database import get_db
from app.models import Repo, Run
from app.schemas.repo import RepoCreate
from app.services import git_service
from app.services.errors import GitError

router = APIRouter(prefix="/api/repos", tags=["repos"])

PREVIEW_MAX_LINES = 300


async def _get_repo_or_404(db: AsyncSession, repo_id: int) -> Repo:
    repo = await db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="仓库不存在")
    return repo


@router.get("")
async def list_repos(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.execute(select(Repo).order_by(Repo.id))).scalars().all()
    return [r.to_dict() for r in rows]


@router.post("", status_code=201)
async def create_repo(payload: RepoCreate, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        git_service.validate_repo(payload.path)
    except GitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    existing = (await db.execute(select(Repo).where(Repo.path == payload.path))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="该仓库路径已注册")
    name = (payload.name or "").strip() or Path(payload.path).name
    repo = Repo(name=name, path=payload.path, is_sample=False)
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return repo.to_dict()


@router.delete("/{repo_id}")
async def delete_repo(repo_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    repo = await _get_repo_or_404(db, repo_id)
    run_count = (await db.execute(
        select(func.count()).select_from(Run).where(Run.repo_id == repo_id))).scalar_one()
    if run_count:
        raise HTTPException(status_code=400, detail=f"该仓库已有 {run_count} 条运行记录，不可删除")
    await db.delete(repo)
    await db.commit()
    return {"ok": True}


@router.get("/{repo_id}/refs")
async def repo_refs(repo_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    repo = await _get_repo_or_404(db, repo_id)
    try:
        return git_service.list_refs(repo.path)
    except GitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{repo_id}/scenarios")
async def repo_scenarios(repo_id: int, db: AsyncSession = Depends(get_db)) -> list[dict]:
    repo = await _get_repo_or_404(db, repo_id)
    return list(seed_data.SCENARIOS) if repo.is_sample else []


@router.get("/{repo_id}/preview")
async def repo_preview(repo_id: int, base: str, head: str,
                       db: AsyncSession = Depends(get_db)) -> dict:
    repo = await _get_repo_or_404(db, repo_id)
    try:
        return git_service.collect_diff(repo.path, base, head, max_lines=PREVIEW_MAX_LINES)
    except GitError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
