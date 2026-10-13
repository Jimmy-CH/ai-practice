"""content-workbench 演示数据生成脚本。

用法：
    1. 启动后端（建议使用 e2e_main 入口，使用 FakeGenerator）：
       cd content-workbench/backend
       $env:DATABASE_URL="sqlite+aiosqlite:///./workbench.db"
       .\venv\Scripts\python -m uvicorn app.e2e_main:app --host 127.0.0.1 --port 8000

    2. 运行本脚本：
       .\venv\Scripts\python seed_demo_data.py

脚本会创建：一个项目、两条相关资料、三类生成资产、完成审核与模拟发布。
"""

import asyncio
import os
import sys

import httpx

BASE_URL = os.environ.get("WORKBENCH_API_URL", "http://127.0.0.1:8000/api")
EDITOR = {"username": "editor", "password": "editor123"}
REVIEWER = {"username": "reviewer", "password": "review123"}


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token = ""

    async def login(self, username: str, password: str) -> None:
        response = await self._post("/auth/login", json={"username": username, "password": password})
        self.token = response["token"]

    async def _request(self, method: str, path: str, **kwargs) -> any:
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                **kwargs,
            )
            if response.status_code >= 400:
                print(f"ERROR {method} {path}: {response.status_code} {response.text}")
                response.raise_for_status()
            if response.status_code == 204:
                return None
            return response.json()

    async def _get(self, path: str, **kwargs) -> any:
        return await self._request("GET", path, **kwargs)

    async def _post(self, path: str, **kwargs) -> any:
        return await self._request("POST", path, **kwargs)

    async def _put(self, path: str, **kwargs) -> any:
        return await self._request("PUT", path, **kwargs)

    async def _delete(self, path: str, **kwargs) -> any:
        return await self._request("DELETE", path, **kwargs)


async def clean_existing_projects(client: ApiClient, prefix: str = "演示项目") -> None:
    projects = await client._get("/projects")
    for project in projects:
        if project["name"].startswith(prefix):
            print(f"清理旧项目: {project['name']} ({project['id']})")
            await client._delete(f"/projects/{project['id']}")


async def main() -> int:
    client = ApiClient(BASE_URL)

    print("==> 登录 editor")
    await client.login(EDITOR["username"], EDITOR["password"])

    print("==> 清理历史演示项目")
    await clean_existing_projects(client)

    print("==> 创建项目")
    project = await client._post(
        "/projects",
        json={
            "name": "演示项目-新品发布",
            "theme": "AI 智能报表新品发布",
            "audience": "企业数据分析师",
            "tone": "专业且亲和",
        },
    )
    project_id = project["id"]
    print(f"    项目 ID: {project_id}")

    print("==> 添加资料")
    sources = [
        {
            "name": "产品白皮书",
            "content": (
                "AI 智能报表是面向企业数据分析师的一站式分析平台。"
                "支持拖拽式探索、多维度下钻、智能洞察与一键导出。"
                "帮助企业快速发现数据价值，提升决策效率。"
            ),
        },
        {
            "name": "用户场景",
            "content": (
                "企业数据分析师每天需要处理大量销售、运营数据。"
                "AI 智能报表通过自然语言查询和自动可视化，"
                "让分析师无需编写复杂 SQL 即可获得业务洞察。"
            ),
        },
    ]
    source_ids = []
    for source in sources:
        created = await client._post(f"/projects/{project_id}/sources", json=source)
        source_ids.append(created["id"])
        print(f"    资料: {source['name']} -> {created['id']}")

    print("==> 一键生成资产")
    assets = await client._post(f"/projects/{project_id}/generate")
    asset_ids = {asset["kind"]: asset["id"] for asset in assets}
    for asset in assets:
        print(f"    生成: {asset['kind']} -> {asset['id']} (status={asset['status']})")

    print("==> 提交所有资产审核")
    for asset_id in asset_ids.values():
        await client._post(f"/assets/{asset_id}/submit")
        print(f"    提交审核: {asset_id}")

    print("==> 登录 reviewer")
    await client.login(REVIEWER["username"], REVIEWER["password"])

    print("==> 获取待审列表")
    pending = await client._get("/assets/pending")
    for asset in pending:
        print(f"    待审: {asset['id']} ({asset['kind']})")

    print("==> 审核通过")
    for asset_id in asset_ids.values():
        await client._post(
            f"/assets/{asset_id}/reviews",
            json={"decision": "approved", "comment": "内容准确，同意发布"},
        )
        print(f"    通过: {asset_id}")

    print("==> 登录 editor")
    await client.login(EDITOR["username"], EDITOR["password"])

    print("==> 获取已审核资产")
    approved = await client._get("/assets/approved")
    for asset in approved:
        print(f"    已审核: {asset['id']} ({asset['kind']})")

    print("==> 模拟发布")
    for asset_id in asset_ids.values():
        await client._post(f"/assets/{asset_id}/deliveries")
        print(f"    发布: {asset_id}")

    print("==> 获取发布任务")
    deliveries = await client._get("/deliveries")
    for delivery in deliveries:
        print(f"    任务: {delivery['id']} asset={delivery['asset_id']} status={delivery['status']}")

    print("\n演示数据生成完成。")
    print(f"前端可访问: http://localhost:5173/projects/{project_id}/workspace")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception as exc:
        print(f"生成失败: {exc}")
        sys.exit(1)
