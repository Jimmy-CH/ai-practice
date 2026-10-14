import pytest
from unittest.mock import patch


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
