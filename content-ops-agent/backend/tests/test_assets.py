from fastapi.testclient import TestClient


def test_list_project_assets() -> None:
    from app.main import app

    with TestClient(app) as client:
        project = client.post('/api/projects', json={'name': '发布', 'theme': '搜索', 'audience': '客户', 'tone': '专业'}).json()
        client.post(f"/api/projects/{project['id']}/sources/text", json={'name': '说明', 'content': '新增搜索'})
        client.post(f"/api/projects/{project['id']}/generate")
        response = client.get(f"/api/projects/{project['id']}/assets")

    assert response.status_code == 200
    assert len(response.json()) == 3
