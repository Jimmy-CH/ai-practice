import pytest


@pytest.mark.asyncio
async def test_only_approved_can_download(client, editor_token):
    r = await client.post(
        "/api/materials",
        json={"title": "t", "content": "c", "material_type": "wechat", "audience": "user"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    mid = r.json()["id"]
    r = await client.get(f"/api/materials/{mid}/download", headers={"Authorization": f"Bearer {editor_token}"})
    assert r.status_code == 400
