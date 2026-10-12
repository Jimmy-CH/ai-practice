from fastapi.testclient import TestClient


def test_generate_three_traced_assets() -> None:
    from app.main import app

    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "发布", "theme": "智能搜索", "audience": "客户", "tone": "专业"}).json()
        client.post(f"/api/projects/{project['id']}/sources/text", json={"name": "说明", "content": "新增智能搜索，支持自然语言检索"})
        response = client.post(f"/api/projects/{project['id']}/generate")

    assert response.status_code == 201
    assert {asset["kind"] for asset in response.json()} == {"announcement", "faq", "poster"}
    assert all(asset["citations"] for asset in response.json())
