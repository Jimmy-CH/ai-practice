import hashlib
import hmac
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.content import ContentProject, Source
from app.schemas.sources import GitSourceCreate, SourceRead, TextSourceCreate

router = APIRouter(prefix="/projects/{project_id}/sources", tags=["sources"])
webhook_router = APIRouter(prefix="/projects/{project_id}/webhooks", tags=["webhooks"])


@router.post("/text", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
async def create_text_source(project_id: str, payload: TextSourceCreate, db: AsyncSession = Depends(get_db)) -> Source:
    if await db.get(ContentProject, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    source = Source(project_id=project_id, name=payload.name, content=payload.content, content_hash=hashlib.sha256(payload.content.encode()).hexdigest())
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@router.post("/git", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
async def create_git_source(project_id: str, payload: GitSourceCreate, db: AsyncSession = Depends(get_db)) -> Source:
    if await db.get(ContentProject, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    content = f"{payload.repository}@{payload.release}\n{payload.content}"
    source = Source(project_id=project_id, name=f"{payload.repository}:{payload.release}", source_type="git", content=content, content_hash=hashlib.sha256(content.encode()).hexdigest())
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@webhook_router.post("/cicd", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
async def receive_cicd_webhook(project_id: str, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> Source:
    raw_body = await request.body()
    signature = request.headers.get("X-Signature", "").removeprefix("sha256=")
    expected = hmac.new(settings.webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    timestamp = request.headers.get("X-Timestamp", "0")
    if not hmac.compare_digest(signature, expected) or abs(time.time() - int(timestamp)) > 300:
        raise HTTPException(status_code=401, detail="无效的 Webhook 签名")
    if await db.get(ContentProject, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    payload = await request.json()
    event_id = str(payload.get("event_id", ""))
    if not event_id:
        raise HTTPException(status_code=422, detail="缺少 event_id")
    existing = await db.scalar(select(Source).where(Source.project_id == project_id, Source.name == event_id))
    if existing:
        response.status_code = status.HTTP_200_OK
        return existing
    source = Source(project_id=project_id, name=event_id, source_type="cicd", content=raw_body.decode(), content_hash=hashlib.sha256(raw_body).hexdigest())
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source
