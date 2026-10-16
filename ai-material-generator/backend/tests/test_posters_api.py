"""海报配图 API 测试：5 端点。全部 mock 星语网络调用与生图链路。"""
import pytest

from app.services import poster_writer

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731


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
