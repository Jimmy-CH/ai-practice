"""海报配图端到端冒烟（真实链路：真星语提炼 + 真文生图），跑完保留供回归。

前置：
- 后端已启动：.\\venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
- editor 账号可用；uat 星语网关（10.130.13.74:8060）可达
- 真实调用耗时：提炼约 5-10 秒，生图约 15-40 秒
"""
import time
from uuid import uuid4

import httpx

BASE = "http://127.0.0.1:8001"
CLIENT_TIMEOUT = 300.0
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def login(username: str, password: str) -> str:
    with httpx.Client(timeout=CLIENT_TIMEOUT) as client:
        r = client.post(f"{BASE}/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["access_token"]


def main():
    token = login("editor", "editor123")
    title = f"E2E-POSTER-{uuid4().hex[:8]}"
    script = (
        "# 网点管家 V3.2.0 升级海报\n\n"
        "主标题：一键上报，省时省心\n"
        "副标题：异常件拍照即报，运单号自动带出\n"
        "卖点：扫码上报、进度可查、24 小时反馈"
    )
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(timeout=CLIENT_TIMEOUT) as client:
        # 1. 提炼画面描述（首次：真实 chat 调用）
        r = client.post(f"{BASE}/api/posters/prompt", json={"script_content": script}, headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["prompt"], "refined prompt is empty"
        assert body["cached"] is False
        print(f"refine prompt ok ({len(body['prompt'])} chars)")

        # 2. 同一脚本再提炼：命中缓存且内容一致
        r2 = client.post(f"{BASE}/api/posters/prompt", json={"script_content": script}, headers=headers)
        assert r2.status_code == 200
        assert r2.json()["cached"] is True
        assert r2.json()["prompt"] == body["prompt"]
        print("refine prompt cache hit ok")

        # 3. 生成海报图（真实文生图）
        t0 = time.perf_counter()
        r3 = client.post(
            f"{BASE}/api/posters/images",
            json={"source_title": title, "audience": "网点管理员", "prompt": body["prompt"]},
            headers=headers,
        )
        assert r3.status_code == 200, r3.text
        image = r3.json()
        assert image["file_size"] > 0
        assert image["image_url"] == f"/api/posters/images/{image['id']}/file"
        print(f"generate poster ok ({time.perf_counter() - t0:.1f}s, {image['file_size']} bytes)")

        # 4. 列表：当前用户+来源+受众组合可见 1 张
        r4 = client.get(
            f"{BASE}/api/posters/images",
            params={"source_title": title, "audience": "网点管理员"},
            headers=headers,
        )
        assert r4.status_code == 200 and len(r4.json()) == 1
        print("list poster images ok")

        # 5. 文件可取回且为合法 PNG
        r5 = client.get(f"{BASE}{image['image_url']}", headers=headers)
        assert r5.status_code == 200, r5.text
        assert r5.content.startswith(PNG_MAGIC), "returned file is not a PNG"
        print(f"fetch poster file ok ({len(r5.content)} bytes)")

        # 6. 删除后记录与文件均消失
        r6 = client.delete(f"{BASE}/api/posters/images/{image['id']}", headers=headers)
        assert r6.status_code == 200
        r7 = client.get(f"{BASE}{image['image_url']}", headers=headers)
        assert r7.status_code == 404
        print("delete poster ok")

    print("E2E poster smoke test passed")


if __name__ == "__main__":
    main()
