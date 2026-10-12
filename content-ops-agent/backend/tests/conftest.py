import pytest


@pytest.fixture(autouse=True)
def fake_deepseek_generator(monkeypatch):
    from app.api import generation

    class FakeGenerator:
        def __init__(self, *_args): pass
        async def generate(self, _theme, evidence):
            source_id = evidence[0]["source_id"]
            return [
                {"kind": "announcement", "content": {"title": "测试公告"}, "source_ids": [source_id]},
                {"kind": "faq", "content": {"items": []}, "source_ids": [source_id]},
                {"kind": "poster", "content": {"headline": "测试海报"}, "source_ids": [source_id]},
            ]

    monkeypatch.setattr(generation, "DeepSeekGenerator", FakeGenerator)
    monkeypatch.setattr(generation.settings, "deepseek_api_key", "test-key")
