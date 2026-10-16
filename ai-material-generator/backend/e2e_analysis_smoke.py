import httpx

BASE = "http://127.0.0.1:8001"


def login(username: str, password: str) -> str:
    r = httpx.post(f"{BASE}/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["access_token"]


def parse(token: str, title: str, content: str) -> dict:
    r = httpx.post(
        f"{BASE}/api/parse",
        data={"title": title, "content": content},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"parse failed: {r.text}"
    return r.json()


def update_analysis(token: str, analysis_id: int) -> dict:
    payload = {
        "new_features": ["编辑后新增"],
        "changes": ["编辑后变更"],
        "notices": ["编辑后注意"],
        "risks": ["编辑后风险"],
    }
    r = httpx.put(
        f"{BASE}/api/analyses/{analysis_id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"update failed: {r.text}"
    return r.json()


def generate(token: str, title: str, analysis: dict) -> dict:
    r = httpx.post(
        f"{BASE}/api/generate",
        json={
            "title": title,
            "analysis": analysis,
            "audience": "网点管理员",
            "material_type": "version_announcement",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"generate failed: {r.text}"
    return r.json()


def main():
    token = login("editor", "editor123")
    title = "E2E 测试文档"
    content = "本次新增一键上报功能，优化导入流程，注意升级版本，风险提示数据延迟。"

    # 首次解析（调用模型）
    first = parse(token, title, content)
    assert "analysis_id" in first
    aid = first["analysis_id"]
    print("first parse ok, analysis_id:", aid)

    # 更新解析结果
    updated = update_analysis(token, aid)
    assert updated["新增功能"] == ["编辑后新增"]
    print("update analysis ok")

    # 用编辑后的解析结果生成
    material = generate(token, title, updated)
    assert "content" in material
    print("generate with edited analysis ok")

    # 再次解析（应命中缓存，不调用模型）
    second = parse(token, title, content)
    assert second["analysis_id"] == aid
    assert second["新增功能"] == ["编辑后新增"]
    print("second parse (cache hit) ok")

    print("E2E analysis smoke test passed")


if __name__ == "__main__":
    main()
