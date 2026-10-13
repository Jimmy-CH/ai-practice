from tests.helpers import setup_project_with_source


async def _draft_asset(client, editor_headers) -> dict:
    project_id = await setup_project_with_source(client, editor_headers)
    assets = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()
    return assets[0]


async def test_edit_draft(client, editor_headers):
    asset = await _draft_asset(client, editor_headers)
    content = dict(asset["content"])
    content["summary"] = "人工润色后的摘要"
    response = await client.put(f"/api/assets/{asset['id']}", json={"content": content}, headers=editor_headers)
    assert response.status_code == 200 and response.json()["content"]["summary"] == "人工润色后的摘要"


async def test_edit_approved_resets_to_draft(client, editor_headers, reviewer_headers):
    asset = await _draft_asset(client, editor_headers)
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    await client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "approved"}, headers=reviewer_headers)
    response = await client.put(f"/api/assets/{asset['id']}", json={"content": asset["content"]}, headers=editor_headers)
    assert response.status_code == 200 and response.json()["status"] == "draft"


async def test_edit_pending_review_rejected(client, editor_headers):
    asset = await _draft_asset(client, editor_headers)
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    response = await client.put(f"/api/assets/{asset['id']}", json={"content": asset["content"]}, headers=editor_headers)
    assert response.status_code == 409


async def test_reviewer_only(client, editor_headers):
    asset = await _draft_asset(client, editor_headers)
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    response = await client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "approved"}, headers=editor_headers)
    assert response.status_code == 403


async def test_review_rejected_with_comment(client, editor_headers, reviewer_headers):
    asset = await _draft_asset(client, editor_headers)
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    response = await client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "rejected", "comment": "标题不准确"}, headers=reviewer_headers)
    assert response.status_code == 200 and response.json()["status"] == "rejected"
    assert (await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)).status_code == 200
