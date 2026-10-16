import asyncio

import pytest
from app.services import material_writer
from app.services.material_writer import generate_material, generate_material_deduped, MATERIAL_TYPES


@pytest.mark.asyncio
async def test_generate_material(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return "# 网点管家 V3.2.0 上线公告\n\n各位网点负责人：..."

    monkeypatch.setattr("app.services.material_writer._chat", fake_chat)
    analysis = {
        "新增功能": ["异常件一键上报"],
        "变更与优化": ["运单批量导入"],
        "注意事项": ["需升级"],
        "风险提示": ["数据延迟"],
    }
    result = await generate_material("网点管家 V3.2.0", analysis, "网点管理员", "version_announcement")
    assert result["title"] == "网点管家 V3.2.0 上线公告"
    assert "各位网点负责人" in result["content"]
    assert result["material_type"] == "version_announcement"


def test_material_types():
    assert "version_announcement" in MATERIAL_TYPES
    assert MATERIAL_TYPES["version_announcement"] == "版本宣发稿"


@pytest.mark.asyncio
async def test_deduped_reuses_inflight_task_for_same_key():
    """同 key 并发调用必须复用同一在飞任务，避免后台预热与用户请求双倍调用 LLM。"""
    calls = []

    async def factory():
        calls.append(1)
        await asyncio.sleep(0.01)
        return {"content": "C"}

    key = (1, "T", "网点管理员", "version_announcement", "hash-x")
    r1, r2 = await asyncio.gather(
        generate_material_deduped(key, factory),
        generate_material_deduped(key, factory),
    )
    assert r1 == r2 == {"content": "C"}
    assert len(calls) == 1
    assert key not in material_writer._inflight_tasks


@pytest.mark.asyncio
async def test_deduped_runs_separately_for_different_keys():
    async def factory(value: str):
        return value

    k1, k2 = (1, "T", "a", "x", "h"), (1, "T", "a", "y", "h")
    r1, r2 = await asyncio.gather(
        generate_material_deduped(k1, lambda: factory("one")),
        generate_material_deduped(k2, lambda: factory("two")),
    )
    assert (r1, r2) == ("one", "two")
    assert k1 not in material_writer._inflight_tasks
    assert k2 not in material_writer._inflight_tasks


@pytest.mark.asyncio
async def test_deduped_clears_key_on_failure_and_allows_retry():
    async def bad():
        raise RuntimeError("boom")

    key = (1, "T", "网点管理员", "faq", "hash-y")
    with pytest.raises(RuntimeError):
        await generate_material_deduped(key, bad)
    assert key not in material_writer._inflight_tasks

    async def ok():
        return "fine"

    assert await generate_material_deduped(key, ok) == "fine"
