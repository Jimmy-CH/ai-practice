import asyncio
import json
import uuid

from app.config import settings
from app.database import async_session_factory
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services import llm_client
from app.services.stream_manager import manager


def _parse(event_text: str) -> tuple[str, dict]:
    lines = [line for line in event_text.split("\n") if line]
    event = next(line[7:] for line in lines if line.startswith("event: "))
    data = next(line[6:] for line in lines if line.startswith("data: "))
    return event, json.loads(data)


async def _seed_message(status="streaming"):
    async with async_session_factory() as db:
        user = User(username=f"u{uuid.uuid4().hex[:12]}", password_hash="x")
        db.add(user)
        await db.flush()
        conv = Conversation(user_id=user.id)
        db.add(conv)
        await db.flush()
        msg = Message(conversation_id=conv.id, role="assistant", content="", status=status)
        db.add(msg)
        await db.commit()
        return user.id, conv.id, msg.id


async def test_normal_stream_and_persist(monkeypatch):
    async def fake_stream(messages, model=None):
        for delta in ["你", "好"]:
            yield delta

    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)

    _, conv_id, mid = await _seed_message()
    manager.start(mid, conv_id, 1, [{"role": "user", "content": "hi"}])
    events = [event async for event in manager.subscribe(manager.get(mid), -1) if not event.startswith(":")]

    parsed = [_parse(event) for event in events]
    assert [name for name, _ in parsed] == ["delta", "delta", "done"]
    assert parsed[0][1]["seq"] == 0 and parsed[1][1]["content"] == "好"
    assert parsed[-1][1]["status"] == "done"

    async with async_session_factory() as db:
        msg = await db.get(Message, mid)
        assert msg.status == "done" and msg.content == "你好"


async def test_upstream_error_emits_error_event(monkeypatch):
    async def failing(messages, model=None):
        yield "A"
        raise llm_client.UpstreamError("upstream_network", "ReadError: boom")

    monkeypatch.setattr(llm_client, "stream_chat", failing)

    _, conv_id, mid = await _seed_message()
    manager.start(mid, conv_id, 1, [{"role": "user", "content": "hi"}])
    names = [
        _parse(event)[0]
        for event in [e async for e in manager.subscribe(manager.get(mid), -1) if not e.startswith(":")]
    ]
    assert names == ["delta", "error"]

    async with async_session_factory() as db:
        msg = await db.get(Message, mid)
        assert msg.status == "failed" and msg.content == "A" and "boom" in (msg.error or "")


async def test_stop_persists_partial_content(monkeypatch):
    gate = asyncio.Event()

    async def slow(messages, model=None):
        yield "A"
        await gate.wait()
        yield "B"

    monkeypatch.setattr(llm_client, "stream_chat", slow)

    _, conv_id, mid = await _seed_message()
    manager.start(mid, conv_id, 1, [{"role": "user", "content": "hi"}])
    agen = manager.subscribe(manager.get(mid), -1)
    assert "A" in await agen.__anext__()
    await manager.stop(mid)
    rest = [_parse(e) async for e in agen if not e.startswith(":")]
    assert rest[-1][1]["status"] == "stopped"

    async with async_session_factory() as db:
        msg = await db.get(Message, mid)
        assert msg.status == "stopped" and msg.content == "A"


async def test_resume_from_skips_received(monkeypatch):
    gate = asyncio.Event()

    async def slow(messages, model=None):
        yield "A"
        yield "B"
        await gate.wait()
        yield "C"

    monkeypatch.setattr(llm_client, "stream_chat", slow)

    _, conv_id, mid = await _seed_message()
    manager.start(mid, conv_id, 1, [{"role": "user", "content": "hi"}])
    await asyncio.sleep(0.05)
    gate.set()
    events = [_parse(e) async for e in manager.subscribe(manager.get(mid), 1) if not e.startswith(":")]
    assert [data["seq"] for name, data in events if name == "delta"] == [2]


async def test_heartbeat_emits_ping(monkeypatch):
    monkeypatch.setattr(settings, "HEARTBEAT_SECONDS", 0.05)
    gate = asyncio.Event()

    async def slow(messages, model=None):
        yield "A"
        await gate.wait()

    monkeypatch.setattr(llm_client, "stream_chat", slow)

    _, conv_id, mid = await _seed_message()
    manager.start(mid, conv_id, 1, [{"role": "user", "content": "hi"}])
    agen = manager.subscribe(manager.get(mid), 0)
    assert (await agen.__anext__()).startswith(": ping")
    await manager.stop(mid)


async def test_running_message_flushes_streaming_status(monkeypatch):
    """运行中落库必须是 streaming：前端刷新续传与启动恢复都依赖这个字面量。"""
    monkeypatch.setattr(settings, "FLUSH_INTERVAL_SECONDS", 0.0)
    gate = asyncio.Event()

    async def slow(messages, model=None):
        yield "A"
        await gate.wait()

    monkeypatch.setattr(llm_client, "stream_chat", slow)

    _, conv_id, mid = await _seed_message(status="")
    manager.start(mid, conv_id, 1, [{"role": "user", "content": "hi"}])

    msg = None
    for _ in range(100):
        await asyncio.sleep(0.02)
        async with async_session_factory() as db:
            msg = await db.get(Message, mid)
        if msg is not None and msg.content == "A":
            break

    assert msg is not None and msg.content == "A"
    assert msg.status == "streaming", msg.status
    await manager.stop(mid)
