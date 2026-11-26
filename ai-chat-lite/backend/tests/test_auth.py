import pytest
from httpx import AsyncClient

REGISTER = {"username": "alice", "password": "secret123"}


async def _register_and_login(client: AsyncClient, username="alice", password="secret123"):
    await client.post("/api/auth/register", json={"username": username, "password": password})
    resp = await client.post("/api/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]


async def test_register_and_login(client: AsyncClient):
    resp = await client.post("/api/auth/register", json=REGISTER)
    assert resp.status_code == 201
    assert resp.json()["username"] == "alice"

    resp = await client.post("/api/auth/login", json=REGISTER)
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert resp.json()["access_token"]


async def test_duplicate_username(client: AsyncClient):
    await client.post("/api/auth/register", json=REGISTER)
    resp = await client.post("/api/auth/register", json=REGISTER)
    assert resp.status_code == 400


async def test_wrong_password(client: AsyncClient):
    await client.post("/api/auth/register", json=REGISTER)
    resp = await client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


async def test_me_requires_token(client: AsyncClient):
    assert (await client.get("/api/users/me")).status_code == 401


async def test_me_ok(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"


async def test_long_password_truncated_not_crash(client: AsyncClient):
    # 30 个汉字 = 90 字节，超过 bcrypt 的 72 字节上限，验证截断后不报错
    pwd = "密" * 30
    assert (
        await client.post("/api/auth/register", json={"username": "bob", "password": pwd})
    ).status_code == 201
    assert (
        await client.post("/api/auth/login", json={"username": "bob", "password": pwd})
    ).status_code == 200


@pytest.mark.parametrize("username", ["ab", "bad name", "bad-name"])
async def test_invalid_username_rejected(client: AsyncClient, username):
    resp = await client.post("/api/auth/register", json={"username": username, "password": "secret123"})
    assert resp.status_code == 422
