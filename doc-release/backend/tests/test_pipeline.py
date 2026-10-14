import json

import pytest
from sqlalchemy import func, select

from app.models import Artifact, Repo, Run
from app.models.run import blank_steps
from app.services import archive_service, git_service, llm_service, pipeline_service
from tests.gitfix import commit, init_repo, tag, write_files


@pytest.fixture
def work_repo(tmp_path):
    r = init_repo(tmp_path)
    write_files(r, {"src/a.ts": "export const A = 1;\n"})
    commit(r, "init")
    tag(r, "v1.0.0")
    write_files(r, {"src/a.ts": "export const A = 2;\nexport function run() {\n  return A;\n}\n"})
    commit(r, "feat: a", date="2026-08-21 09:00:00 +0800")
    tag(r, "v1.1.0")
    return r


async def _make_run(db_session, repo_path, version="v1.1.0", base="v1.0.0"):
    repo = Repo(name="work", path=str(repo_path), is_sample=False)
    db_session.add(repo)
    await db_session.commit()
    run = Run(repo_id=repo.id, base_ref=base, head_ref=version, version_label=version)
    run.steps = blank_steps()
    db_session.add(run)
    await db_session.commit()
    return run


def test_delete_archive_requires_owner(tmp_path):
    root = tmp_path / "ar"
    archive_service.write_artifacts(root, "v1.0.0", {
        "trace.json": json.dumps({"runId": "r1"}), "checklist.csv": "x"})
    assert archive_service.delete_archive_if_owned(root, "v1.0.0", "r2") is False
    assert archive_service.archive_dir_for(root, "v1.0.0").exists()
    assert archive_service.delete_archive_if_owned(root, "v1.0.0", "r1") is True
    assert not archive_service.archive_dir_for(root, "v1.0.0").exists()


async def test_execute_run_success(work_repo, db_session, archive_root):
    run = await _make_run(db_session, work_repo)
    q = pipeline_service.bus.subscribe(run.id)
    await pipeline_service.execute_run(run.id)
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    pipeline_service.bus.unsubscribe(run.id, q)

    await db_session.refresh(run)
    assert run.status == "succeeded"
    assert [s["status"] for s in run.steps] == ["done"] * 5
    assert all(s.get("duration_ms") is not None for s in run.steps)
    assert run.result["features"][0]["title"] == "自动生成的功能点"  # conftest 打桩输出
    assert run.result["meta"]["range"] == "v1.0.0..v1.1.0"
    assert run.result["meta"]["branch"] == "main"
    assert run.result["meta"]["modules"] == ["src"]

    count = (await db_session.execute(select(func.count()).select_from(Artifact))).scalar_one()
    assert count == 3

    target = archive_root / "docs" / "release" / "v1.1.0"
    assert (target / "checklist.csv").exists()
    assert (target / "product-doc.md").exists()
    trace = json.loads((target / "trace.json").read_text(encoding="utf-8"))
    assert trace["runId"] == run.id
    assert {a["kind"]: a["bytes"] for a in trace["artifacts"]} == {
        "checklist": (target / "checklist.csv").stat().st_size,
        "document": (target / "product-doc.md").stat().st_size,
        "trace": (target / "trace.json").stat().st_size,
    }

    names = [e["event"] for e in events]
    assert names.count("step") >= 10          # 每步 active + done
    assert names[-1] == "done"
    assert events[-1]["data"]["status"] == "succeeded"


async def test_execute_run_llm_all_failed(work_repo, db_session, monkeypatch):
    async def bad_chat(system, user):
        raise RuntimeError("网关不可达")

    monkeypatch.setattr(llm_service, "_chat", bad_chat)
    run = await _make_run(db_session, work_repo)
    await pipeline_service.execute_run(run.id)
    await db_session.refresh(run)
    assert run.status == "failed"
    assert "LLM 改写全部失败" in run.error
    assert run.steps[3]["status"] == "failed"
    assert run.steps[4]["status"] == "pending"
    assert run.logs and run.logs[-1]["channel"] == "error"


async def test_execute_run_cancelled_before_start(work_repo, db_session):
    run = await _make_run(db_session, work_repo)
    pipeline_service.cancel_run(run.id)
    await pipeline_service.execute_run(run.id)
    await db_session.refresh(run)
    assert run.status == "cancelled"
    assert all(s["status"] == "pending" for s in run.steps)
    assert any("取消" in log["tag"] for log in run.logs)


async def test_execute_run_cancelled_between_steps(work_repo, db_session, monkeypatch):
    run = await _make_run(db_session, work_repo)
    original = git_service.list_refs

    def cancelling_list_refs(path):
        pipeline_service.cancel_run(run.id)   # 在步骤 1 执行中触发取消
        return original(path)

    monkeypatch.setattr(git_service, "list_refs", cancelling_list_refs)
    await pipeline_service.execute_run(run.id)
    await db_session.refresh(run)
    assert run.status == "cancelled"
    assert run.steps[0]["status"] == "done"       # 步骤 1 正常完成
    assert all(s["status"] == "pending" for s in run.steps[1:])
