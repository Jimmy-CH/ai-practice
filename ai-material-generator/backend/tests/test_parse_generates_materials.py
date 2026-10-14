import pytest
from unittest.mock import patch
from app.services.material_writer import MATERIAL_TYPES


@pytest.mark.asyncio
async def test_parse_generates_all_materials_for_default_audience(client, editor_token):
    async def fake_analyze(*args, **kwargs):
        return {"新增功能": ["A"], "变更与优化": [], "注意事项": [], "风险提示": []}

    async def fake_generate(title, analysis, audience, material_type):
        return {
            "title": f"R-{material_type}",
            "content": f"C-{material_type}",
            "audience": audience,
            "material_type": material_type,
            "meta": {"audience": audience, "material_type": material_type, "generator": "DeepSeek"},
        }

    with patch("app.api.generator.analyze_document", fake_analyze):
        with patch("app.services.material_writer.generate_material", side_effect=fake_generate):
            r = await client.post(
                "/api/parse",
                data={"title": "T", "content": "C"},
                headers={"Authorization": f"Bearer {editor_token}"},
            )
    assert r.status_code == 200

    # 切换每种物料类型都应命中缓存
    for mt in MATERIAL_TYPES:
        r2 = await client.post(
            "/api/generate",
            json={"title": "T", "analysis": r.json(), "audience": "网点管理员", "material_type": mt},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        assert r2.status_code == 200, f"failed for {mt}: {r2.text}"
        assert r2.json()["cached"] is True, f"not cached for {mt}"
        assert r2.json()["content"] == f"C-{mt}"
