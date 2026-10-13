import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.auth import require_role
from app.config import settings
from app.database import get_db
from app.models.content import ContentAsset, ContentProject, Source, User
from app.services.generation import ContentGenerator, DeepSeekGenerator, GenerationValidationError, parse_model_output, validate_generation
from app.services.retrieval import select_evidence

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}", tags=["generation"])


def get_generator() -> ContentGenerator:
    if not settings.deepseek_api_key:
        raise HTTPException(status_code=422, detail="未配置 DeepSeek API Key")
    return DeepSeekGenerator(settings.deepseek_api_key, settings.deepseek_base_url, settings.deepseek_model)


@router.get("/assets")
async def list_assets(project_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("editor"))) -> list[dict]:
    assets = list((await db.scalars(select(ContentAsset).where(ContentAsset.project_id == project_id))).all())
    return [_serialize(asset) for asset in assets]


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_assets(project_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_role("editor")), generator: ContentGenerator = Depends(get_generator)) -> list[dict]:
    project = await db.get(ContentProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    sources = list((await db.scalars(select(Source).where(Source.project_id == project_id))).all())
    if not sources:
        raise HTTPException(status_code=422, detail="需补充资料")
    evidence = select_evidence([(s.id, s.content) for s in sources], [project.theme, project.audience], settings.max_evidence_chunks)
    if not evidence:
        raise HTTPException(status_code=422, detail="需补充资料")
    allowed = {item.source_id: item.text for item in evidence}
    try:
        raw = await generator.generate(project.theme, project.audience, [{"source_id": k, "text": v} for k, v in allowed.items()])
        results = validate_generation(parse_model_output(raw), allowed)
    except GenerationValidationError as error:
        logger.warning("生成内容校验失败: %s", error)
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.error("内容生成失败: %s", error, exc_info=True)
        raise HTTPException(status_code=502, detail="内容生成失败，请稍后重试") from error
    assets = [ContentAsset(project_id=project_id, kind=kind, content=content, citations=citations) for kind, content, citations in results]
    db.add_all(assets)
    await db.commit()
    for asset in assets:
        await db.refresh(asset)
    await record_audit(db, user.username, "generate_assets", "project", project_id, detail={"kinds": sorted(a.kind for a in assets)})
    return [_serialize(asset) for asset in assets]


def _serialize(asset: ContentAsset) -> dict:
    return {"id": asset.id, "kind": asset.kind, "status": asset.status, "content": asset.content, "citations": asset.citations}
