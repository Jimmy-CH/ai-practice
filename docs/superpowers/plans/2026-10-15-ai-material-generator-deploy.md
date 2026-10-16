# ai-material-generator 内网 Linux 部署实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ai-material-generator 提供内网 Linux 一键部署能力：后端单端口（8081）同源托管前端产物 + 部署脚手架（构包/安装/升级/回滚）。

**Architecture:** 复刻 doc-release 已验证模式——`main.py` 移植 `register_static()`（StaticFiles + SPA fallback + 307/405 补偿），`deploy/` 脚手架含构包 PowerShell 脚本与部署机 bash 安装脚本（在线 pip 安装，非离线 wheel）。设计文档：仓库根 `docs/superpowers/specs/2026-10-15-ai-material-generator-deploy-design.md`。

**Tech Stack:** FastAPI 0.141.1 / uvicorn / pytest-asyncio（asyncio_mode=auto）/ Vue 3 + Vite / systemd / rsync / bash / PowerShell 5.1。

**关键约束（执行前必读）：**
- 后端测试必须用 venv 解释器：`cd ai-material-generator/backend` 后 `.\venv\Scripts\python.exe -m pytest`，直接 `python -m pytest` 会缺依赖。
- git commit 消息含中文/括号时用单引号包裹（PowerShell 5.1）。
- 开发/测试期后端用 8001 端口（8000 常被残留进程占用）。
- 仓库 `ai-material-generator/backend/static/` 是端到端验证的临时产物，验证完必须删除（`test_dev_mode_root_still_404` 依赖它不存在）。

---

## 文件结构总览

| 文件 | 动作 | 职责 |
|---|---|---|
| `ai-material-generator/backend/app/config.py` | 修改 | 新增 `static_dir` 配置项 |
| `ai-material-generator/backend/app/main.py` | 修改 | 新增 `register_static()` 与末尾调用 |
| `ai-material-generator/backend/tests/test_static_serving.py` | 新建 | 静态托管/SPA 回退/307/405 补偿测试 |
| `ai-material-generator/deploy/env.template` | 新建 | 部署 .env 模板 |
| `ai-material-generator/deploy/material-gen.service` | 新建 | systemd 单元模板 |
| `ai-material-generator/deploy/install.sh` | 新建 | 安装/升级入口 |
| `ai-material-generator/deploy/build_package.ps1` | 新建 | Windows 开发机构包 |
| `ai-material-generator/deploy/README.md` | 新建 | 部署操作手册 |
| `ai-material-generator/.gitignore` | 修改 | 追加 `out/` 与 `backend/static/` |

---

### Task 1: 静态托管测试先行（TDD 红）

**Files:**
- Create: `ai-material-generator/backend/tests/test_static_serving.py`

- [ ] **Step 1: 创建测试文件（完整内容如下）**

```python
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
    (static_dir / "index.html").write_text("<html>materialgen</html>", encoding="utf-8")


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
    assert "materialgen" in resp.text


async def test_asset_file_served(tmp_path):
    """static/ 下真实文件可被访问（临时构造 assets/app.js 验证）。"""
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
        resp = await c.get("/materials/abc123")
    assert resp.status_code == 200
    assert "materialgen" in resp.text


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
    """模拟真实业务路由结构（include_router + prefix + 动态参数），验证尾斜杠补偿。"""
    app = FastAPI()
    router = APIRouter()

    @router.get("/materials")
    async def list_materials():
        return []

    @router.post("/materials")
    async def create_material():
        return {}

    @router.get("/materials/{material_id}")
    async def get_material(material_id: int):
        return {}

    app.include_router(router, prefix="/api")
    register_static(app, static_dir)
    return app


async def test_api_trailing_slash_included_router(tmp_path):
    """include_router 注册的业务路径带尾斜杠仍保持原生 307。"""
    static_dir = tmp_path / "static"
    _write_index(static_dir)
    app = _make_api_app(static_dir)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/materials/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].endswith("/api/materials")


async def test_api_trailing_slash_keeps_query_and_params(tmp_path):
    """动态参数路径 + 查询串：307 重定向需保留两者。"""
    static_dir = tmp_path / "static"
    _write_index(static_dir)
    app = _make_api_app(static_dir)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/materials/1/?audience=branch", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].endswith("/api/materials/1?audience=branch")


async def test_api_trailing_slash_non_get_methods(tmp_path):
    """POST 带尾斜杠也保持 307，不被 GET/HEAD catch-all 压成 405。"""
    static_dir = tmp_path / "static"
    _write_index(static_dir)
    app = _make_api_app(static_dir)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        post_resp = await c.post("/api/materials/", follow_redirects=False)
    assert post_resp.status_code == 307
    assert post_resp.headers["location"].endswith("/api/materials")


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


async def test_api_method_not_allowed_kept(tmp_path):
    """已注册路径的方法不匹配保持原生 405 + Allow，不被 catch-all 压成 404。"""
    static_dir = tmp_path / "static"
    _write_index(static_dir)
    app = _make_api_app(static_dir)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        patch_resp = await c.patch("/api/materials")
        options_resp = await c.options("/api/materials")
    assert patch_resp.status_code == 405
    assert {"GET", "POST"} <= set(patch_resp.headers["allow"].split(", "))
    assert options_resp.status_code == 405


async def test_real_app_trailing_slash(client):
    """真实应用的 /api/health 带尾斜杠同样保持 307（回归门禁）。"""
    resp = await client.get("/api/health/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].endswith("/api/health")


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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd D:\StudyProjects\ai-practice\ai-material-generator\backend; .\venv\Scripts\python.exe -m pytest tests/test_static_serving.py -q`
Expected: 收集阶段 ERROR —— `ImportError: cannot import name 'register_static' from 'app.main'`

