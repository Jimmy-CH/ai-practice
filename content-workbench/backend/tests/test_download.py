from tests.helpers import setup_project_with_source


async def _approved_asset(client, editor_headers, reviewer_headers) -> dict:
    project_id = await setup_project_with_source(client, editor_headers)
    assets = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()
    asset = assets[0]
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    await client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "approved"}, headers=reviewer_headers)
    return asset


async def test_download_approved(client, editor_headers, reviewer_headers):
    asset = await _approved_asset(client, editor_headers, reviewer_headers)
    response = await client.get(f"/api/assets/{asset['id']}/download?format=markdown", headers=editor_headers)
    assert response.status_code == 200 and "attachment" in response.headers.get("content-disposition", "")


async def test_download_draft_rejected(client, editor_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    asset = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()[0]
    response = await client.get(f"/api/assets/{asset['id']}/download?format=markdown", headers=editor_headers)
    assert response.status_code == 409
