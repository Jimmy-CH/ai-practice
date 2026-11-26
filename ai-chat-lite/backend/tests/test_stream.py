import asyncio
import json

from app.config import settings
from app.database import async_session_factory
from app.models.message import Message
from app.services import chat_service, llm_client
from app.services.stream_manager import manager
from tests.test_auth import _register_and_login


async def _setup(client, username="alice"):
    token = await _register_and_login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    cid = (await client.post("/api/conversations", headers=headers)).json()["id"]
    return headers, cid


class SSEReader:
    def __init__(self, response):
        self._it = response.aiter_lines()

    async def next_event(self):
        event = {}
        while True:
            try:
                line = await self._it.__anext__()
            except StopAsyncIteration:
                return event or None
            if line == "":
                if event:
                    return event
            elif line.startswith("event: "):
                event["event"] = line[7:]
            elif line.startswith("data: "):
                event["data"] = json.loads(line[6:])
            elif line.startswith("id: "):
                event["id"] = int(line[4:])

    async def collect(self):
        events = []
        while True:
            event = await self.next_event()
            if event is None:
                return events
            events.append(event)


async def test_normal_stream_persists(client, monkeypatch):
    async def fake_stream(messages, model=None):
        for delta in ["你", "好"]:
            yield delta

    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)

    headers, cid = await _setup(client)
    resp = await client.post(f"/api/conversations/{cid}/messages", json={"content": "你好"}, headers=headers)
    assert resp.status_code == 201
    mid = resp.json()["assistant_message"]["id"]

    async with client.stream("GET", f"/api/messages/{mid}/stream", headers=headers) as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        events = await SSEReader(stream).collect()

    assert [e["event"] for e in events] == ["delta", "delta", "done"]
    assert [e["data"]["seq"] for e in events[:2]] == [0, 1]
    assert events[-1]["data"]["content"] == "你好"

    async with async_session_factory() as db:
        msg = await db.get(Message, mid)
        assert msg.status == "done" and msg.content == "你好"


async def test_conversation_title_auto_filled(client, monkeypatch):
    async def fake_stream(messages, model=None):
        yield "ok"

    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)

    headers, cid = await _setup(client)
    await client.post(f"/api/conversations/{cid}/messages", json={"content": "帮我写一首诗"}, headers=headers)
    items = (await client.get("/api/conversations", headers=headers)).json()["items"]
    assert items[0]["title"] == "帮我写一首诗"


async def test_upstream_failure_emits_error_and_marks_failed(client, monkeypatch):
    async def failing(messages, model=None):
        yield "A"
        raise llm_client.UpstreamError("upstream_http", "HTTP 500")

    monkeypatch.setattr(llm_client, "stream_chat", failing)

    headers, cid = await _setup(client)
    mid = (
        await client.post(f"/api/conversations/{cid}/messages", json={"content": "hi"}, headers=headers)
    ).json()["assistant_message"]["id"]
    async with client.stream("GET", f"/api/messages/{mid}/stream", headers=headers) as stream:
        events = await SSEReader(stream).collect()
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["code"] == "upstream_http"


async def test_stop_returns_done_stopped(client, monkeypatch):
    gate = asyncio.Event()

    async def slow(messages, model=None):
        yield "A"
        await gate.wait()

    monkeypatch.setattr(llm_client, "stream_chat", slow)

    headers, cid = await _setup(client)
    mid = (
        await client.post(f"/api/conversations/{cid}/messages", json={"content": "hi"}, headers=headers)
    ).json()["assistant_message"]["id"]

    await asyncio.sleep(0.1)
    stop_resp = await client.post(f"/api/messages/{mid}/stop", headers=headers)
    assert stop_resp.json()["status"] == "stopped"

    async with client.stream("GET", f"/api/messages/{mid}/stream", headers=headers) as stream:
        events = await SSEReader(stream).collect()
    assert events[-1]["event"] == "done" and events[-1]["data"]["status"] == "stopped"

    async with async_session_factory() as db:
        msg = await db.get(Message, mid)
        assert msg.status == "stopped" and msg.content == "A"


