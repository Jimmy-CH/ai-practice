import pytest
from unittest.mock import patch
from app.services.material_writer import MATERIAL_TYPES, generate_all_materials


@pytest.mark.asyncio
async def test_generate_all_skips_everything_when_only_types_empty():
    """only_types 白名单为空集时应全部跳过：generate-all 全命中时不能白烧模型调用。"""
    with patch("app.services.material_writer.generate_material", side_effect=AssertionError("must not be called")) as mock_generate:
        result = await generate_all_materials("T", {}, "网点管理员", only_types=set())
    assert result == []
    mock_generate.assert_not_called()


@pytest.mark.asyncio
async def test_generate_caches_result(client, editor_token):
    with patch("app.api.generator.generate_material", return_value={
        "title": "R",
        "content": "C",
        "audience": "网点管理员",
        "material_type": "version_announcement",
        "meta": {"audience": "网点管理员", "material_type": "版本宣发稿", "generator": "DeepSeek"},
    }) as mock_generate:
        r = await client.post(
            "/api/generate",
            json={
                "title": "T",
                "analysis": {"新增功能": ["A"]},
                "audience": "网点管理员",
                "material_type": "version_announcement",
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    assert r.status_code == 200
    assert r.json()["content"] == "C"
    assert r.json()["cached"] is False
    mock_generate.assert_called_once()


@pytest.mark.asyncio
async def test_generate_uses_cache(client, editor_token):
    with patch("app.api.generator.generate_material", return_value={
        "title": "R",
        "content": "C",
        "audience": "网点管理员",
        "material_type": "version_announcement",
        "meta": {"audience": "网点管理员", "material_type": "版本宣发稿", "generator": "DeepSeek"},
    }) as mock_generate:
        await client.post(
            "/api/generate",
            json={
                "title": "T",
                "analysis": {"新增功能": ["A"]},
                "audience": "网点管理员",
                "material_type": "version_announcement",
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        r = await client.post(
            "/api/generate",
            json={
                "title": "T",
                "analysis": {"新增功能": ["A"]},
                "audience": "网点管理员",
                "material_type": "version_announcement",
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    assert r.status_code == 200
    assert r.json()["content"] == "C"
    assert r.json()["cached"] is True
    mock_generate.assert_called_once()


@pytest.mark.asyncio
async def test_generate_all_hits_cache_right_after_parse(client, editor_token):
    """复现真实用户路径：parse 预生成后前端立即回调 generate-all，
    必须全部命中缓存，不允许追加任何模型调用（回归：哈希不一致导致 30s 全量重生成）。"""
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
        with patch("app.services.material_writer.generate_material", side_effect=fake_generate) as mock_generate:
            r = await client.post(
                "/api/parse",
                data={"title": "T", "content": "C"},
                headers={"Authorization": f"Bearer {editor_token}"},
            )
            assert r.status_code == 200

            # 与前端 doParse 一致：直接把 parse 响应对象作为 analysis 回传
            r2 = await client.post(
                "/api/generate-all",
                json={"title": "T", "analysis": r.json(), "audience": "网点管理员"},
                headers={"Authorization": f"Bearer {editor_token}"},
            )
    assert r2.status_code == 200
    materials = r2.json()["materials"]
    assert len(materials) == len(MATERIAL_TYPES)
    assert all(m["cached"] is True for m in materials)
    # 回归：命中缓存的物料项必须带缓存记录 id，否则前端编辑保存无从发起 PUT
    assert all(isinstance(m.get("id"), int) for m in materials)
    # parse 预生成恰好 6 次调用；generate-all 全命中不得追加任何调用
    assert mock_generate.call_count == len(MATERIAL_TYPES)


@pytest.mark.asyncio
async def test_generate_all_caches_and_reuses(client, editor_token):
    async def fake_generate(title, analysis, audience, mt):
        return {
            "title": f"R-{mt}",
            "content": f"C-{mt}",
            "audience": audience,
            "material_type": mt,
            "meta": {"audience": audience, "material_type": mt, "generator": "DeepSeek"},
        }

    with patch("app.services.material_writer.generate_material", side_effect=fake_generate) as mock_generate:
        r = await client.post(
            "/api/generate-all",
            json={"title": "T", "analysis": {"新增功能": ["A"]}, "audience": "网点管理员"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        assert r.status_code == 200
        first_count = mock_generate.call_count

        r2 = await client.post(
            "/api/generate-all",
            json={"title": "T", "analysis": {"新增功能": ["A"]}, "audience": "网点管理员"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        assert r2.status_code == 200
        assert mock_generate.call_count == first_count
        # 未命中与命中两条返回路径都必须携带缓存 id
        assert all(isinstance(m.get("id"), int) for m in r.json()["materials"])
        assert all(isinstance(m.get("id"), int) for m in r2.json()["materials"])
