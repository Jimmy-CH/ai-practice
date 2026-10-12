from fastapi.testclient import TestClient


def test_approved_asset_can_create_mock_delivery() -> None:
    from app.main import app

    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "发布", "theme": "搜索", "audience": "客户", "tone": "专业"}).json()
        client.post(f"/api/projects/{project['id']}/sources/text", json={"name": "说明", "content": "新增搜索"})
        asset = client.post(f"/api/projects/{project['id']}/generate").json()[0]
        client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "approved"})
        response = client.post(f"/api/assets/{asset['id']}/deliveries")

    assert response.status_code == 201
    assert response.json()["status"] == "completed"
