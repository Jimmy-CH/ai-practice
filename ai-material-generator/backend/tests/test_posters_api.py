"""海报配图 API 测试：5 端点。全部 mock 星语网络调用与生图链路。"""
import pytest

from app.services import poster_writer

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def _mock_poster_generation(monkeypatch, tmp_path):
    """把生图链路整体 mock 掉：generate 返回固定字节，落盘目录指向 tmp。"""
    monkeypatch.setattr(poster_writer, "POSTER_IMAGE_DIR", tmp_path / "poster_images")

    async def fake_generate(prompt):
        return "http://oss/x.png", PNG_BYTES

    monkeypatch.setattr("app.services.poster_writer.generate_poster_image", fake_generate)


@pytest.mark.asyncio
async def test_refine_prompt_requires_login(client):
    r = await client.post("/api/posters/prompt", json={"script_content": "x"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refine_prompt_requires_editor(client, reviewer_token):
    r = await client.post(
        "/api/posters/prompt", json={"script_content": "x"}, headers=AUTH(reviewer_token)
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_refine_prompt_refines_then_caches(client, editor_token, monkeypatch):
    calls = []

    async def fake_refine(content):
        calls.append(content)
        return "一只橙猫在草地上，扁平插画风格"

    monkeypatch.setattr("app.services.poster_writer.refine_poster_prompt", fake_refine)
    payload = {"script_content": "# 海报\n卖点：一键上报"}
    r1 = await client.post("/api/posters/prompt", json=payload, headers=AUTH(editor_token))
    assert r1.status_code == 200
    assert r1.json() == {"prompt": "一只橙猫在草地上，扁平插画风格", "cached": False}
    r2 = await client.post("/api/posters/prompt", json=payload, headers=AUTH(editor_token))
    assert r2.status_code == 200
    assert r2.json() == {"prompt": "一只橙猫在草地上，扁平插画风格", "cached": True}
    assert len(calls) == 1  # 第二次命中缓存，不再调 chat


@pytest.mark.asyncio
async def test_refine_prompt_empty_content(client, editor_token):
    r = await client.post("/api/posters/prompt", json={"script_content": "  "}, headers=AUTH(editor_token))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_refine_prompt_502_on_refine_error(client, editor_token, monkeypatch):
    async def broken(content):
        raise RuntimeError("星语超时")

    monkeypatch.setattr("app.services.poster_writer.refine_poster_prompt", broken)
    r = await client.post(
        "/api/posters/prompt", json={"script_content": "x"}, headers=AUTH(editor_token)
    )
    assert r.status_code == 502
    assert "画面描述提炼失败" in r.json()["detail"]


@pytest.mark.asyncio
async def test_create_poster_image_generates_and_stores(client, editor_token, monkeypatch, tmp_path):
    _mock_poster_generation(monkeypatch, tmp_path)
    r = await client.post(
        "/api/posters/images",
        json={"source_title": "标题T", "audience": "网点管理员", "prompt": "一只橙猫"},
        headers=AUTH(editor_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["prompt"] == "一只橙猫"
    assert body["file_size"] == len(PNG_BYTES)
    assert body["image_url"] == f"/api/posters/images/{body['id']}/file"
    # 文件已真实落盘（在 tmp 内，不污染仓库）；to_dict 刻意不外露 file_path，用 rglob 校验
    stored_files = list((tmp_path / "poster_images").rglob("*.png"))
    assert len(stored_files) == 1 and stored_files[0].is_file()


@pytest.mark.asyncio
async def test_create_poster_image_requires_editor(client, reviewer_token, monkeypatch, tmp_path):
    _mock_poster_generation(monkeypatch, tmp_path)
    r = await client.post(
        "/api/posters/images",
        json={"source_title": "T", "audience": "A", "prompt": "p"},
        headers=AUTH(reviewer_token),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_poster_image_502_on_generation_error(client, editor_token, monkeypatch, tmp_path):
    _mock_poster_generation(monkeypatch, tmp_path)

    async def broken(prompt):
        raise RuntimeError("星语文生图未返回图片 URL")

    monkeypatch.setattr("app.services.poster_writer.generate_poster_image", broken)
    r = await client.post(
        "/api/posters/images",
        json={"source_title": "T", "audience": "A", "prompt": "p"},
        headers=AUTH(editor_token),
    )
    assert r.status_code == 502
    assert "海报图生成失败" in r.json()["detail"]


@pytest.mark.asyncio
async def test_list_poster_images_owner_and_combo_isolated(client, editor_token, monkeypatch, tmp_path):
    _mock_poster_generation(monkeypatch, tmp_path)
    for title, audience in [("T1", "网点管理员"), ("T1", "业务员"), ("T2", "网点管理员")]:
        await client.post(
            "/api/posters/images",
            json={"source_title": title, "audience": audience, "prompt": "p"},
            headers=AUTH(editor_token),
        )
    r = await client.get(
        "/api/posters/images",
        params={"source_title": "T1", "audience": "网点管理员"},
        headers=AUTH(editor_token),
    )
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["source_title"] == "T1"
    # reviewer 看不到 editor 的图
    r2 = await client.get(
        "/api/posters/images",
        params={"source_title": "T1", "audience": "网点管理员"},
        headers=AUTH(reviewer_token),
    )
    assert r2.json() == []
