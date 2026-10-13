import pytest


@pytest.mark.asyncio
async def test_login_success(client):
    r = await client.post("/api/auth/login", data={"username": "editor", "password": "editor123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["role"] == "editor"


@pytest.mark.asyncio
async def test_login_failure(client):
    r = await client.post("/api/auth/login", data={"username": "editor", "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_success(client, editor_token):
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {editor_token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "editor"
