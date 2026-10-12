from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.content import ContentAsset, ContentProject, Source
from app.services.generation import DeepSeekGenerator
from app.services.retrieval import split_and_rank

router = APIRouter(prefix="/projects/{project_id}", tags=["generation"])


@router.get("/assets")
async def list_assets(project_id: str, db: AsyncSession = Depends(get_db)) -> list[dict]:
    assets = list((await db.scalars(select(ContentAsset).where(ContentAsset.project_id == project_id))).all())
    return [{"id": asset.id, "kind": asset.kind, "status": asset.status, "content": asset.content, "citations": asset.citations} for asset in assets]


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_assets(project_id: str, db: AsyncSession = Depends(get_db)) -> list[dict]:
    project = await db.get(ContentProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    sources = list((await db.scalars(select(Source).where(Source.project_id == project_id))).all())
    if not sources:
        raise HTTPException(status_code=422, detail="需补充资料")
    if not settings.deepseek_api_key:
        raise HTTPException(status_code=422, detail="未配置 DeepSeek API Key")
    ranked = []
    for source in sources:
        ranked.extend((source, evidence) for evidence in split_and_rank(source.content, [project.theme, project.audience]))
    ranked.sort(key=lambda item: item[1].score, reverse=True)
    selected = ranked[:settings.max_evidence_chunks]
    if not selected or selected[0][1].score == 0:
        raise HTTPException(status_code=422, detail="需补充资料")
    evidence = [{"source_id": source.id, "text": item.text} for source, item in selected]
    try:
        generated = await DeepSeekGenerator(settings.deepseek_api_key, settings.deepseek_base_url, settings.deepseek_model).generate(project.theme, evidence)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"内容生成失败: {error}") from error
    allowed_ids = {item["source_id"] for item in evidence}
    drafts = []
    for item in generated:
        source_ids = item.get("source_ids", [])
        if item.get("kind") not in {"announcement", "faq", "poster"} or not item.get("content") or not source_ids or not set(source_ids).issubset(allowed_ids):
            raise HTTPException(status_code=422, detail="模型返回了无依据内容")
        drafts.append((item["kind"], item["content"], [{"source_id": source_id} for source_id in source_ids]))
    if {item[0] for item in drafts} != {"announcement", "faq", "poster"}:
        raise HTTPException(status_code=422, detail="模型未生成完整内容")
    assets = [ContentAsset(project_id=project_id, kind=kind, content=content, citations=citations) for kind, content, citations in drafts]
    db.add_all(assets)
    await db.commit()
    for asset in assets:
        await db.refresh(asset)
    return [{"id": asset.id, "kind": asset.kind, "status": asset.status, "content": asset.content, "citations": asset.citations} for asset in assets]
