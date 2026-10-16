"""海报配图服务层测试：星语文生图封装 / _chat 透传 / 提炼 / 生图落盘。全部 mock 网络调用。"""
import pytest
import pytest_asyncio

from app.models import poster_image  # noqa: F401  注册两张海报表进 Base.metadata
from app.services import poster_image_service  # noqa: F401
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


@pytest.mark.asyncio
async def test_compute_script_hash_stable():
    from app.models.poster_image import compute_script_hash

    assert compute_script_hash("abc") == compute_script_hash("abc")
    # md5 跨进程稳定（不受 PYTHONHASHSEED 影响）
    assert compute_script_hash("x") == "9dd4e461268c8034f5c8564e155c67a6"


@pytest.mark.asyncio
async def test_poster_prompt_upsert_and_owner_isolation(db_session):
    from app.models.poster_image import compute_script_hash
    from app.services import poster_image_service as poster_svc

    h = compute_script_hash("脚本A")
    first = await poster_svc.upsert_poster_prompt(db_session, 1, h, "描述v1")
    got = await poster_svc.get_poster_prompt(db_session, 1, h)
    assert got is not None and got.id == first.id and got.prompt == "描述v1"
    # 同 owner 同脚本：覆盖更新（同一条记录）
    updated = await poster_svc.upsert_poster_prompt(db_session, 1, h, "描述v2")
    assert updated.id == first.id and updated.prompt == "描述v2"
    # 不同 owner 不共享缓存
    assert await poster_svc.get_poster_prompt(db_session, 2, h) is None


@pytest.mark.asyncio
async def test_poster_image_crud_and_to_dict(db_session):
    from app.services import poster_image_service as poster_svc

    image = await poster_svc.create_poster_image(
        db_session, 1, "标题T", "网点管理员", "一只橙猫", "poster_images/1/a.png", 123
    )
    got = await poster_svc.get_poster_image_by_id(db_session, image.id)
    assert got is not None and got.prompt == "一只橙猫"
    d = got.to_dict()
    assert d["image_url"] == f"/api/posters/images/{got.id}/file"
    assert "file_path" not in d  # 内部路径不外露
    items = await poster_svc.list_poster_images(db_session, 1, "标题T", "网点管理员")
    assert [i.id for i in items] == [image.id]
    assert await poster_svc.list_poster_images(db_session, 2, "标题T", "网点管理员") == []
    await poster_svc.delete_poster_image(db_session, got)
    assert await poster_svc.get_poster_image_by_id(db_session, image.id) is None


@pytest.mark.asyncio
async def test_refine_poster_prompt_composes_messages_and_strips(monkeypatch):
    from app.services import poster_writer

    captured = {}

    async def fake_chat(messages):
        captured["messages"] = messages
        return "  一只橙猫坐在草地上，扁平插画风格，阳光明媚  "

    monkeypatch.setattr(poster_writer.material_writer, "_chat", fake_chat)
    result = await poster_writer.refine_poster_prompt("# 网点管家升级海报\n卖点：一键上报")
    assert result == "一只橙猫坐在草地上，扁平插画风格，阳光明媚"
    assert captured["messages"][0]["role"] == "system"
    assert "视觉设计" in captured["messages"][0]["content"]
    assert "海报脚本" in captured["messages"][1]["content"]
    assert "一键上报" in captured["messages"][1]["content"]


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32


@pytest.mark.asyncio
async def test_generate_poster_image_downloads_and_validates(monkeypatch):
    from app.services import poster_writer

    async def fake_url(prompt):
        return "http://oss/img.png"

    class FakeResp:
        status_code = 200
        content = PNG_BYTES

    monkeypatch.setattr(poster_writer, "generate_poster_image_url", fake_url)
    monkeypatch.setattr(poster_writer.requests, "get", lambda url, timeout: FakeResp())
    url, data = await poster_writer.generate_poster_image("橙猫草地")
    assert url == "http://oss/img.png"
    assert data == PNG_BYTES


@pytest.mark.asyncio
async def test_generate_poster_image_rejects_non_png(monkeypatch):
    from app.services import poster_writer

    async def fake_url(prompt):
        return "http://oss/img.png"

    class FakeResp:
        status_code = 200
        content = b"<html>not an image</html>"

    monkeypatch.setattr(poster_writer, "generate_poster_image_url", fake_url)
    monkeypatch.setattr(poster_writer.requests, "get", lambda url, timeout: FakeResp())
    try:
        await poster_writer.generate_poster_image("p")
        assert False, "非 PNG 应抛 RuntimeError"
    except RuntimeError as exc:
        assert "PNG" in str(exc)


def test_save_and_remove_poster_image(tmp_path, monkeypatch):
    from app.services import poster_writer

    monkeypatch.setattr(poster_writer, "POSTER_IMAGE_DIR", tmp_path / "poster_images")
    rel_path = poster_writer.save_poster_image(7, PNG_BYTES)
    assert rel_path.replace("\\", "/").startswith("poster_images/7/")
    absolute = tmp_path / rel_path
    assert absolute.is_file() and absolute.read_bytes() == PNG_BYTES
    # 删除（含不存在路径不报错）
    poster_writer.remove_poster_image(rel_path)
    assert not absolute.exists()
    poster_writer.remove_poster_image(rel_path)
