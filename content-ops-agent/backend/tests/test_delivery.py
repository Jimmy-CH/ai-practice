from fastapi.testclient import TestClient


def test_download_requires_approved_asset() -> None:
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/assets/missing/download?format=html")

    assert response.status_code == 404
    assert response.json()["detail"] == "资产不存在"
