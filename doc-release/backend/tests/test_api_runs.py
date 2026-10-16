import asyncio
import json as jsonlib

import pytest

from tests.gitfix import commit, init_repo, tag, write_files


@pytest.fixture
def sample_dir(tmp_path):
    r = init_repo(tmp_path)
    write_files(r, {"src/a.ts": "export const A = 1;\n"})
    commit(r, "init")
    tag(r, "v1.0.0")
    write_files(r, {"src/a.ts": "export const A = 2;\nexport function run() {\n  return A;\n}\n"})
    commit(r, "feat", date="2026-08-22 09:00:00 +0800")
    tag(r, "v1.1.0")
    return r


async def _register(client, path) -> int:
    return (await client.post("/api/repos", json={"path": str(path)})).json()["id"]


async def _wait_terminal(client, run_id, timeout=15.0) -> dict:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        data = (await client.get(f"/api/runs/{run_id}")).json()
        if data["status"] not in ("pending", "running"):
            return data
        await asyncio.sleep(0.05)
    raise AssertionError("运行未在超时内结束")


def _slow_chat(seconds: float):
    async def chat(system, user):
        await asyncio.sleep(seconds)
        return jsonlib.dumps({"features": [], "highlights": [], "confidence": 0.5},
                             ensure_ascii=False)
    return chat


async def test_run_full_flow(client, sample_dir):
    repo_id = await _register(client, sample_dir)
    created = await client.post("/api/runs", json={
        "repo_id": repo_id, "base_ref": "v1.0.0", "head_ref": "v1.1.0",
        "version_label": "v1.1.0", "tone": "business", "mask": False})
    assert created.status_code == 201
    run_id = created.json()["id"]

    detail = await _wait_terminal(client, run_id)
    assert detail["status"] == "succeeded"
    assert detail["repo_name"] == "repo"
    assert [a["kind"] for a in detail["artifacts"]] == ["checklist", "document", "trace"]

    art = await client.get(f"/api/runs/{run_id}/artifacts/checklist")
    assert art.status_code == 200
    assert art.text.startswith("\ufeff")
    assert "自动生成的功能点" in art.text

    doc = await client.get(f"/api/runs/{run_id}/artifacts/document", params={"tone": "tech"})
    assert doc.status_code == 200 and "技术说明" in doc.text

    dl = await client.get(f"/api/runs/{run_id}/artifacts/document/download")
    assert "attachment" in dl.headers["content-disposition"]

    listing = (await client.get("/api/runs")).json()
    assert listing["total"] == 1
    assert listing["items"][0]["status"] == "succeeded"
    assert "logs" not in listing["items"][0]        # 列表不返回重型字段

    trace = jsonlib.loads((await client.get(f"/api/runs/{run_id}/artifacts/trace")).text)
    assert trace["runId"] == run_id


async def test_run_validation_and_duplicate(client, sample_dir, monkeypatch):
    from app.services import llm_service

    monkeypatch.setattr(llm_service, "_chat", _slow_chat(0.4))
    repo_id = await _register(client, sample_dir)
    bad = await client.post("/api/runs", json={
        "repo_id": repo_id, "base_ref": "nope", "head_ref": "v1.1.0"})
    assert bad.status_code == 422

    payload = {"repo_id": repo_id, "base_ref": "v1.0.0", "head_ref": "v1.1.0"}
    first = await client.post("/api/runs", json=payload)
    assert first.status_code == 201
    dup = await client.post("/api/runs", json=payload)
    assert dup.status_code == 409

    detail = await _wait_terminal(client, first.json()["id"])
    assert detail["status"] == "succeeded"
    second = await client.post("/api/runs", json=payload)
    assert second.status_code == 201
    await _wait_terminal(client, second.json()["id"])


async def test_cancel_running(client, sample_dir, monkeypatch):
    from app.services import llm_service

    monkeypatch.setattr(llm_service, "_chat", _slow_chat(1.0))
    repo_id = await _register(client, sample_dir)
    run_id = (await client.post("/api/runs", json={
        "repo_id": repo_id, "base_ref": "v1.0.0", "head_ref": "v1.1.0"})).json()["id"]
    assert (await client.post(f"/api/runs/{run_id}/cancel")).status_code == 200
    detail = await _wait_terminal(client, run_id)
    assert detail["status"] == "cancelled"
    assert (await client.post(f"/api/runs/{run_id}/cancel")).status_code == 409


async def test_artifacts_guards(client, sample_dir, monkeypatch):
    from app.services import llm_service

    monkeypatch.setattr(llm_service, "_chat", _slow_chat(0.5))
    repo_id = await _register(client, sample_dir)
    run_id = (await client.post("/api/runs", json={
        "repo_id": repo_id, "base_ref": "v1.0.0", "head_ref": "v1.1.0"})).json()["id"]
    assert (await client.get(f"/api/runs/{run_id}/artifacts/checklist")).status_code == 409
    assert (await client.get(f"/api/runs/{run_id}/artifacts/report")).status_code == 422
    assert (await client.get("/api/runs/unknown-id/artifacts/checklist")).status_code == 404
    await _wait_terminal(client, run_id)


async def test_sse_live_and_finished(client, sample_dir, monkeypatch):
    from app.services import llm_service

    monkeypatch.setattr(llm_service, "_chat", _slow_chat(0.3))
    repo_id = await _register(client, sample_dir)
    run_id = (await client.post("/api/runs", json={
        "repo_id": repo_id, "base_ref": "v1.0.0", "head_ref": "v1.1.0"})).json()["id"]

    events: list[str] = []
    guard = 0
    async with client.stream("GET", f"/api/runs/{run_id}/events") as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        async for line in resp.aiter_lines():
            guard += 1
            assert guard < 2000
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
            if events and events[-1] == "done":
                break
    assert events[0] == "snapshot"
    assert "step" in events and "log" in events
    assert events[-1] == "done"

    await _wait_terminal(client, run_id)
    events2: list[str] = []
    async with client.stream("GET", f"/api/runs/{run_id}/events") as resp:
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                events2.append(line.split(":", 1)[1].strip())
            if events2 and events2[-1] == "done":
                break
    assert events2 == ["snapshot", "done"]


async def test_delete_run_and_archive(client, sample_dir):
    repo_id = await _register(client, sample_dir)
    run_id = (await client.post("/api/runs", json={
        "repo_id": repo_id, "base_ref": "v1.0.0", "head_ref": "v1.1.0",
        "version_label": "v9.9.9"})).json()["id"]
    await _wait_terminal(client, run_id)
    assert (await client.delete(f"/api/runs/{run_id}")).status_code == 200
    assert (await client.get(f"/api/runs/{run_id}")).status_code == 404
    assert (await client.delete(f"/api/runs/{run_id}")).status_code == 404
