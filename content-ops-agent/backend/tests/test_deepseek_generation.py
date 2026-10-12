import json

import httpx
import pytest

from app.services.generation import DeepSeekGenerator


@pytest.mark.asyncio
async def test_generator_sends_evidence_and_returns_assets() -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"assets":[{"kind":"announcement","content":{"title":"搜索上线"},"source_ids":["s1"]}]}'}}]})

    generator = DeepSeekGenerator("key", "https://api.deepseek.com", "deepseek-chat", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assets = await generator.generate("搜索", [{"source_id": "s1", "text": "搜索功能上线"}])

    assert assets[0]["source_ids"] == ["s1"]
    assert "不得使用证据外事实" in captured["messages"][0]["content"]
