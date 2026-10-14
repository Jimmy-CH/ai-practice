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


async def _create_pending(client, editor_token, title: str = "t") -> int:
    """创建物料并提交审核，返回物料 id。"""
    r = await client.post(
        "/api/materials",
        json={"title": title, "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    mid = r.json()["id"]
    await client.post(f"/api/materials/{mid}/submit", headers={"Authorization": f"Bearer {editor_token}"})
    return mid


@pytest.mark.asyncio
async def test_reject_requires_comment(client, editor_token, reviewer_token):
    mid = await _create_pending(client, editor_token)
    r = await client.post(
        f"/api/materials/{mid}/reviews",
        json={"action": "reject", "comment": ""},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert r.status_code == 400
    assert "驳回" in r.json()["detail"]
    detail = await client.get(f"/api/materials/{mid}", headers={"Authorization": f"Bearer {editor_token}"})
    assert detail.json()["status"] == "pending_review"


@pytest.mark.asyncio
async def test_reject_whitespace_comment_rejected(client, editor_token, reviewer_token):
    mid = await _create_pending(client, editor_token)
    r = await client.post(
        f"/api/materials/{mid}/reviews",
        json={"action": "reject", "comment": "   \n  "},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_reject_records_review_fields(client, editor_token, reviewer_token):
    mid = await _create_pending(client, editor_token)
    r = await client.post(
        f"/api/materials/{mid}/reviews",
        json={"action": "reject", "comment": "证据不足，请补充数据来源"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "rejected"
    assert data["review_comment"] == "证据不足，请补充数据来源"
    assert data["reviewed_by"] is not None
    assert data["reviewed_at"] is not None


@pytest.mark.asyncio
async def test_approved_list_shows_reviewer_username(client, editor_token, reviewer_token):
    mid = await _create_pending(client, editor_token)
    await client.post(
        f"/api/materials/{mid}/reviews",
        json={"action": "approve", "comment": ""},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    r = await client.get("/api/materials/approved", headers={"Authorization": f"Bearer {editor_token}"})
    assert r.status_code == 200
    item = next(m for m in r.json() if m["id"] == mid)
    assert item["status"] == "approved"
    assert item["reviewer_username"] == "reviewer"
    assert item["reviewed_at"] is not None


@pytest.mark.asyncio
async def test_resubmit_clears_review_fields(client, editor_token, reviewer_token):
    mid = await _create_pending(client, editor_token)
    await client.post(
        f"/api/materials/{mid}/reviews",
        json={"action": "reject", "comment": "需修改"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    r = await client.post(f"/api/materials/{mid}/submit", headers={"Authorization": f"Bearer {editor_token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "pending_review"
    assert data["review_comment"] is None
    assert data["reviewed_by"] is None
    assert data["reviewed_at"] is None


@pytest.mark.asyncio
async def test_material_detail_has_null_reviewer_username(client, editor_token):
    r = await client.post(
        "/api/materials",
        json={"title": "t", "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    mid = r.json()["id"]
    r = await client.get(f"/api/materials/{mid}", headers={"Authorization": f"Bearer {editor_token}"})
    assert r.status_code == 200
    assert r.json()["reviewer_username"] is None
