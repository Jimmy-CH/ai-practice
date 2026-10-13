import pytest
from app.services.material_writer import generate_material, MATERIAL_TYPES


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
