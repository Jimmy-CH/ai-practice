"""海报配图服务层测试：星语文生图封装 / _chat 透传 / 提炼 / 生图落盘。全部 mock 网络调用。"""
import pytest

from app.services import xingyu_api


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _image_payload(content="http://oss/img.png"):
    return {
        "status": 0,
        "data": {
            "contents": [{"index": 0, "content": content, "reasoningContent": None}],
            "results": None,
        },
    }


def test_text_to_image_prefers_contents(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, data=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return FakeResponse(payload=_image_payload("http://oss/from-contents.png"))

    monkeypatch.setattr(xingyu_api.requests, "post", fake_post)
    url = xingyu_api.xingyu_text_to_image_api("一只橙猫")
    assert url == "http://oss/from-contents.png"
    assert captured["url"] == xingyu_api.image_url
    assert '"async": false' in captured["data"]
    assert xingyu_api.image_robot_code in captured["data"]


def test_text_to_image_falls_back_to_results(monkeypatch):
    payload = {"status": 0, "data": {"contents": [], "results": ["http://oss/from-results.png"]}}

    def fake_post(url, headers=None, data=None, timeout=None):
        return FakeResponse(payload=payload)

    monkeypatch.setattr(xingyu_api.requests, "post", fake_post)
    assert xingyu_api.xingyu_text_to_image_api("p") == "http://oss/from-results.png"


def test_text_to_image_returns_none_on_error_status(monkeypatch):
    payload = {"status": 400, "message": "请求阿里云后端文生图服务失败!", "data": None}

    def fake_post(url, headers=None, data=None, timeout=None):
        return FakeResponse(payload=payload, text='{"status": 400}')

    monkeypatch.setattr(xingyu_api.requests, "post", fake_post)
    assert xingyu_api.xingyu_text_to_image_api("p") is None


def test_text_to_image_returns_none_on_network_exc(monkeypatch):
    def fake_post(url, headers=None, data=None, timeout=None):
        raise xingyu_api.requests.ConnectionError("boom")

    monkeypatch.setattr(xingyu_api.requests, "post", fake_post)
    assert xingyu_api.xingyu_text_to_image_api("p") is None


@pytest.mark.asyncio
async def test_generate_poster_image_url_async_wrapper(monkeypatch):
    monkeypatch.setattr(xingyu_api, "xingyu_text_to_image_api", lambda p: "http://oss/ok.png")
    assert await xingyu_api.generate_poster_image_url("p") == "http://oss/ok.png"


@pytest.mark.asyncio
async def test_generate_poster_image_url_raises_without_url(monkeypatch):
    monkeypatch.setattr(xingyu_api, "xingyu_text_to_image_api", lambda p: None)
    try:
        await xingyu_api.generate_poster_image_url("p")
        assert False, "应抛 RuntimeError"
    except RuntimeError:
        pass


async def _fake_xingyu_capture(captured, system_prompt, user_prompt):
    captured["system"] = system_prompt
    captured["user"] = user_prompt
    return "ok"


@pytest.mark.asyncio
async def test_chat_passes_system_role_to_xingyu(monkeypatch):
    from app.services import material_writer

    captured = {}
    monkeypatch.setattr(material_writer.settings, "llm_provider", "xingyu")
    monkeypatch.setattr(
        material_writer,
        "generate_by_xingyu",
        lambda s, u: _fake_xingyu_capture(captured, s, u),
    )
    result = await material_writer._chat(
        [
            {"role": "system", "content": "你是视觉设计师。"},
            {"role": "user", "content": "描述一只猫"},
        ]
    )
    assert result == "ok"
    assert captured["system"] == "你是视觉设计师。"
    assert captured["user"] == "描述一只猫"


@pytest.mark.asyncio
async def test_chat_keeps_default_system_without_system_msg(monkeypatch):
    from app.services import material_writer

    captured = {}
    monkeypatch.setattr(material_writer.settings, "llm_provider", "xingyu")
    monkeypatch.setattr(
        material_writer,
        "generate_by_xingyu",
        lambda s, u: _fake_xingyu_capture(captured, s, u),
    )
    await material_writer._chat([{"role": "user", "content": "写一篇宣发稿"}])
    assert captured["system"] == "你是一名资深运营文案。"
