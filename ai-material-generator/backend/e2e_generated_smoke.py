import httpx
from uuid import uuid4

BASE = "http://127.0.0.1:8001"


def login(username: str, password: str) -> str:
    r = httpx.post(f"{BASE}/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["access_token"]


def main():
    token = login("editor", "editor123")
    analysis = {"新增功能": ["A"], "变更与优化": [], "注意事项": [], "风险提示": []}
    title = f"E2E-{uuid4().hex[:8]}"

    # 首次生成
    r = httpx.post(
        f"{BASE}/api/generate",
        json={"title": title, "analysis": analysis, "audience": "网点管理员", "material_type": "version_announcement"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["cached"] is False
    gm_id = r.json()["id"]
    print("first generate ok")

    # 再次生成，应命中缓存
    r2 = httpx.post(
        f"{BASE}/api/generate",
        json={"title": title, "analysis": analysis, "audience": "网点管理员", "material_type": "version_announcement"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["cached"] is True
    print("cached generate ok")

    # 编辑缓存内容
    r3 = httpx.put(
        f"{BASE}/api/generated-materials/{gm_id}",
        json={"content": "edited content"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r3.status_code == 200
    assert r3.json()["content"] == "edited content"
    print("edit generated material ok")

    # 再次生成，应返回编辑后的内容
    r4 = httpx.post(
        f"{BASE}/api/generate",
        json={"title": title, "analysis": analysis, "audience": "网点管理员", "material_type": "version_announcement"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r4.status_code == 200
    assert r4.json()["content"] == "edited content"
    assert r4.json()["cached"] is True
    print("generate after edit returns edited content ok")

    print("E2E generated material smoke test passed")


if __name__ == "__main__":
    main()
