async def test_editor_can_create_project(client, editor_headers):
    response = await client.post("/api/projects", headers=editor_headers, json={
        "name": "新品发布会", "theme": "发布 X1", "audience": "运营", "tone": "正式"
    })
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "新品发布会" and body["source_count"] == 0


async def test_reviewer_cannot_create_project(client, reviewer_headers):
    response = await client.post("/api/projects", headers=reviewer_headers, json={
        "name": "新品发布会", "theme": "发布 X1", "audience": "运营"
    })
    assert response.status_code == 403


async def test_editor_can_list_projects(client, editor_headers):
    await client.post("/api/projects", headers=editor_headers, json={"name": "A", "theme": "t"})
    response = await client.get("/api/projects", headers=editor_headers)
    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_editor_can_add_and_list_sources(client, editor_headers):
    project = (await client.post("/api/projects", headers=editor_headers, json={"name": "P", "theme": "t"})).json()
    pid = project["id"]
    response = await client.post(f"/api/projects/{pid}/sources", headers=editor_headers, json={
        "name": "手册.txt", "content": "X1 支持 5G。"
    })
    assert response.status_code == 201
    body = response.json()
    assert body["content_hash"] and body["content_hash"] == response.json()["content_hash"]

    response = await client.get(f"/api/projects/{pid}/sources", headers=editor_headers)
    assert response.status_code == 200 and len(response.json()) == 1


async def test_source_dedup_by_hash(client, editor_headers):
    project = (await client.post("/api/projects", headers=editor_headers, json={"name": "P", "theme": "t"})).json()
    pid = project["id"]
    body = {"name": "手册", "content": "第一段。智能报表支持拖拽分析。\n\n第二段。"}
    first = await client.post(f"/api/projects/{pid}/sources", headers=editor_headers, json=body)
    second = await client.post(f"/api/projects/{pid}/sources", headers=editor_headers, json=body)
    assert first.status_code == 201 and second.status_code == 409


async def test_delete_project_cascades(client, editor_headers):
    project = (await client.post("/api/projects", headers=editor_headers, json={"name": "P", "theme": "t"})).json()
    pid = project["id"]
    await client.post(f"/api/projects/{pid}/sources", headers=editor_headers, json={"name": "s", "content": "内容。"})
    assert (await client.delete(f"/api/projects/{pid}", headers=editor_headers)).status_code == 204
    assert (await client.get(f"/api/projects/{pid}/sources", headers=editor_headers)).status_code == 404
