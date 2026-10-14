"""五步流水线编排、运行状态机、进程内事件总线与取消。

执行模型：API 层 create_task 调用 execute_run；execute_run 自带数据库会话
（与请求生命周期解耦），运行期状态存在内存 _live_states 供 SSE snapshot 使用，
每个步骤结束时落库，结束时整体落库（logs/result/status）。
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Artifact, Repo, Run
from app.models.run import blank_steps
from app.services import archive_service, git_service, llm_service, parser_service, renderers
from app.services.errors import GitError, RunCancelled, ServiceError

logger = logging.getLogger(__name__)

_PIPELINE_MAX_LINES = 600

_session_factory: Callable = AsyncSessionLocal
_archive_root: Path = Path(settings.archive_dir)
_live_states: dict[str, dict] = {}
_cancelled: set[str] = set()


def set_session_factory(factory: Callable) -> None:
    global _session_factory
    _session_factory = factory


def set_archive_root(root: Path) -> None:
    global _archive_root
    _archive_root = Path(root)


class RunEventBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(run_id, set()).add(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(run_id)
        if subs is not None:
            subs.discard(q)
            if not subs:
                self._subs.pop(run_id, None)

    def publish(self, run_id: str, event: dict) -> None:
        for q in list(self._subs.get(run_id, ())):
            q.put_nowait(event)


bus = RunEventBus()


def get_live_state(run_id: str) -> dict | None:
    return _live_states.get(run_id)


def is_cancelled(run_id: str) -> bool:
    return run_id in _cancelled


def cancel_run(run_id: str) -> bool:
    """标记取消；实际生效点在每步开始与 LLM 分块启动前。"""
    _cancelled.add(run_id)
    return True


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _log(run_id: str, state: dict, channel: str, tag: str, message: str) -> None:
    line = {"ts": _now(), "channel": channel, "tag": tag, "message": message}
    state["logs"].append(line)
    bus.publish(run_id, {"event": "log", "data": line})


async def _persist_progress(db, run: Run, state: dict) -> None:
    run.current_step = state["current_step"]
    run.steps = state["steps"]
    # steps 为原地变异的 JSON 列，快照相等时 ORM 脏检查会跳过，需强制标记
    flag_modified(run, "steps")
    if state.get("stats"):
        run.stats = state["stats"]
    await db.commit()


async def _run_step(run_id: str, run: Run, state: dict, db, index: int, fn):
    if is_cancelled(run_id):
        raise RunCancelled("运行已取消")
    step = state["steps"][index]
    total_steps = len(state["steps"])
    step["status"] = "active"
    step["started_at"] = _now()
    state["current_step"] = index
    bus.publish(run_id, {"event": "step", "data": {"index": index, "name": step["name"], "status": "active"}})
    bus.publish(run_id, {"event": "progress", "data": {"percent": int(index / total_steps * 100)}})
    started = datetime.now()
    try:
        result = await fn()
    except RunCancelled:
        step["status"] = "pending"
        raise
    except Exception:
        step["status"] = "failed"
        step["finished_at"] = _now()
        bus.publish(run_id, {"event": "step", "data": {"index": index, "name": step["name"], "status": "failed"}})
        raise
    step["status"] = "done"
    step["finished_at"] = _now()
    step["duration_ms"] = int((datetime.now() - started).total_seconds() * 1000)
    bus.publish(run_id, {"event": "step", "data": {"index": index, "name": step["name"],
                                                   "status": "done", "duration_ms": step["duration_ms"]}})
    bus.publish(run_id, {"event": "progress", "data": {"percent": int((index + 1) / total_steps * 100)}})
    await _persist_progress(db, run, state)
    return result


async def _finish_cancelled(db, run: Run, state: dict, run_id: str) -> None:
    _cancelled.discard(run_id)
    state["status"] = "cancelled"
    state["error"] = "运行已取消"
    _log(run_id, state, "warn", "取消", "运行已被用户取消")
    run.status = "cancelled"
    run.steps = state["steps"]
    flag_modified(run, "steps")
    run.logs = state["logs"]
    flag_modified(run, "logs")
    run.error = "运行已取消"
    run.finished_at = datetime.utcnow()
    await db.commit()
    bus.publish(run_id, {"event": "done", "data": {"status": "cancelled", "result": None}})


async def _finish_failed(db, run: Run, state: dict, run_id: str, exc: Exception) -> None:
    message = str(exc) or exc.__class__.__name__
    if isinstance(exc, GitError):
        message = f"Git 错误：{message}"
    state["status"] = "failed"
    state["error"] = message
    _log(run_id, state, "error", "失败", message)
    run.status = "failed"
    run.steps = state["steps"]
    flag_modified(run, "steps")
    run.logs = state["logs"]
    flag_modified(run, "logs")
    if state.get("stats"):
        run.stats = state["stats"]
    run.error = message
    run.finished_at = datetime.utcnow()
    await db.commit()
    bus.publish(run_id, {"event": "error", "data": {"message": message}})
    bus.publish(run_id, {"event": "done", "data": {"status": "failed", "result": None}})


async def execute_run(run_id: str) -> None:
    """后台任务：执行五步流水线，异常/取消均完整落库并广播。"""
    async with _session_factory() as db:
        run = await db.get(Run, run_id)
        if run is None:
            return
        repo = await db.get(Repo, run.repo_id)
        if repo is None:
            run.status = "failed"
            run.error = "仓库记录不存在"
            run.finished_at = datetime.utcnow()
            await db.commit()
            bus.publish(run_id, {"event": "error", "data": {"message": "仓库记录不存在"}})
            bus.publish(run_id, {"event": "done", "data": {"status": "failed", "result": None}})
            return

        state = {"status": "running", "current_step": -1, "steps": blank_steps(),
                 "logs": [], "stats": {}, "result": None, "error": None}
        _live_states[run_id] = state
        run.status = "running"
        run.steps = state["steps"]
        flag_modified(run, "steps")
        await db.commit()

        try:
            if is_cancelled(run_id):
                raise RunCancelled("运行已取消")

            async def step1():
                git_service.resolve_ref(repo.path, run.base_ref)
                head_sha = git_service.resolve_ref(repo.path, run.head_ref)
                commits = git_service.list_commits(repo.path, run.base_ref, run.head_ref)
                refs = git_service.list_refs(repo.path)
                _log(run_id, state, "step", "范围",
                     f"解析 {run.base_ref}..{run.head_ref}，头部 {head_sha[:7]}")
                _log(run_id, state, "step", "提交", f"范围内 {len(commits)} 个提交")
                return {"head_sha": head_sha, "commits": commits,
                        "branch": refs["default_branch"] or "main"}

            range_info = await _run_step(run_id, run, state, db, 0, step1)

            async def step2():
                cs = git_service.collect_diff(repo.path, run.base_ref, run.head_ref,
                                              max_lines=_PIPELINE_MAX_LINES)
                state["stats"] = cs["stats"]
                _log(run_id, state, "step", "规模",
                     f"{cs['stats']['files']} 个文件，+{cs['stats']['added']}/-{cs['stats']['removed']} 行，"
                     f"{cs['stats']['modules']} 个模块")
                for m in cs["modules"]:
                    _log(run_id, state, "step", "模块", f"{m['name']}（{len(m['files'])} 个文件）")
                return cs

            changeset = await _run_step(run_id, run, state, db, 1, step2)

            async def step3():
                total = {"added": 0, "removed": 0, "changed": 0}
                signals: list[dict] = []
                degraded = 0
                for f in changeset["files"]:
                    if f.get("binary"):
                        f["ast"] = None
                        f["contract_signals"] = []
                        continue
                    base_src = (git_service.show_file(repo.path, run.base_ref, f["path"])
                                if f["status"] != "a" else "")
                    head_src = (git_service.show_file(repo.path, run.head_ref, f["path"])
                                if f["status"] != "d" else "")
                    parsed = parser_service.parse_file_pair(f["path"], base_src, head_src,
                                                            f.get("lines", []))
                    f["ast"] = parsed
                    f["contract_signals"] = parsed["contract_signals"]
                    if parsed["degraded"]:
                        degraded += 1
                    for key in total:
                        total[key] += len(parsed["symbols"].get(key, []))
                    signals.extend(parsed["contract_signals"])
                changeset["contract_signals"] = signals
                _log(run_id, state, "step", "符号",
                     f"新增 {total['added']} · 修改 {total['changed']} · 删除 {total['removed']}")
                for sig in signals:
                    _log(run_id, state, "warn", "契约", sig["message"])
                if degraded:
                    _log(run_id, state, "warn", "降级",
                         f"{degraded} 个文件未解析到符号级（已降级为文件级信号）")
                return {"total": total, "signals": signals, "degraded": degraded}

            await _run_step(run_id, run, state, db, 2, step3)

            async def step4():
                outcome = await llm_service.rewrite_changes(
                    changeset, cancel_check=lambda: is_cancelled(run_id))
                if outcome["all_failed"]:
                    raise ServiceError("LLM 改写全部失败，运行终止")
                for cl in outcome["chunk_logs"]:
                    if cl["ok"]:
                        _log(run_id, state, "step", "分块", f"{cl['chunk']}：生成 {cl['features']} 个功能点")
                    else:
                        _log(run_id, state, "warn", "分块", f"{cl['chunk']}：改写失败（{cl['error'][:60]}）")
                for item in outcome["lowConfidence"]:
                    _log(run_id, state, "warn", "复核", item)
                _log(run_id, state, "step", "改写",
                     f"功能点 {len(outcome['features'])} 个 · 置信度 {outcome['llm']['confidence']} · "
                     f"术语命中 {outcome['llm']['glossaryHits']} 处")
                return outcome

            outcome = await _run_step(run_id, run, state, db, 3, step4)

            async def step5():
                meta = {
                    "runId": run.id,
                    "repoName": repo.name,
                    "version": run.version_label,
                    "branch": range_info["branch"],
                    "headShort": range_info["head_sha"][:7],
                    "range": f"{run.base_ref}..{run.head_ref}",
                    "trigger": "手动触发",
                    "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "stats": changeset["stats"],
                    "modules": [m["name"] for m in changeset["modules"]],
                    "pipeline": [{"name": s["name"], "ok": s["status"] == "done",
                                  "ms": s.get("duration_ms", 0)} for s in state["steps"]],
                }
                result = {
                    "features": outcome["features"],
                    "highlights": outcome["highlights"],
                    "lowConfidence": outcome["lowConfidence"],
                    "llm": outcome["llm"],
                    "contractSignals": changeset["contract_signals"],
                    "meta": meta,
                }
                opts = {"tone": run.tone, "mask": run.mask}
                checklist = renderers.render_checklist(result, opts)
                document = renderers.render_document(result, opts)
                trace, _sizes = renderers.render_trace_stable(result, opts, base_sizes={
                    "checklist": len(checklist.encode("utf-8")),
                    "document": len(document.encode("utf-8")),
                })
                files = {"checklist.csv": checklist, "product-doc.md": document, "trace.json": trace}
                written = archive_service.write_artifacts(_archive_root, run.version_label, files)
                for kind, filename in (("checklist", "checklist.csv"),
                                       ("document", "product-doc.md"),
                                       ("trace", "trace.json")):
                    path = written[filename]
                    db.add(Artifact(run_id=run.id, kind=kind, filename=filename,
                                    path=str(path), bytes=path.stat().st_size))
                _log(run_id, state, "step", "归档",
                     f"{archive_service.archive_dir_for(_archive_root, run.version_label)}")
                return result

            result = await _run_step(run_id, run, state, db, 4, step5)

            final_status = "degraded" if outcome["lowConfidence"] else "succeeded"
            state["status"] = final_status
            state["result"] = result
            state["current_step"] = len(state["steps"])
            run.status = final_status
            run.current_step = len(state["steps"])
            run.steps = state["steps"]
            flag_modified(run, "steps")
            run.logs = state["logs"]
            flag_modified(run, "logs")
            run.stats = changeset["stats"]
            run.result = result
            run.finished_at = datetime.utcnow()
            await db.commit()
            bus.publish(run_id, {"event": "progress", "data": {"percent": 100}})
            bus.publish(run_id, {"event": "done",
                                 "data": {"status": final_status, "result": result}})
        except RunCancelled:
            await _finish_cancelled(db, run, state, run_id)
        except Exception as exc:  # noqa: BLE001 —— 运行失败需完整落库并广播
            logger.exception("运行 %s 失败", run_id)
            await _finish_failed(db, run, state, run_id, exc)
