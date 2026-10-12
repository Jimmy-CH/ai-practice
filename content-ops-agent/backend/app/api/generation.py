from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.content import ContentAsset, ContentProject, Source

router = APIRouter(prefix="/projects/{project_id}", tags=["generation"])


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_assets(project_id: str, db: AsyncSession = Depends(get_db)) -> list[dict]:
    project = await db.get(ContentProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    sources = list((await db.scalars(select(Source).where(Source.project_id == project_id))).all())
    if not sources:
        raise HTTPException(status_code=422, detail="需补充资料")
    citations = [{"source_id": source.id, "name": source.name} for source in sources]
    context = "\n".join(source.content for source in sources)
    drafts = [
        ("announcement", {"title": project.theme, "body": context}),
        ("faq", {"items": [{"question": f"{project.theme} 是什么？", "answer": context}]}),
        ("poster", {"headline": project.theme, "highlights": context, "call_to_action": "立即体验"}),
    ]
    assets = [ContentAsset(project_id=project_id, kind=kind, content=content, citations=citations) for kind, content in drafts]
    db.add_all(assets)
    await db.commit()
    for asset in assets:
        await db.refresh(asset)
    return [{"id": asset.id, "kind": asset.kind, "status": asset.status, "content": asset.content, "citations": asset.citations} for asset in assets]
