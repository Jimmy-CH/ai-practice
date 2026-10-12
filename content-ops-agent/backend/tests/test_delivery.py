from fastapi.testclient import TestClient


def test_download_requires_approved_asset() -> None:
    from app.main import app

    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "发布", "theme": "智能搜索", "audience": "客户", "tone": "专业"}).json()
        client.post(f"/api/projects/{project['id']}/sources/text", json={"name": "说明", "content": "新增智能搜索"})
        asset = client.post(f"/api/projects/{project['id']}/generate").json()[0]
        denied = client.get(f"/api/assets/{asset['id']}/download?format=html")
        approved = client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "approved"})
        response = client.get(f"/api/assets/{asset['id']}/download?format=html")

    assert denied.status_code == 409
    assert approved.status_code == 200
    assert response.status_code == 200
    assert response.json()["format"] == "html"