---

### Task 2: 实现 register_static（TDD 绿）

**Files:**
- Modify: `ai-material-generator/backend/app/config.py`
- Modify: `ai-material-generator/backend/app/main.py`

- [ ] **Step 1: config.py 新增 static_dir 配置**

在 `algorithm: str = "HS256"` 之后加一行：

```python
    static_dir: str = "static"
```

- [ ] **Step 2: main.py 增补 imports**

将现有 imports 头部（`import json` 至 `from app.services.auth_service import seed_users`）改为：

```python
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.routing import Match

from app.api.generator import router as generator_router
from app.api.auth import router as auth_router
from app.api.materials import router as materials_router
from app.api.analyses import router as analyses_router
from app.api.generated_materials import router as generated_materials_router
from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.services.auth_service import seed_users
```

变化点：新增 `Path`、`FileResponse/JSONResponse/RedirectResponse`、`StaticFiles`、`Match`、`from app.config import settings`。

- [ ] **Step 3: main.py 末尾追加 register_static（在 `/api/health` 路由之后）**

```python
def register_static(app: FastAPI, static_dir: Path) -> None:
    """挂载前端产物与 SPA 回退；目录不存在时跳过（开发模式不受影响）。

    必须在所有 API 路由注册之后调用，避免 catch-all 拦截 /api。
    """
    if not static_dir.is_dir():
        return
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # catch-all 会拦截 Starlette 的尾斜杠重定向，这里用框架真实路由匹配补偿该行为
    # （include_router 生成的路由无 path 属性，不能用路径字符串白名单）
    def _matches_other_route(path: str, method: str) -> bool:
        scope = {"type": "http", "path": path, "method": method, "headers": []}
        for route in app.routes:
            if getattr(route, "path", None) == "/{full_path:path}":
                continue
            match, _child = route.matches(scope)
            if match != Match.NONE:
                return True
        return False

    def _partial_match_methods(path: str, method: str) -> list[str]:
        """路径已注册但方法不匹配时返回允许的方法，复刻原生 405/Allow 语义。"""
        scope = {"type": "http", "path": path, "method": method, "headers": []}
        methods: set[str] = set()
        for route in app.routes:
            if getattr(route, "path", None) == "/{full_path:path}":
                continue
            match, _child = route.matches(scope)
            if match == Match.PARTIAL:
                methods |= _collect_methods(route, scope)
        return sorted(methods)

    def _collect_methods(route, scope: dict) -> set[str]:
        """聚合路由允许的方法；兼容无 methods 属性的聚合路由（FastAPI 0.141 _IncludedRouter）。"""
        methods = getattr(route, "methods", None)
        if methods:
            return {m for m in methods if m != "HEAD"}
        result: set[str] = set()
        inner = getattr(route, "original_router", None)
        for sub in getattr(inner, "routes", None) or []:
            match, _child = sub.matches(scope)
            if match != Match.NONE:
                result |= _collect_methods(sub, scope)
        return result

    @app.api_route(
        "/{full_path:path}",
        methods=["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        include_in_schema=False,
    )
    async def spa_fallback(request: Request, full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            if full_path.endswith("/"):
                target = "/" + full_path.rstrip("/")
                if _matches_other_route(target, request.method):
                    query = request.scope.get("query_string", b"")
                    location = target + (f"?{query.decode('latin-1')}" if query else "")
                    return RedirectResponse(location, status_code=307)
            else:
                allowed = _partial_match_methods("/" + full_path, request.method)
                if allowed:
                    return JSONResponse(
                        {"detail": "Method Not Allowed"},
                        status_code=405,
                        headers={"Allow": ", ".join(allowed)},
                    )
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if request.method in ("GET", "HEAD"):
            candidate = (static_dir / full_path).resolve()
            if full_path and candidate.is_file() and candidate.is_relative_to(static_dir.resolve()):
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")
        return JSONResponse({"detail": "Not Found"}, status_code=404)


register_static(app, Path(settings.static_dir))
```

