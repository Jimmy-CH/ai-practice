async def setup_project_with_source(client, editor_headers, theme="智能报表 2.0", content="智能报表 2.0 支持拖拽分析与一键导出，面向数据分析师。") -> str:
    project = (await client.post("/api/projects", json={"name": "V2", "theme": theme, "audience": "数据分析师"}, headers=editor_headers)).json()
    await client.post(f"/api/projects/{project['id']}/sources", json={"name": "手册", "content": content}, headers=editor_headers)
    return project["id"]
