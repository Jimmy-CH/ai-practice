async def test_login_success(client):
    response = await client.post("/api/auth/login", json={"username": "editor", "password": "editor123"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "editor" and body["token"]


async def test_login_wrong_password(client):
    response = await client.post("/api/auth/login", json={"username": "editor", "password": "bad"})
    assert response.status_code == 401


async def test_missing_token_rejected(client):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_me_returns_role(client, editor_headers):
    response = await client.get("/api/auth/me", headers=editor_headers)
    assert response.status_code == 200 and response.json()["role"] == "editor"
