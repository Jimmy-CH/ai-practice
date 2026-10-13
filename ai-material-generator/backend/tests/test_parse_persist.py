import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_parse_requires_auth(client):
    r = await client.post("/api/parse", data={"title": "版本说明", "content": "正文"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_parse_saves_analysis(client, editor_token):
    with patch("app.api.generator.analyze_document", return_value={
        "新增功能": ["一键上报"],
        "变更与优化": ["优化导入"],
        "注意事项": ["需升级"],
        "风险提示": ["数据延迟"],
    }) as mock_analyze:
        r = await client.post(
            "/api/parse",
            data={"title": "版本说明", "content": "正文"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["analysis_id"] is not None
    assert data["新增功能"] == ["一键上报"]
    mock_analyze.assert_called_once()


@pytest.mark.asyncio
async def test_parse_uses_cached_analysis(client, editor_token):
    with patch("app.api.generator.analyze_document", return_value={
        "新增功能": ["一键上报"],
        "变更与优化": ["优化导入"],
        "注意事项": ["需升级"],
        "风险提示": ["数据延迟"],
    }) as mock_analyze:
        await client.post(
            "/api/parse",
            data={"title": "版本说明", "content": "正文"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        r = await client.post(
            "/api/parse",
            data={"title": "版本说明", "content": "正文"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    assert r.status_code == 200
    assert r.json()["新增功能"] == ["一键上报"]
    mock_analyze.assert_called_once()
