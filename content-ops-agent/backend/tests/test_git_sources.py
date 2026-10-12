from fastapi.testclient import TestClient


def test_import_git_release_context() -> None:
    from app.main import app

    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "发布", "theme": "搜索", "audience": "客户", "tone": "专业"}).json()
        response = client.post(
            f"/api/projects/{project['id']}/sources/git",
            json={"repository": "acme/product", "release": "v1.2.0", "content": "新增智能搜索"},
        )

    assert response.status_code == 201
    assert response.json()["source_type"] == "git"
