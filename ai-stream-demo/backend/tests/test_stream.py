from types import SimpleNamespace

import httpx
import pytest

import main


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class FakeStream:
    def __init__(self, contents):
        self._iterator = iter(contents)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            content = next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration
        return SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=content))]
        )


class FakeCompletions:
    def __init__(self, contents=None, error=None):
        self._contents = contents or []
        self._error = error

    async def create(self, **kwargs):
        if self._error is not None:
            raise self._error
        return FakeStream(self._contents)


class FakeClient:
    def __init__(self, contents=None, error=None):
        self.chat = SimpleNamespace(
            completions=FakeCompletions(contents=contents, error=error)
        )


async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_cors_preflight(client):
    resp = await client.options(
        "/api/stream",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5500"


async def test_stream_happy_path(client, monkeypatch):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(main, "get_client", lambda: FakeClient(["你", "好"]))

    resp = await client.post(
        "/api/stream",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert '"你"' in body
    assert '"好"' in body
    assert body.index('"你"') < body.index('"好"')
    assert body.rstrip().endswith("data: [DONE]")


async def test_stream_upstream_error_still_done(client, monkeypatch):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        main,
        "get_client",
        lambda: FakeClient(error=RuntimeError("upstream boom")),
    )

    resp = await client.post(
        "/api/stream",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert resp.status_code == 200
    body = resp.text
    assert '"error"' in body
    assert "upstream boom" in body
    assert body.rstrip().endswith("data: [DONE]")


async def test_stream_missing_api_key_returns_json(client, monkeypatch):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "")

    resp = await client.post(
        "/api/stream",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert resp.status_code == 500
    assert resp.headers["content-type"].startswith("application/json")
    assert "DEEPSEEK_API_KEY" in resp.json()["detail"]
