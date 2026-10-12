from fastapi.testclient import TestClient


def test_import_text_source_for_project() -> None:
    from app.main import app

    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "发布", "theme": "搜索", "audience": "客户", "tone": "专业"}).json()
        response = client.post(
            f"/api/projects/{project['id']}/sources/text",
            json={"name": "发布说明", "content": "新增智能搜索功能"},
        )

    assert response.status_code == 201
    assert response.json()["content"] == "新增智能搜索功能"
