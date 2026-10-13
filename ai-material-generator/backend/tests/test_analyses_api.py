import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_get_analysis(client, editor_token):
    with patch("app.api.generator.analyze_document", return_value={
        "新增功能": ["一键上报"],
        "变更与优化": ["优化导入"],
        "注意事项": ["需升级"],
        "风险提示": ["数据延迟"],
    }):
        await client.post(
            "/api/parse",
            data={"title": "版本说明", "content": "正文"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    r = await client.get(
        "/api/analyses/版本说明",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 200
    assert r.json()["新增功能"] == ["一键上报"]


@pytest.mark.asyncio
async def test_update_analysis(client, editor_token):
    with patch("app.api.generator.analyze_document", return_value={
        "新增功能": ["一键上报"],
        "变更与优化": ["优化导入"],
        "注意事项": ["需升级"],
        "风险提示": ["数据延迟"],
    }):
        parsed = await client.post(
            "/api/parse",
            data={"title": "版本说明", "content": "正文"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    analysis_id = parsed.json()["analysis_id"]
    r = await client.put(
        f"/api/analyses/{analysis_id}",
        json={"new_features": ["编辑后"], "changes": [], "notices": [], "risks": []},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 200
    assert r.json()["新增功能"] == ["编辑后"]


@pytest.mark.asyncio
async def test_update_analysis_forbidden_for_other_user(client, editor_token, reviewer_token):
    with patch("app.api.generator.analyze_document", return_value={
        "新增功能": ["一键上报"],
        "变更与优化": ["优化导入"],
        "注意事项": ["需升级"],
        "风险提示": ["数据延迟"],
    }):
        parsed = await client.post(
            "/api/parse",
            data={"title": "版本说明", "content": "正文"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    analysis_id = parsed.json()["analysis_id"]
    r = await client.put(
        f"/api/analyses/{analysis_id}",
        json={"new_features": ["越权"], "changes": [], "notices": [], "risks": []},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert r.status_code == 403
