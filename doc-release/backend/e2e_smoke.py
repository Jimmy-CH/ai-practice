"""端到端冒烟：进程内起 uvicorn（默认打桩 LLM），跑通三大场景并校验产物。

用法（在 backend 目录下）：
  .\\venv\\Scripts\\python.exe e2e_smoke.py            # 打桩 LLM（离线模式）
  .\\venv\\Scripts\\python.exe e2e_smoke.py --real     # 真实星语网关（需内网）
"""

import asyncio
import json
import sys
import threading
import time

import httpx
import uvicorn

import app.main as main_module
from app.services import llm_service

HOST = "127.0.0.1"
PORT = 8100
BASE = f"http://{HOST}:{PORT}"


async def _fake_chat(system_prompt: str, user_prompt: str) -> str:
    return json.dumps({
        "features": [{
            "tag": "技术重构", "risk": "低", "breaking": False,
            "title": "冒烟生成的占位功能点", "biz": "冒烟测试用业务说明",
            "tech": "冒烟测试用技术说明", "visible": "无", "scope": "冒烟",
            "acceptance": "冒烟断言", "action": "无需操作", "role": "研发", "paths": [],
        }],
        "highlights": ["冒烟通过"], "confidence": 0.9,
    }, ensure_ascii=False)


async def _run_checks() -> list[str]:
    failures: list[str] = []
    async with httpx.AsyncClient(base_url=BASE, timeout=180) as client:
        repos = (await client.get("/api/repos")).json()
        sample = next((r for r in repos if r["is_sample"]), None)
        if sample is None:
            return ["未找到示例仓库（is_sample=True）"]

        refs = (await client.get(f"/api/repos/{sample['id']}/refs")).json()
        tags = {t["name"] for t in refs["tags"]}
        for t in ("v2.13.3", "v2.13.4", "v2.14.0", "v3.0.0"):
            if t not in tags:
                failures.append(f"缺少标签 {t}")

        scenarios = (await client.get(f"/api/repos/{sample['id']}/scenarios")).json()
        if len(scenarios) != 3:
            failures.append(f"场景数应为 3，实际 {len(scenarios)}")

        for sc in scenarios:
            resp = await client.post("/api/runs", json={
                "repo_id": sample["id"], "base_ref": sc["base"], "head_ref": sc["head"],
                "version_label": sc["version"], "tone": "business", "mask": False})
            if resp.status_code != 201:
                failures.append(f"[{sc['id']}] 创建运行失败：{resp.status_code} {resp.text[:200]}")
                continue
            run_id = resp.json()["id"]
            deadline = time.time() + 180
            detail: dict = {}
            while time.time() < deadline:
                detail = (await client.get(f"/api/runs/{run_id}")).json()
                if detail["status"] not in ("pending", "running"):
                    break
                await asyncio.sleep(0.3)
            if detail.get("status") != "succeeded":
                failures.append(f"[{sc['id']}] 终态 {detail.get('status')}（error={detail.get('error')}）")
                continue

            for kind in ("checklist", "document", "trace"):
                art = await client.get(f"/api/runs/{run_id}/artifacts/{kind}")
                if art.status_code != 200 or not art.text.strip():
                    failures.append(f"[{sc['id']}] 产物 {kind} 不可读或为空")
            trace = json.loads((await client.get(f"/api/runs/{run_id}/artifacts/trace")).text)
            if trace["runId"] != run_id:
                failures.append(f"[{sc['id']}] trace.runId 不匹配")
            print(f"  [{sc['id']}] {sc['version']}：功能点 {len(trace['features'])} 个，"
                  f"提交 {trace['changes'].get('commits')} 个，产物 3 份 OK")
    return failures


def main() -> int:
    if "--real" not in sys.argv:
        llm_service._chat = _fake_chat
        print("使用打桩 LLM（离线模式）")
    else:
        print("使用真实星语网关")

    config = uvicorn.Config(main_module.app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    try:
        failures = asyncio.run(_run_checks())
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    if failures:
        print("冒烟失败：")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("冒烟全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
