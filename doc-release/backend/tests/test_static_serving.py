"""静态托管与 SPA 回退：部署形态下由后端同端口服务前端产物。"""
from pathlib import Path

from fastapi import FastAPI
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


async def test_dev_mode_root_still_404(client):
    """仓库内无 backend/static/ 时，全局 app 的 / 保持 404（开发模式回归）。"""
    resp = await client.get("/")
    assert resp.status_code == 404
