import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient


def test_cicd_webhook_is_idempotent() -> None:
    from app.config import settings
    from app.main import app

    payload = {"event_id": "build-100", "version": "1.2.0", "summary": "修复搜索"}
    raw_body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(settings.webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    headers = {"X-Signature": f"sha256={signature}", "X-Timestamp": str(int(time.time())), "Content-Type": "application/json"}

    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "发布", "theme": "搜索", "audience": "客户", "tone": "专业"}).json()
        first = client.post(f"/api/projects/{project['id']}/webhooks/cicd", content=raw_body, headers=headers)
        second = client.post(f"/api/projects/{project['id']}/webhooks/cicd", content=raw_body, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
