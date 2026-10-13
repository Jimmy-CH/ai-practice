from tests.helpers import setup_project_with_source


async def test_generate_creates_three_assets(client, editor_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    response = await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)
    assert response.status_code == 201
    assets = response.json()
    assert {a["kind"] for a in assets} == {"announcement", "faq", "poster"}
    assert all(a["citations"] and a["citations"][0]["text"] for a in assets)


async def test_generate_without_sources_rejected(client, editor_headers):
    project = (await client.post("/api/projects", json={"name": "V2", "theme": "主题X", "audience": "用户"}, headers=editor_headers)).json()
    response = await client.post(f"/api/projects/{project['id']}/generate", headers=editor_headers)
    assert response.status_code == 422 and "该项目暂无资料" in response.json()["detail"]


async def test_generate_irrelevant_sources_rejected(client, editor_headers):
    project_id = await setup_project_with_source(client, editor_headers, theme="完全无关主题Z", content="这是一段与主题和受众都毫无关系的文本。")
    response = await client.post(f"/api/projects/{project_id}/generate", headers=editor_headers)
    assert response.status_code == 422 and "不相关或内容过短" in response.json()["detail"]


async def test_generate_editor_only(client, reviewer_headers, editor_headers):
    project_id = await setup_project_with_source(client, editor_headers)
    response = await client.post(f"/api/projects/{project_id}/generate", headers=reviewer_headers)
    assert response.status_code == 403
