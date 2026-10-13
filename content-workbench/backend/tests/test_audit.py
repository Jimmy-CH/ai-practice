from tests.helpers import setup_project_with_source


async def test_audit_reviewer_only(client, editor_headers, reviewer_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)
    assert (await client.get("/api/audit", headers=reviewer_headers)).status_code == 200
    assert (await client.get("/api/audit", headers=editor_headers)).status_code == 403


async def test_audit_records_edit_snapshot(client, editor_headers, reviewer_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    asset = (await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)).json()[0]
    await client.post(f"/api/assets/{asset['id']}/submit", headers=editor_headers)
    await client.post(f"/api/assets/{asset['id']}/reviews", json={"decision": "approved"}, headers=reviewer_headers)
    new_content = dict(asset["content"])
    new_content["summary"] = "改"
    await client.put(f"/api/assets/{asset['id']}", json={"content": new_content}, headers=editor_headers)
    rows = (await client.get("/api/audit", headers=reviewer_headers)).json()
    edit_rows = [r for r in rows if r["action"] == "edit_asset"]
    assert edit_rows and edit_rows[0]["detail"]["status_reset"] is True