async def test_resume_from_skips_received(client, monkeypatch):
    async def fake_stream(messages, model=None):
        for delta in ["A", "B", "C"]:
            yield delta

    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)

    headers, cid = await _setup(client)
    mid = (
        await client.post(f"/api/conversations/{cid}/messages", json={"content": "hi"}, headers=headers)
    ).json()["assistant_message"]["id"]
    await asyncio.sleep(0.1)

    async with client.stream(
        "GET", f"/api/messages/{mid}/stream?resume_from=1", headers=headers
    ) as stream:
        events = await SSEReader(stream).collect()
    seqs = [e["data"]["seq"] for e in events if e["event"] == "delta"]
    # resume_from 是“已收到的最后序号”，跳过 seq <= resume_from
    assert seqs == [2]


async def test_resume_out_of_range_400(client, monkeypatch):
    async def fake_stream(messages, model=None):
        yield "A"

    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)
    headers, cid = await _setup(client)
    mid = (
        await client.post(f"/api/conversations/{cid}/messages", json={"content": "hi"}, headers=headers)
    ).json()["assistant_message"]["id"]
    await asyncio.sleep(0.1)
    resp = await client.get(f"/api/messages/{mid}/stream?resume_from=99", headers=headers)
    assert resp.status_code == 400


async def test_concurrency_409(client, monkeypatch):
    gate = asyncio.Event()

    async def slow(messages, model=None):
        yield "A"
        await gate.wait()

    monkeypatch.setattr(llm_client, "stream_chat", slow)

    headers, cid = await _setup(client)
    await client.post(f"/api/conversations/{cid}/messages", json={"content": "one"}, headers=headers)
    resp = await client.post(f"/api/conversations/{cid}/messages", json={"content": "two"}, headers=headers)
    assert resp.status_code == 409


async def test_context_trimming_payload(client, monkeypatch):
    captured = {}

    async def fake_stream(messages, model=None):
        captured["messages"] = messages
        yield "ok"

    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)
    monkeypatch.setattr(settings, "MAX_CONTEXT_MESSAGES", 3)

    headers, cid = await _setup(client)
    for i in range(6):
        resp = await client.post(
            f"/api/conversations/{cid}/messages", json={"content": f"q{i}"}, headers=headers
        )
        assert resp.status_code == 201
        await asyncio.sleep(0.05)

    await asyncio.sleep(0.1)
    assert captured["messages"][0]["role"] == "system"
    assert len(captured["messages"]) == 4  # system + 最近 3 条
    assert captured["messages"][-1]["content"] == "q5"


async def test_terminal_without_session_synthesizes_done(client, monkeypatch):
    async def fake_stream(messages, model=None):
        yield "A"

    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)
    headers, cid = await _setup(client)
    mid = (
        await client.post(f"/api/conversations/{cid}/messages", json={"content": "hi"}, headers=headers)
    ).json()["assistant_message"]["id"]
    await asyncio.sleep(0.1)
    await manager.ashutdown()  # 模拟会话已被清理 / 进程重启
    async with client.stream("GET", f"/api/messages/{mid}/stream", headers=headers) as stream:
        events = await SSEReader(stream).collect()
    assert events[-1]["event"] == "done" and events[-1]["data"]["status"] == "done"
    assert events[-1]["data"]["content"] == "A"


async def test_recover_stale_streaming(client):
    headers, cid = await _setup(client)
    async with async_session_factory() as db:
        msg = Message(conversation_id=cid, role="assistant", content="partial", status="streaming")
        db.add(msg)
        await db.commit()
        mid = msg.id
    await chat_service.recover_stale_streaming()
    async with async_session_factory() as db:
        msg = await db.get(Message, mid)
        assert msg.status == "failed" and "重启" in (msg.error or "")


async def test_other_user_message_404(client, monkeypatch):
    async def fake_stream(messages, model=None):
        yield "A"

    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)
    alice_headers, cid = await _setup(client, "alice")
    bob_headers, _ = await _setup(client, "bob")
    mid = (
        await client.post(
            f"/api/conversations/{cid}/messages", json={"content": "hi"}, headers=alice_headers
        )
    ).json()["assistant_message"]["id"]
    resp = await client.get(f"/api/messages/{mid}/stream", headers=bob_headers)
    assert resp.status_code == 404
    assert (await client.post(f"/api/messages/{mid}/stop", headers=bob_headers)).status_code == 404
