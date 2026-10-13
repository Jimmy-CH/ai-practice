import pytest


@pytest.mark.asyncio
async def test_create_material(client, editor_token):
    r = await client.post(
        "/api/materials",
        json={"title": "t", "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_editor_cannot_see_others_materials(client, editor_token, reviewer_token):
    r = await client.post(
        "/api/materials",
        json={"title": "t", "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 200
    editor_list = await client.get("/api/materials", headers={"Authorization": f"Bearer {editor_token}"})
    assert len(editor_list.json()) == 1
    reviewer_list = await client.get("/api/materials", headers={"Authorization": f"Bearer {reviewer_token}"})
    assert len(reviewer_list.json()) == 1


@pytest.mark.asyncio
async def test_submit_and_approve_flow(client, editor_token, reviewer_token):
    r = await client.post(
        "/api/materials",
        json={"title": "t", "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    mid = r.json()["id"]
    r = await client.post(f"/api/materials/{mid}/submit", headers={"Authorization": f"Bearer {editor_token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "pending_review"
    r = await client.post(
        f"/api/materials/{mid}/reviews",
        json={"action": "approve", "comment": "ok"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_approved_edit_fallback_to_draft(client, editor_token, reviewer_token):
    r = await client.post(
        "/api/materials",
        json={"title": "t", "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    mid = r.json()["id"]
    await client.post(f"/api/materials/{mid}/submit", headers={"Authorization": f"Bearer {editor_token}"})
    await client.post(
        f"/api/materials/{mid}/reviews",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    r = await client.put(
        f"/api/materials/{mid}",
        json={"title": "t2", "content": "c2", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_pending_material_cannot_be_edited(client, editor_token):
    r = await client.post(
        "/api/materials",
        json={"title": "t", "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    mid = r.json()["id"]
    await client.post(f"/api/materials/{mid}/submit", headers={"Authorization": f"Bearer {editor_token}"})
    r = await client.put(
        f"/api/materials/{mid}",
        json={"title": "t2", "content": "c2", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 400