- [ ] **Step 4: 运行静态托管测试验证通过**

Run: `cd D:\StudyProjects\ai-practice\ai-material-generator\backend; .\venv\Scripts\python.exe -m pytest tests/test_static_serving.py -q`
Expected: `15 passed`（全部通过，秒级完成）

- [ ] **Step 5: 全量回归**

Run: `cd D:\StudyProjects\ai-practice\ai-material-generator\backend; .\venv\Scripts\python.exe -m pytest tests -q`
Expected: `66 passed`（51 既有 + 15 新增）且总耗时约 30 秒内。若显著超时说明有用例打到真实星语网关，需排查。

---

### Task 3: 提交静态托管改动

**Files:** Task 1-2 的三个文件

- [ ] **Step 1: 提交**

```powershell
git add ai-material-generator/backend/app/config.py ai-material-generator/backend/app/main.py ai-material-generator/backend/tests/test_static_serving.py
git commit -m 'feat: 后端单端口托管前端产物与 SPA 回退'
```

---

### Task 4: 部署脚手架——env.template 与 systemd 单元

**Files:**
- Create: `ai-material-generator/deploy/env.template`
- Create: `ai-material-generator/deploy/material-gen.service`

- [ ] **Step 1: 创建 env.template（完整内容）**

```env
# 大模型提供方：xingyu（默认，内网星语网关，地址硬编码于 app/services/xingyu_api.py）
LLM_PROVIDER=xingyu
# DeepSeek 回退配置（仅 LLM_PROVIDER=deepseek 时必填 API_KEY）
# LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

注意：`LLM_PROVIDER=deepseek` 保持注释状态，取消注释会与上方 `LLM_PROVIDER=xingyu` 重复定义，部署人需自行二选一（模板内注释已说明）。

- [ ] **Step 2: 创建 material-gen.service（完整内容，`__XXX__` 占位符由 install.sh sed 注入）**

```ini
[Unit]
Description=MaterialGen (AI 运营物料智能生成助手) backend + frontend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=__APP_USER__
WorkingDirectory=__DEPLOY_ROOT__/backend
ExecStart=__DEPLOY_ROOT__/backend/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port __PORT__
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

---

### Task 5: 部署脚手架——install.sh

**Files:**
- Create: `ai-material-generator/deploy/install.sh`

- [ ] **Step 1: 创建 install.sh（完整内容）**

