import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_parse_text(client, monkeypatch):
    async def fake_analyze(*args, **kwargs):
        return {"新增功能": ["A"], "变更与优化": [], "注意事项": [], "风险提示": []}
    monkeypatch.setattr("app.api.generator.analyze_document", fake_analyze)
    login = client.post("/api/auth/login", data={"username": "editor", "password": "editor123"})
    token = login.json()["access_token"]
    response = client.post(
        "/api/parse",
        data={"title": "T", "content": "C"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["新增功能"] == ["A"]


def test_generate(client, monkeypatch):
    async def fake_generate(*args, **kwargs):
        return {"title": "R", "content": "C", "audience": "网点管理员", "material_type": "version_announcement"}
    monkeypatch.setattr("app.api.generator.generate_material", fake_generate)
    response = client.post("/api/generate", json={
        "title": "T",
        "analysis": {"新增功能": ["A"]},
        "audience": "网点管理员",
        "material_type": "version_announcement",
    })
    assert response.status_code == 200
    assert response.json()["title"] == "R"
