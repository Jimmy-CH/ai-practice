from fastapi.testclient import TestClient


def test_create_and_list_projects() -> None:
    from app.main import app

    with TestClient(app) as client:
        created = client.post(
            "/api/projects",
            json={"name": "秋季发布", "theme": "智能搜索", "audience": "客户", "tone": "专业"},
        )
        assert created.status_code == 201
        assert created.json()["theme"] == "智能搜索"
        listed = client.get("/api/projects")

    assert [item["id"] for item in listed.json()] == [created.json()["id"]]
