import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_frontend_index_served(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert 'id="auth-view"' in resp.text
    assert "/app.js" in resp.text


async def test_frontend_static_assets_served(client: AsyncClient):
    for path in ("/app.js", "/markdown.js", "/styles.css"):
        resp = await client.get(path)
        assert resp.status_code == 200, path
