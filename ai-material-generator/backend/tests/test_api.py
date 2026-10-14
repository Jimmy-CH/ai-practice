import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_parse_text(client, monkeypatch):
    async def fake_analyze(*args, **kwargs):
        return {"新增功能": ["A"], "变更与优化": [], "注意事项": [], "风险提示": []}
    monkeypatch.setattr("app.api.generator.analyze_document", fake_analyze)
    monkeypatch.setattr("app.api.generator.generate_all_materials", lambda *args, **kwargs: [])
    login = await client.post("/api/auth/login", data={"username": "editor", "password": "editor123"})
    token = login.json()["access_token"]
    response = await client.post(
        "/api/parse",
        data={"title": "T", "content": "C"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["新增功能"] == ["A"]


@pytest.mark.asyncio
async def test_generate(client, monkeypatch):
    async def fake_generate(*args, **kwargs):
        return {"title": "R", "content": "C", "audience": "网点管理员", "material_type": "version_announcement", "meta": {"audience": "网点管理员", "material_type": "版本宣发稿", "generator": "DeepSeek"}}
    monkeypatch.setattr("app.api.generator.generate_material", fake_generate)
    login = await client.post("/api/auth/login", data={"username": "editor", "password": "editor123"})
    token = login.json()["access_token"]
    response = await client.post(
        "/api/generate",
        json={
            "title": "T",
            "analysis": {"新增功能": ["A"]},
            "audience": "网点管理员",
            "material_type": "version_announcement",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "R"