```bash
#!/usr/bin/env bash
# MaterialGen 安装/升级脚本（在部署机的部署包目录内执行）
# 用法：sudo bash install.sh
# 可覆盖默认：DEPLOY_ROOT=/opt/material-gen PORT=8081 APP_USER=materialgen
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/material-gen}"
APP_USER="${APP_USER:-materialgen}"
SERVICE_NAME="material-gen"
PORT="${PORT:-8081}"
XINGYU_URL="${XINGYU_URL:-http://10.130.13.74:8060/api/chat/chat}"

log() { echo "[install] $*"; }
die() { echo "[install][ERROR] $*" >&2; exit 1; }

# ---- 1. 前置检查 ----
command -v python3.11 >/dev/null || die "缺少 python3.11，请先安装"
command -v rsync >/dev/null || die "缺少 rsync"
if curl -sS --max-time 5 -o /dev/null "$XINGYU_URL"; then
  log "星语网关可达"
else
  log "警告：星语网关暂不可达（$XINGYU_URL），继续安装；运行期生成/解析将失败"
fi
[ -d "$PKG_ROOT/backend" ] || die "部署包不完整：缺少 backend/"
[ -d "$PKG_ROOT/static" ] || die "部署包不完整：缺少 static/（请先在开发机执行 build_package.ps1）"
[ -d "$PKG_ROOT/deploy" ] || die "部署包不完整：缺少 deploy/"

# 升级场景：先停旧服务释放端口（首次安装无单元则跳过）
if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
  log "检测到已安装的 ${SERVICE_NAME}，先停止以完成升级"
  systemctl stop "$SERVICE_NAME" || true
fi
if ss -ltn 2>/dev/null | grep -q ":${PORT} "; then
  die "端口 ${PORT} 被其他进程占用，请先释放，或以 PORT=其他端口 重跑"
fi

# ---- 2. 系统用户 ----
if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --shell /usr/sbin/nologin --home-dir "$DEPLOY_ROOT" "$APP_USER"
  log "已创建系统用户 $APP_USER"
fi

# ---- 3. 铺设文件（现场数据全保留：venv/.env/materials.db）----
mkdir -p "$DEPLOY_ROOT/packages"
rsync -a --delete \
  --exclude "venv/" --exclude ".env" --exclude "materials.db" \
  --exclude "static/" \
  "$PKG_ROOT/backend/" "$DEPLOY_ROOT/backend/"
rsync -a --delete "$PKG_ROOT/static/" "$DEPLOY_ROOT/backend/static/"
rsync -a --delete "$PKG_ROOT/deploy/" "$DEPLOY_ROOT/deploy/"
if [ -f "$PKG_ROOT/MANIFEST.md" ]; then cp -f "$PKG_ROOT/MANIFEST.md" "$DEPLOY_ROOT/MANIFEST.md"; fi

# ---- 4. venv 与在线依赖 ----
VENV_PY="$DEPLOY_ROOT/backend/venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  python3.11 -m venv "$DEPLOY_ROOT/backend/venv"
  log "已创建 venv"
fi
"$VENV_PY" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)' \
  || die "venv Python 版本不是 3.11，请删除 $DEPLOY_ROOT/backend/venv 后重跑"
if ! curl -sS --max-time 5 -o /dev/null "${PIP_INDEX_URL:-https://pypi.org/simple}/pip/"; then
  log "警告：pip 源（${PIP_INDEX_URL:-默认官方源}）暂不可达，若安装失败请配置内网源后重跑"
fi
"$VENV_PY" -m pip install -r "$DEPLOY_ROOT/backend/requirements.txt"

# ---- 5. .env 初始化（存在则保留现场配置）----
if [ ! -f "$DEPLOY_ROOT/backend/.env" ]; then
  cp "$DEPLOY_ROOT/deploy/env.template" "$DEPLOY_ROOT/backend/.env"
  log "已从模板初始化 .env"
fi

# ---- 6. systemd ----
sed -e "s#__APP_USER__#$APP_USER#g" \
    -e "s#__DEPLOY_ROOT__#$DEPLOY_ROOT#g" \
    -e "s#__PORT__#$PORT#g" \
    "$DEPLOY_ROOT/deploy/material-gen.service" > "/etc/systemd/system/${SERVICE_NAME}.service"
chown -R "$APP_USER":"$APP_USER" "$DEPLOY_ROOT"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null
systemctl restart "$SERVICE_NAME"

# ---- 7. 健康检查（30 秒上限）----
log "等待服务就绪…"
for _ in $(seq 1 15); do
  if curl -sf "http://127.0.0.1:${PORT}/api/health" >/dev/null; then
    log "安装完成：http://<本机>:${PORT}/（systemctl status ${SERVICE_NAME} 查看状态）"
    exit 0
  fi
  sleep 2
done
echo "[install][ERROR] 健康检查未通过，排查：journalctl -u ${SERVICE_NAME} -n 50" >&2
exit 1
```

与 doc-release 版的差异：无 wheels（在线 pip 安装 + pip 源探测仅警告）；排除 `materials.db`（无 archive/sample_repo）；前置检查无 git（本项目不需要）；健康检查 30 秒上限；unit 模板名 `material-gen.service`。

- [ ] **Step 2: bash 语法检查**

Run: `bash -n D:/StudyProjects/ai-practice/ai-material-generator/deploy/install.sh`
Expected: 无输出（语法正确）

---

### Task 6: 部署脚手架——build_package.ps1 与 .gitignore

**Files:**
- Create: `ai-material-generator/deploy/build_package.ps1`
- Modify: `ai-material-generator/.gitignore`

- [ ] **Step 1: 创建 build_package.ps1（完整内容）**

