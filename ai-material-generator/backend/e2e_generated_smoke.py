import httpx
import time
from uuid import uuid4

BASE = "http://127.0.0.1:8001"
CLIENT_TIMEOUT = 300.0


def login(username: str, password: str) -> str:
    with httpx.Client(timeout=CLIENT_TIMEOUT) as client:
        r = client.post(f"{BASE}/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["access_token"]


def main():
    token = login("editor", "editor123")
    title = f"E2E-{uuid4().hex[:8]}"

    with httpx.Client(timeout=CLIENT_TIMEOUT) as client:
        # 解析文档：响应立即返回，物料预热在后台继续生成
        r = client.post(
            f"{BASE}/api/parse",
            data={"title": title, "content": "C"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        analysis = r.json()  # 后续生成复用解析响应，缓存键与后台预热保持一致
        print("parse returns immediately ok")

        # 预热尚在后台执行时立即请求物料：命中在飞任务或缓存均可，但必须返回有效内容
        r2 = client.post(
            f"{BASE}/api/generate",
            json={"title": title, "analysis": analysis, "audience": "网点管理员", "material_type": "operation_guide"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["content"]
        print("generate during background preheating returns content ok")

        # 轮询等待后台预热完成：目标物料最终应命中缓存
        deadline = time.monotonic() + 240
        while True:
            r3 = client.post(
                f"{BASE}/api/generate",
                json={"title": title, "analysis": analysis, "audience": "网点管理员", "material_type": "version_announcement"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r3.status_code == 200
            if r3.json()["cached"] is True:
                break
            assert time.monotonic() < deadline, "background pregeneration did not warm cache in time"
            time.sleep(5)
        gm_id = r3.json()["id"]
        print("background pregeneration warms cache ok")

        # 全量生成（真实用户路径：解析后前端立即回调 generate-all）
        # 回归：无论命中缓存与否，每项都必须携带缓存记录 id，否则前端编辑保存无从发起 PUT
        r_all = client.post(
            f"{BASE}/api/generate-all",
            json={"title": title, "analysis": analysis, "audience": "网点管理员"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r_all.status_code == 200
        items = r_all.json()["materials"]
        assert len(items) == 6
        assert all(m.get("id") for m in items), "generate-all items must carry generated material id"
        print("generate-all returns items with id ok")

        # 编辑缓存内容
        r4 = client.put(
            f"{BASE}/api/generated-materials/{gm_id}",
            json={"content": "edited content"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r4.status_code == 200
        assert r4.json()["content"] == "edited content"
        print("edit generated material ok")

        # 再次生成，应返回编辑后的内容
        r5 = client.post(
            f"{BASE}/api/generate",
            json={"title": title, "analysis": analysis, "audience": "网点管理员", "material_type": "version_announcement"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r5.status_code == 200
        assert r5.json()["content"] == "edited content"
        assert r5.json()["cached"] is True
        print("generate after edit returns edited content ok")

    print("E2E generated material smoke test passed")


if __name__ == "__main__":
    main()
