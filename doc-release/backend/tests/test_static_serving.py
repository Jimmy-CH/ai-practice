"""静态托管与 SPA 回退：部署形态下由后端同端口服务前端产物。"""
from pathlib import Path

from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import register_static


def _make_client(static_dir: Path) -> AsyncClient:
    app = FastAPI()
    register_static(app, static_dir)
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _write_index(static_dir: Path) -> None:
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "index.html").write_text("<html>docrelease</html>", encoding="utf-8")


async def test_no_static_dir_registers_nothing(tmp_path):
    """static 目录不存在时不新增任何路由（开发模式行为不变）。"""
    app = FastAPI()
    routes_before = len(app.routes)
    register_static(app, tmp_path / "static")
    assert len(app.routes) == routes_before


async def test_index_served(tmp_path):
    static_dir = tmp_path / "static"
    _write_index(static_dir)
    async with _make_client(static_dir) as c:
        resp = await c.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "docrelease" in resp.text


async def test_asset_file_served(tmp_path):
    static_dir = tmp_path / "static"
    assets = static_dir / "assets"
    assets.mkdir(parents=True)
    (assets / "app.js").write_text("console.log(1)", encoding="utf-8")
    async with _make_client(static_dir) as c:
        resp = await c.get("/assets/app.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]


async def test_spa_route_falls_back_to_index(tmp_path):
    """history 模式子路由直刷回退到 index.html。"""
    static_dir = tmp_path / "static"
    _write_index(static_dir)
    async with _make_client(static_dir) as c:
        resp = await c.get("/history/abc123")
    assert resp.status_code == 200
    assert "docrelease" in resp.text


async def test_api_prefix_not_masked_by_fallback(tmp_path):
    """以 api/ 开头的未匹配路径必须 404 JSON，不得回退成 index.html。"""
    static_dir = tmp_path / "static"
    _write_index(static_dir)
    async with _make_client(static_dir) as c:
        resp = await c.get("/api/nonexistent")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}


async def test_path_escape_cannot_read_outside(tmp_path):
    """路径穿越不得读到 static 目录之外的文件。"""
    (tmp_path / "secret.txt").write_text("TOP-SECRET", encoding="utf-8")
    static_dir = tmp_path / "static"
    _write_index(static_dir)
    async with _make_client(static_dir) as c:
        resp = await c.get("/..%2Fsecret.txt")
    assert "TOP-SECRET" not in resp.text


def _make_api_app(static_dir: Path) -> FastAPI:
    """模拟真实业务路由结构（include_router + 动态参数），验证尾斜杠补偿。"""
    app = FastAPI()
    router = APIRouter()

    @router.get("/api/repos")
    async def list_repos():
        return []

    @router.post("/api/repos")
    async def create_repo():
        return {}

    @router.delete("/api/repos/{repo_id}")
    async def delete_repo(repo_id: int):
        return {}

    @router.get("/api/repos/{repo_id}/preview")
    async def preview(repo_id: int):
        return {}

    app.include_router(router)
    register_static(app, static_dir)
    return app


async def test_api_trailing_slash_included_router(tmp_path):
    """include_router 注册的业务路径带尾斜杠仍保持原生 307（白名单方式无法覆盖此场景）。"""
    static_dir = tmp_path / "static"
    _write_index(static_dir)
    app = _make_api_app(static_dir)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/repos/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].endswith("/api/repos")


async def test_api_trailing_slash_keeps_query_and_params(tmp_path):
    """动态参数路径 + 查询串：307 重定向需保留两者。"""
    static_dir = tmp_path / "static"
    _write_index(static_dir)
    app = _make_api_app(static_dir)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/repos/1/preview/?base=a&head=b", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].endswith("/api/repos/1/preview?base=a&head=b")


async def test_api_trailing_slash_non_get_methods(tmp_path):
    """POST/DELETE 带尾斜杠也保持 307，不被 GET/HEAD catch-all 压成 405。"""
    static_dir = tmp_path / "static"
    _write_index(static_dir)
    app = _make_api_app(static_dir)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        post_resp = await c.post("/api/repos/", follow_redirects=False)
        del_resp = await c.delete("/api/repos/1/", follow_redirects=False)
    assert post_resp.status_code == 307
    assert post_resp.headers["location"].endswith("/api/repos")
    assert del_resp.status_code == 307
    assert del_resp.headers["location"].endswith("/api/repos/1")


async def test_api_trailing_slash_unknown_stays_404(tmp_path):
    """去尾斜杠后也无路由命中的路径仍为 404 JSON。"""
    static_dir = tmp_path / "static"
    _write_index(static_dir)
    app = _make_api_app(static_dir)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/nope/", follow_redirects=False)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}


async def test_real_app_trailing_slash(client):
    """真实应用的 include_router 路由同样保持 307（回归门禁）。"""
    resp = await client.get("/api/repos/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].endswith("/api/repos")


async def test_head_index(tmp_path):
    """静态入口支持 HEAD 请求（与 /assets 文件行为一致）。"""
    static_dir = tmp_path / "static"
    _write_index(static_dir)
    async with _make_client(static_dir) as c:
        resp = await c.head("/")
    assert resp.status_code == 200
    assert resp.content == b""


async def test_dev_mode_root_still_404(client):
    """仓库内无 backend/static/ 时，全局 app 的 / 保持 404（开发模式回归）。"""
    resp = await client.get("/")
    assert resp.status_code == 404
