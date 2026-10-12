from fastapi.testclient import TestClient


def test_generate_three_traced_assets(monkeypatch) -> None:
    from app.api import generation
    from app.main import app

    class FakeGenerator:
        def __init__(self, *_args): pass
        async def generate(self, _theme, evidence):
            source_id = evidence[0]["source_id"]
            return [{"kind": "announcement", "content": {"title": "搜索"}, "source_ids": [source_id]}, {"kind": "faq", "content": {"items": []}, "source_ids": [source_id]}, {"kind": "poster", "content": {"headline": "搜索"}, "source_ids": [source_id]}]

    monkeypatch.setattr(generation, "DeepSeekGenerator", FakeGenerator)
    monkeypatch.setattr(generation.settings, "deepseek_api_key", "test-key")
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "发布", "theme": "智能搜索", "audience": "客户", "tone": "专业"}).json()
        client.post(f"/api/projects/{project['id']}/sources/text", json={"name": "说明", "content": "新增智能搜索，支持自然语言检索"})
        response = client.post(f"/api/projects/{project['id']}/generate")

    assert response.status_code == 201
    assert {asset["kind"] for asset in response.json()} == {"announcement", "faq", "poster"}
    assert all(asset["citations"] for asset in response.json())
    assert all(asset["id"] for asset in response.json())