```powershell
# MaterialGen 部署包构建脚本（开发机 Windows 执行）
# 用法：cd ai-material-generator; .\deploy\build_package.ps1
# 产物：out/materialgen-package-<日期>.zip（依赖在线安装，不含 wheels）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot   # ai-material-generator/
$stamp = Get-Date -Format "yyyyMMdd"
$outDir = Join-Path $root "out\materialgen-package-$stamp"
if (Test-Path $outDir) { $outDir = "$outDir-$(Get-Date -Format 'HHmmss')" }
Write-Host "[build] 输出目录：$outDir"

# 1. 前端构建
Push-Location (Join-Path $root "frontend")
try { npm run build } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }

# 2. 目录骨架
foreach ($d in @("backend", "deploy")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $outDir $d) | Out-Null
}

# 3. 后端源码：app/ 与 requirements.txt（运行最小集，不含 tests/venv/db/.env）
Copy-Item (Join-Path $root "backend\app") (Join-Path $outDir "backend\app") -Recurse
Copy-Item (Join-Path $root "backend\requirements.txt") (Join-Path $outDir "backend\requirements.txt")
Get-ChildItem (Join-Path $outDir "backend\app") -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# 4. 前端产物 → static/；deploy 脚手架
Copy-Item (Join-Path $root "frontend\dist") (Join-Path $outDir "static") -Recurse
Copy-Item (Join-Path $root "deploy\*") (Join-Path $outDir "deploy\") -Recurse

# 5. MANIFEST.md
$commit = (git -C $root rev-parse HEAD).Trim()
$dirty = (git -C $root status --porcelain) -join "; "
if ($dirty) { Write-Warning "工作区有未提交改动，MANIFEST 记录的 commit 可能与包内容不一致" }
@(
    "# MaterialGen 部署包",
    "- 构建时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "- 源码 commit：$commit",
    "- 包结构：backend/（后端源码）static/（前端产物）deploy/（安装脚手架）",
    "- 部署：解压后在包内 deploy/ 执行 sudo bash install.sh（详见 deploy/README.md）"
) | Set-Content (Join-Path $outDir "MANIFEST.md") -Encoding utf8

# 6. 压缩
$zip = "$outDir.zip"
Compress-Archive -Path $outDir -DestinationPath $zip -Force
Write-Host "[build] 完成：$zip"
```

- [ ] **Step 2: .gitignore 追加（在 `# OS` 段之前插入）**

```gitignore
# 部署构建产物
out/
backend/static/
```

---

### Task 7: 部署脚手架——README 与提交

**Files:**
- Create: `ai-material-generator/deploy/README.md`

- [ ] **Step 1: 创建 deploy/README.md（完整内容）**

```markdown
# MaterialGen 部署脚手架

内网 Linux 部署（设计文档：仓库根 `docs/superpowers/specs/2026-10-15-ai-material-generator-deploy-design.md`）。
单端口同源托管：uvicorn :8081 同时服务页面与 API。依赖经部署机 pip 源在线安装（无需离线 wheel）。

## 一、开发机构建部署包（Windows）

```powershell
cd ai-material-generator
.\deploy\build_package.ps1
```

产物：`out/materialgen-package-<日期>.zip`（前端 dist 产物 + 后端源码 + 脚手架 + MANIFEST.md）。

## 二、上传与解压（部署机）

```bash
sudo mkdir -p /opt/material-gen/packages
sudo unzip materialgen-package-<日期>.zip -d /opt/material-gen/packages/
```

## 三、安装 / 升级（同一入口）

前置：`python3.11`、`rsync`；pip 源可达（内网源用 `PIP_INDEX_URL` 指定）。星语网关不通仅警告，不阻断安装。

```bash
cd /opt/material-gen/packages/materialgen-package-<日期>/deploy
sudo bash install.sh
# 可覆盖默认值：sudo DEPLOY_ROOT=/opt/material-gen PORT=8081 APP_USER=materialgen bash install.sh
```

脚本行为：前置检查 →（升级时先停旧服务释放端口，首次安装直接检查端口）→
rsync 源码与 static（排除 venv/.env/materials.db，现场数据保留）→
venv 缺失则创建（Python 3.11）→ 在线安装依赖 → .env 缺失则从模板初始化 →
安装并启动 systemd 服务 → 健康检查。

## 四、部署后验证清单

1. `systemctl status material-gen` → active (running)
2. `curl http://<host>:8081/api/health` → `{"status":"ok"}`
3. 浏览器 `http://<host>:8081/` → 登录页加载；直刷 `/materials`、`/review` 不 404
4. editor/editor123 登录 → 粘贴文本解析 → 生成物料 → 保存草稿；
   reviewer/reviewer123 登录 → 审核通过 → 「已审核」页下载 Markdown

