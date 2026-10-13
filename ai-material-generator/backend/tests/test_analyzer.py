import json
import pytest
from app.services.analyzer import analyze_document


@pytest.mark.asyncio
async def test_analyze_document(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return json.dumps({
            "新增功能": ["异常件一键上报"],
            "变更与优化": ["运单批量导入"],
            "注意事项": ["需升级至 V3.2.0"],
            "风险提示": ["数据存在延迟"],
        })

    monkeypatch.setattr("app.services.analyzer._chat", fake_chat)
    result = await analyze_document("网点管家 V3.2.0", "本次新增异常件一键上报功能。")
    assert result["新增功能"] == ["异常件一键上报"]
    assert result["变更与优化"] == ["运单批量导入"]
