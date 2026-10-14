import asyncio

import pytest
from unittest.mock import AsyncMock, patch
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


@pytest.mark.asyncio
async def test_parse_schedules_background_pregeneration(client, editor_token):
    """parse 不得同步等待物料生成：预热必须移交后台任务，解析结果立即返回。"""

    async def fake_analyze(*args, **kwargs):
        return {"新增功能": ["A"], "变更与优化": [], "注意事项": [], "风险提示": []}

    with patch("app.api.generator.analyze_document", fake_analyze):
        with patch(
            "app.api.generator.pregenerate_materials", new_callable=AsyncMock
        ) as mock_pre:
            r = await client.post(
                "/api/parse",
                data={"title": "T", "content": "C"},
                headers={"Authorization": f"Bearer {editor_token}"},
            )
    assert r.status_code == 200
    mock_pre.assert_called_once()
    args = mock_pre.call_args.args
    assert args[1] == "T"
    assert args[2] == {"新增功能": ["A"], "变更与优化": [], "注意事项": [], "风险提示": []}
    assert args[3] == "网点管理员"


@pytest.mark.asyncio
async def test_pregenerate_writes_cache_per_type_without_waiting(db_session, monkeypatch):
    """预热应每种物料完成即落库：先完成的类型不必等其余类型结束才写缓存。"""
    from app.api.generator import pregenerate_materials
    from app.services import generated_material_service as gm_svc

    analysis = {"新增功能": ["A"], "变更与优化": [], "注意事项": [], "风险提示": []}
    faq_started = asyncio.Event()
    release_faq = asyncio.Event()
    others_done = asyncio.Event()
    upserted: list[str] = []

    async def fake_generate(title, analysis, audience, material_type):
        if material_type == "faq":
            faq_started.set()
            await release_faq.wait()
        return {
            "title": f"R-{material_type}",
            "content": f"C-{material_type}",
            "audience": audience,
            "material_type": material_type,
            "meta": {},
        }

    async def fake_upsert(session, owner_id, source_title, audience, material_type, analysis_hash, content):
        upserted.append(material_type)
        if set(upserted) == set(MATERIAL_TYPES) - {"faq"}:
            others_done.set()

    monkeypatch.setattr("app.services.material_writer.generate_material", fake_generate)
    monkeypatch.setattr(gm_svc, "upsert_generated_material", fake_upsert)

    pre_task = asyncio.create_task(pregenerate_materials(1, "T", analysis, "网点管理员"))
    await asyncio.wait_for(faq_started.wait(), timeout=5)
    await asyncio.wait_for(others_done.wait(), timeout=5)
    assert "faq" not in upserted  # faq 仍阻塞在生成中，其余类型已全部落库

    release_faq.set()
    await asyncio.wait_for(pre_task, timeout=5)
    assert "faq" in upserted
