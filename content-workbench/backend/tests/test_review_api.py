from tests.helpers import setup_project_with_source


async def test_pending_list_reviewer_only(client, editor_headers, reviewer_headers):
    assert (await client.get("/api/assets/pending", headers=editor_headers)).status_code == 403
    response = await client.get("/api/assets/pending", headers=reviewer_headers)
    assert response.status_code == 200 and response.json() == []


async def test_pending_list_shows_submitted(client, editor_headers, reviewer_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    assets = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()
    await client.post(f"/api/assets/{assets[0]['id']}/submit", headers=editor_headers)
    response = await client.get("/api/assets/pending", headers=reviewer_headers)
    assert len(response.json()) == 1
