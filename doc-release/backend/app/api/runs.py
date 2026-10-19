import asyncio
import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.clock import utcnow
from app.database import get_db
from app.models import Artifact, Repo, Run
from app.models.run import blank_steps
from app.schemas.run import RunCreate
from app.services import archive_service, git_service, pipeline_service, renderers
from app.services.errors import GitError

router = APIRouter(prefix="/api/runs", tags=["runs"])

_ACTIVE_STATUSES = ("pending", "running")
# 查重与插入须原子进行，否则并发请求可同时通过查重、绕过 409
_create_lock = asyncio.Lock()
_KIND_META = {
    "checklist": ("checklist.csv", "text/csv; charset=utf-8"),
    "document": ("product-doc.md", "text/markdown; charset=utf-8"),
    "trace": ("trace.json", "application/json; charset=utf-8"),
}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _run_detail(db: AsyncSession, run: Run) -> dict:
    detail = run.to_dict()
    repo = await db.get(Repo, run.repo_id)
    detail["repo_name"] = repo.name if repo else ""
    arts = (await db.execute(select(Artifact).where(Artifact.run_id == run.id))).scalars().all()
    detail["artifacts"] = [a.to_dict() for a in arts]
    return detail


@router.post("", status_code=201)
async def create_run(payload: RunCreate, db: AsyncSession = Depends(get_db)) -> dict:
    repo = await db.get(Repo, payload.repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="仓库不存在")
    if payload.tone not in ("business", "tech"):
        raise HTTPException(status_code=422, detail="tone 仅支持 business 或 tech")
    try:
        # git 子进程会阻塞事件循环，最长 60s；统一放线程池
        await asyncio.to_thread(git_service.resolve_ref, repo.path, payload.base_ref)
        await asyncio.to_thread(git_service.resolve_ref, repo.path, payload.head_ref)
    except GitError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    async with _create_lock:
        dup = (await db.execute(
            select(Run).where(Run.repo_id == payload.repo_id,
                             Run.base_ref == payload.base_ref,
                             Run.head_ref == payload.head_ref,
                             Run.status.in_(_ACTIVE_STATUSES)))).scalars().first()
        if dup is not None:
            raise HTTPException(status_code=409, detail="相同范围已有运行中的任务")

        run = Run(
            repo_id=payload.repo_id,
            base_ref=payload.base_ref,
            head_ref=payload.head_ref,
            # 版本号直接做归档目录名：未填写时用 head_ref，需先收敛成单层目录
            version_label=archive_service.normalize_version(
                payload.version_label or payload.head_ref),
            tone=payload.tone,
            mask=payload.mask,
        )
        run.steps = blank_steps()
        db.add(run)
        await db.commit()
    await db.refresh(run)

    # schedule_run 持有任务引用，供取消与进程退出时判断任务是否仍在跑
    pipeline_service.schedule_run(run.id)
    return await _run_detail(db, run)


@router.get("")
async def list_runs(limit: int = 20, offset: int = 0,
                   db: AsyncSession = Depends(get_db)) -> dict:
    total = (await db.execute(select(func.count()).select_from(Run))).scalar_one()
    rows = (await db.execute(select(Run).order_by(Run.created_at.desc(), Run.id)
                             .limit(min(max(limit, 1), 100)).offset(max(offset, 0)))).scalars().all()
    repo_names: dict[int, str] = {}
    if rows:
        repo_ids = {r.repo_id for r in rows}
        repos = (await db.execute(select(Repo).where(Repo.id.in_(repo_ids)))).scalars().all()
        repo_names = {repo.id: repo.name for repo in repos}
    items = []
    for r in rows:
        d = r.to_dict()
        d.pop("steps", None)
        d.pop("logs", None)
        d.pop("result", None)
        d["repo_name"] = repo_names.get(r.repo_id, "")
        items.append(d)
    return {"total": total, "items": items}


