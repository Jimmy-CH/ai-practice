from tests.helpers import setup_project_with_source


async def _approved_asset(client, editor_headers, reviewer_headers) -> dict:
    project_id = await setup_project_with_source(client, editor_headers)
    assets = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()
    asset = assets[0]
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    await client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "approved"}, headers=reviewer_headers)
    return asset


async def test_create_delivery_approved(client, editor_headers, reviewer_headers):
    asset = await _approved_asset(client, editor_headers, reviewer_headers)
    response = await client.post(f"/api/assets/{asset['id']}/deliveries", headers=editor_headers)
    assert response.status_code == 201 and response.json()["status"] == "completed"


async def test_delivery_draft_rejected(client, editor_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    asset = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()[0]
    response = await client.post(f"/api/assets/{asset['id']}/deliveries", headers=editor_headers)
    assert response.status_code == 409


async def test_list_deliveries(client, editor_headers, reviewer_headers):
    asset = await _approved_asset(client, editor_headers, reviewer_headers)
    await client.post(f"/api/assets/{asset['id']}/deliveries", headers=editor_headers)
    response = await client.get("/api/deliveries", headers=editor_headers)
    assert response.status_code == 200 and len(response.json()) == 1
