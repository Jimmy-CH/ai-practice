import httpx

BASE = "http://127.0.0.1:8001"


def login(username: str, password: str) -> str:
    r = httpx.post(f"{BASE}/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["access_token"]


def main():
    token = login("editor", "editor123")
    analysis = {"新增功能": ["A"], "变更与优化": [], "注意事项": [], "风险提示": []}

    # 首次生成
    r = httpx.post(
        f"{BASE}/api/generate",
        json={"title": "T", "analysis": analysis, "audience": "网点管理员", "material_type": "version_announcement"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["cached"] is False
    print("first generate ok")

    # 再次生成，应命中缓存
    r2 = httpx.post(
        f"{BASE}/api/generate",
        json={"title": "T", "analysis": analysis, "audience": "网点管理员", "material_type": "version_announcement"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["cached"] is True
    print("cached generate ok")

    print("E2E generated material smoke test passed")


if __name__ == "__main__":
    main()