@router.get("/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    return await _run_detail(db, run)


def _build_snapshot(run: Run, live: dict | None) -> dict:
    base = run.to_dict()
    if live and live.get("status") == "running":
        base.update({"status": live["status"], "current_step": live["current_step"],
                     "steps": live["steps"], "logs": live["logs"],
                     "stats": live.get("stats") or {}, "result": live.get("result")})
    return base


@router.get("/{run_id}/events")
async def run_events(run_id: str, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")

    # 先订阅再读快照：两者之间发布的事件会进队列，由 seen 去重，没有丢失窗口
    queue = pipeline_service.bus.subscribe(run_id)
    try:
        await db.refresh(run)
        snapshot = _build_snapshot(run, pipeline_service.get_live_state(run_id))
    except Exception:
        pipeline_service.bus.unsubscribe(run_id, queue)
        raise
    finally:
        # SSE 可能持续数分钟，快照构建完就归还连接，避免长期占用连接池
        await db.close()

    async def gen():
        try:
            seen = {(l.get("ts"), l.get("tag"), l.get("message")) for l in snapshot.get("logs", [])}
            yield _sse("snapshot", {"run": snapshot})
            if snapshot["status"] not in ("pending", "running"):
                yield _sse("done", {"status": snapshot["status"], "result": snapshot.get("result")})
                return
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                if ev["event"] == "log":
                    key = (ev["data"].get("ts"), ev["data"].get("tag"), ev["data"].get("message"))
                    if key in seen:
                        continue
                    seen.add(key)
                yield _sse(ev["event"], ev["data"])
                if ev["event"] == "done":
                    break
        finally:
            pipeline_service.bus.unsubscribe(run_id, queue)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    if run.status not in _ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail=f"运行已是 {run.status} 状态，无法取消")
    if pipeline_service.is_running_in_process(run_id):
        pipeline_service.cancel_run(run_id)
        return {"ok": True}
    # 本进程没有对应任务（如服务重启）：直接收敛状态，否则这条记录会永久卡在运行中
    run.status = "cancelled"
    run.error = "运行已取消"
    run.finished_at = utcnow()
    steps = run.steps or []
    for step in steps:
        if step.get("status") == "active":
            step["status"] = "pending"
    run.steps = steps
    flag_modified(run, "steps")
    await db.commit()
    return {"ok": True}


def _render_artifact(run: Run, kind: str, tone: str | None, mask: bool | None) -> str:
    if kind not in _KIND_META:
        raise HTTPException(status_code=422, detail="kind 仅支持 checklist/document/trace")
    if not run.result:
        raise HTTPException(status_code=409, detail="运行尚未完成，无产物可下载")
    opts = {"tone": tone or run.tone, "mask": run.mask if mask is None else mask}
    if opts["tone"] not in ("business", "tech"):
        raise HTTPException(status_code=422, detail="tone 仅支持 business 或 tech")
    result = run.result
    if kind == "checklist":
        return renderers.render_checklist(result, opts)
    if kind == "document":
        return renderers.render_document(result, opts)
    checklist = renderers.render_checklist(result, opts)
    document = renderers.render_document(result, opts)
    text, _ = renderers.render_trace_stable(result, opts, base_sizes={
        "checklist": len(checklist.encode("utf-8")),
        "document": len(document.encode("utf-8")),
    })
    return text


@router.get("/{run_id}/artifacts/{kind}")
async def get_artifact(run_id: str, kind: str, tone: str | None = None, mask: bool | None = None,
                       db: AsyncSession = Depends(get_db)) -> Response:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    text = _render_artifact(run, kind, tone, mask)
    _, media = _KIND_META[kind]
    return Response(content=text, media_type=media)


@router.get("/{run_id}/artifacts/{kind}/download")
async def download_artifact(run_id: str, kind: str, tone: str | None = None, mask: bool | None = None,
                            db: AsyncSession = Depends(get_db)) -> Response:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    text = _render_artifact(run, kind, tone, mask)
    filename, media = _KIND_META[kind]
    return Response(content=text, media_type=media,
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@router.delete("/{run_id}")
async def delete_run(run_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    if run.status in _ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="运行仍在进行中，请先取消")
    for art in (await db.execute(select(Artifact).where(Artifact.run_id == run.id))).scalars().all():
        await db.delete(art)
    archive_service.delete_archive_if_owned(pipeline_service.get_archive_root(),
                                            run.version_label, run.id)
    await db.delete(run)
    await db.commit()
    return {"ok": True}
