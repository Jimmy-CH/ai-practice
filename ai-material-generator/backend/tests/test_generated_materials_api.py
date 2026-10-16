import pytest
from unittest.mock import patch
from app.services import generated_material_service as gm_svc


@pytest.mark.asyncio
async def test_update_generated_material(client, editor_token):
    with patch("app.api.generator.generate_material", return_value={
        "title": "R",
        "content": "C",
        "audience": "网点管理员",
        "material_type": "version_announcement",
        "meta": {"audience": "网点管理员", "material_type": "版本宣发稿", "generator": "DeepSeek"},
    }):
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
    gm_id = r.json()["id"]

    r2 = await client.put(
        f"/api/generated-materials/{gm_id}",
        json={"content": "edited content"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["content"] == "edited content"


@pytest.mark.asyncio
async def test_update_generated_material_forbidden_for_other_user(client, editor_token):
    with patch("app.api.generator.generate_material", return_value={
        "title": "R",
        "content": "C",
        "audience": "网点管理员",
        "material_type": "version_announcement",
        "meta": {"audience": "网点管理员", "material_type": "版本宣发稿", "generator": "DeepSeek"},
    }):
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
    gm_id = r.json()["id"]

    reviewer_login = await client.post("/api/auth/login", data={"username": "reviewer", "password": "reviewer123"})
    reviewer_token = reviewer_login.json()["access_token"]

    r2 = await client.put(
        f"/api/generated-materials/{gm_id}",
        json={"content": "edited content"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert r2.status_code == 403