## 五、升级与回滚

- 升级：新包解压到 `packages/` 后重跑 `install.sh`（db/.env/venv 全保留，新列由启动期幂等迁移自动补齐）
- 回滚（用旧包覆盖部署目录后重启）：

```bash
sudo rsync -a --exclude "venv/" --exclude ".env" --exclude "materials.db" \
  --exclude "static/" \
  /opt/material-gen/packages/<旧包>/backend/ /opt/material-gen/backend/
sudo rsync -a /opt/material-gen/packages/<旧包>/static/ /opt/material-gen/backend/static/
sudo systemctl restart material-gen
```
```

- [ ] **Step 2: 提交全部部署脚手架**

```powershell
git add ai-material-generator/deploy ai-material-generator/.gitignore
git commit -m 'chore: 部署脚手架 env/service/install/构包脚本/手册'
```

---

### Task 8: 本机端到端模拟验证（部署形态冒烟）

**Files:** 无新增；临时创建 `ai-material-generator/backend/static/`，结束必须删除。

- [ ] **Step 1: 构建前端并模拟部署目录结构**

```powershell
cd D:\StudyProjects\ai-practice\ai-material-generator\frontend
npm run build
Copy-Item -Recurse -Force .\dist D:\StudyProjects\ai-practice\ai-material-generator\backend\static
```

Expected: `npm run build` 无报错；`backend/static/index.html` 存在。

- [ ] **Step 2: 以部署形态启动后端（8001 端口，后台）**

```powershell
cd D:\StudyProjects\ai-practice\ai-material-generator\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

后台运行，等待启动日志 `Uvicorn running on http://127.0.0.1:8001`。

- [ ] **Step 3: 逐项验证（curl.exe，PowerShell 5.1 下勿用 curl 别名）**

```powershell
curl.exe -s http://127.0.0.1:8001/api/health
# Expected: {"status":"ok"}

curl.exe -s http://127.0.0.1:8001/ | Select-String -Pattern "<!DOCTYPE html>|<!doctype html>"
# Expected: 命中（返回 index.html）

curl.exe -s http://127.0.0.1:8001/materials | Select-String -Pattern "<!DOCTYPE html>|<!doctype html>"
# Expected: 命中（SPA fallback，直刷不 404）

curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8001/api/nonexistent
# Expected: 404

curl.exe -s -X PATCH -o NUL -w "%{http_code}" http://127.0.0.1:8001/api/health
# Expected: 405
```

- [ ] **Step 4: 停止服务并清理临时 static**

```powershell
# 记下 Step 2 终端输出的进程号 <PID>，精确停止：
Stop-Process -Id <PID> -Force
Remove-Item -Recurse -Force D:\StudyProjects\ai-practice\ai-material-generator\backend\static
```

注意：`backend/static` 必须删除，否则 `test_dev_mode_root_still_404` 在后续回归中失败。

- [ ] **Step 5: 清理后最终回归**

Run: `cd D:\StudyProjects\ai-practice\ai-material-generator\backend; .\venv\Scripts\python.exe -m pytest tests -q`
Expected: `66 passed`

- [ ] **Step 6: 确认工作区干净**

Run: `git status --short`
Expected: 无 ai-material-generator 相关未跟踪文件（static 已删、out/ 已忽略）。

---

## 自审记录

- **Spec 覆盖**：设计文档 §4 代码改动 → Task 1-3；§5 脚手架五件套 → Task 4-7；§7 验证清单 1-3 → Task 8（清单 4 需真实内网机星语网关，属部署现场动作，写入 deploy/README）；§8 测试与回归 → Task 1/2/8；§6 数据生命周期 → install.sh 排除项与 README 升级/回滚章节。无缺口。
- **占位符**：install.sh / service 模板中 `__APP_USER__` 等为约定的 sed 注入占位符，非计划缺陷；无 TBD/TODO。
- **类型一致性**：`register_static(app: FastAPI, static_dir: Path)` 签名在测试与实现一致；`SERVICE_NAME="material-gen"` 与 unit 文件名 `material-gen.service` 一致；端口 8081 在 install.sh 默认值、README、验证命令一致。
