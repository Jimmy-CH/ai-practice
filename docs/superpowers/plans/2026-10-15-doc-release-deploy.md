# doc-release 内网 Linux 离线部署 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 doc-release 落地"内网 Linux 离线部署"能力：后端同端口托管前端产物（SPA 回退）、`deploy/` 脚手架（install.sh + systemd 单元 + env 模板）、开发机离线包构建脚本。

**Architecture:** 方案 A（FastAPI 单端口同源托管）——`main.py` 末尾注册静态挂载与 SPA catch-all（`static/` 不存在则零影响，开发模式与现有测试不变）；离线包含后端源码、前端 dist、manylinux wheel、deploy 脚手架与 MANIFEST；部署机 `install.sh` 一键安装/升级，systemd 管理单 uvicorn 进程。

**Tech Stack:** FastAPI 0.141 / uvicorn（Python 3.10 目标）、Vue3 + Vite（npm run build）、bash + rsync + systemd、PowerShell 5+ 打包脚本、pytest-asyncio（asyncio_mode=auto）+ httpx AsyncClient。

**Spec:** `docs/superpowers/specs/2026-10-15-doc-release-deploy-design.md`（已确认）

**Scope Check:** 单一子系统（部署能力），不拆分。真实安装验证需在内网 Linux 机执行，本计划以"可静态验证的全部环节"为边界，内网机验证清单写入 deploy/README.md。

**注意（执行环境）：**
- 工作区根：`D:\StudyProjects\ai-practice`，shell 为 PowerShell；git 操作在仓库根执行
- PowerShell 下 `git commit -m` 消息含中文/括号时必须用**单引号**包裹
- 后端命令一律用 `doc-release\backend\venv\Scripts\python.exe`（已有 venv，Python 3.11 开发环境；部署目标 **3.11.11** 与开发同大版本，已核验全部依赖 `Requires-Python` 下限 ≤3.10）

---

### Task 1: 后端静态托管与 SPA 回退（TDD）

**Files:**
- Modify: `doc-release/backend/app/config.py`
- Modify: `doc-release/backend/app/main.py`
- Test: `doc-release/backend/tests/test_static_serving.py`（新建）

- [ ] **Step 1: 写失败测试**

创建 `doc-release/backend/tests/test_static_serving.py`，内容完整如下：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
cd D:\StudyProjects\ai-practice\doc-release\backend
.\venv\Scripts\python.exe -m pytest tests\test_static_serving.py -q
```

期望：**收集期报错** `ImportError: cannot import name 'register_static' from 'app.main'`（此时尚未实现）。

- [ ] **Step 3: config.py 增加 static_dir 配置**

在 `doc-release/backend/app/config.py` 的 `cors_origins` 字段之后、`@property` 之前插入一行：

```python
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # 部署形态下前端产物目录（相对 WorkingDirectory）；目录不存在则不挂载，开发模式不受影响
    static_dir: str = "static"
```

- [ ] **Step 4: main.py 实现 register_static 并在路由末尾调用**

对 `doc-release/backend/app/main.py` 做三处修改：

1) import 区补两行（与现有 import 风格一致）：

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
```

2) 在 `app.include_router(runs_api.router)` **之后**（文件末尾）新增函数定义与调用：

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

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = (static_dir / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(static_dir.resolve()):
            return FileResponse(candidate)
        return FileResponse(static_dir / "index.html")


register_static(app, Path(settings.static_dir))
```

- [ ] **Step 5: 运行新测试确认通过**

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_static_serving.py -q
```

期望：`7 passed`。

- [ ] **Step 6: 全量回归**

```powershell
.\venv\Scripts\python.exe -m pytest tests -q
```

期望：全部通过（原有用例 + 新增 7 例，无回归）。

- [ ] **Step 7: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add doc-release/backend/app/config.py doc-release/backend/app/main.py doc-release/backend/tests/test_static_serving.py
git commit -m 'feat(doc-release): 后端同端口托管前端产物与 SPA 回退'
```

---

### Task 2: deploy 脚手架——env 模板、systemd 单元、使用说明

**Files:**
- Create: `doc-release/deploy/env.template`
- Create: `doc-release/deploy/docrelease.service`
- Create: `doc-release/deploy/README.md`

- [ ] **Step 1: 创建 `env.template`（与 backend/.env.example 字段一致）**

```ini
# 星语大模型网关（内网地址，脱离内网时 LLM 步骤会失败/降级）
XINGYU_URL=http://10.130.13.74:8060/api/chat/chat
ROBOT_CODE=ROBOT_00000149
# xingyu（默认）/ deepseek（回退）
LLM_PROVIDER=xingyu
# DeepSeek 回退密钥（可选，仅 LLM_PROVIDER=deepseek 时需要）
DEEPSEEK_API_KEY=
LLM_TIMEOUT=120
LLM_MAX_CONCURRENCY=3
```

- [ ] **Step 2: 创建 `docrelease.service`（占位符由 install.sh 的 sed 替换）**

```ini
[Unit]
Description=DocRelease (释文) backend + frontend
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

- [ ] **Step 3: 创建 `deploy/README.md`（部署操作手册）**

````markdown
# DocRelease 部署脚手架

内网 Linux 离线部署（设计文档：仓库根 `docs/superpowers/specs/2026-10-15-doc-release-deploy-design.md`）。
单端口同源托管：uvicorn :8000 同时服务页面、API、SSE。

## 一、开发机构建离线包（Windows）

```powershell
cd doc-release
.\deploy\build_offline_package.ps1                    # 默认：pip --platform 下载 manylinux wheel
.\deploy\build_offline_package.ps1 -WheelSource wsl   # 备选：WSL 内 Python 3.11 下载（platform 法缺 wheel 时用）
```

产物：`out/docrelease-offline-<日期>.zip`。脚本自动校验：wheels 中不得出现 win_amd64 包；
`tree_sitter-` / `tree_sitter_language_pack-` / `pydantic_core-` 关键 wheel 必须在场；生成 MANIFEST.md（源码 commit）。

## 二、上传与解压（部署机）

```bash
sudo mkdir -p /opt/docrelease/packages
sudo unzip docrelease-offline-<日期>.zip -d /opt/docrelease/packages/
```

## 三、安装 / 升级（同一入口）

前置：`python3.11`、`git`、`rsync`。星语网关不通仅警告，不阻断安装。

```bash
cd /opt/docrelease/packages/docrelease-offline-<日期>/deploy
sudo bash install.sh
# 可覆盖默认值：sudo DEPLOY_ROOT=/opt/docrelease PORT=8000 APP_USER=docrelease bash install.sh
```

脚本行为：前置检查 → rsync 源码与 static（排除 venv/.env/db/archive/sample_repo，现场数据保留）→
venv 缺失则创建（Python 3.11）→ 离线安装依赖 → .env 缺失则从模板初始化 → 安装并重启 systemd 服务 → 健康检查。

## 四、部署后验证清单

1. `systemctl status docrelease` → active (running)
2. `curl http://<host>:8000/api/health` → `{"status":"ok"}`
3. 浏览器 `http://<host>:8000/` 工作台加载、仓库列表含 order-center；直刷 `/history` 不 404
4. 示例仓 v2.13.3→v2.13.4 跑一次：SSE 步骤/日志/进度实时推送，产物可预览下载，
   `archive/docs/release/v2.13.4/` 生成三个产物文件

## 五、升级与回滚

- 升级：新包解压到 `packages/` 后重跑 `install.sh`（db/archive/sample_repo/.env 全保留）
- 回滚（用旧包覆盖部署目录后重启）：

```bash
sudo rsync -a --exclude "venv/" --exclude ".env" --exclude "docrelease.db" \
  --exclude "archive/" --exclude "sample_repo/" --exclude "static/" \
  /opt/docrelease/packages/<旧包>/backend/ /opt/docrelease/backend/
sudo rsync -a /opt/docrelease/packages/<旧包>/static/ /opt/docrelease/backend/static/
sudo systemctl restart docrelease
```
````

- [ ] **Step 4: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add doc-release/deploy/env.template doc-release/deploy/docrelease.service doc-release/deploy/README.md
git commit -m 'feat(doc-release): 部署脚手架——env 模板、systemd 单元、部署手册'
```

---

### Task 3: install.sh（部署机安装/升级入口）

**Files:**
- Create: `doc-release/deploy/install.sh`

- [ ] **Step 1: 创建脚本（完整内容如下）**

```bash
#!/usr/bin/env bash
# DocRelease 离线安装/升级脚本（在部署机的离线包目录内执行）
# 用法：sudo bash install.sh
# 可覆盖默认：DEPLOY_ROOT=/opt/docrelease PORT=8000 APP_USER=docrelease
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/docrelease}"
APP_USER="${APP_USER:-docrelease}"
SERVICE_NAME="docrelease"
PORT="${PORT:-8000}"
XINGYU_URL="${XINGYU_URL:-http://10.130.13.74:8060/api/chat/chat}"

log() { echo "[install] $*"; }
die() { echo "[install][ERROR] $*" >&2; exit 1; }

# ---- 1. 前置检查 ----
command -v python3.11 >/dev/null || die "缺少 python3.11，请先安装（如 apt install python3.11）"
command -v git >/dev/null || die "缺少 git：示例仓库生成与『注册本地仓库』功能依赖它"
command -v rsync >/dev/null || die "缺少 rsync"
if curl -sS --max-time 5 -o /dev/null "$XINGYU_URL"; then
  log "星语网关可达"
else
  log "警告：星语网关暂不可达（$XINGYU_URL），继续安装；运行期 LLM 步骤将失败/降级"
fi
if ss -ltn 2>/dev/null | grep -q ":${PORT} "; then
  die "端口 ${PORT} 已被占用，请先释放，或以 PORT=其他端口 重跑"
fi
[ -d "$PKG_ROOT/backend" ] || die "离线包不完整：缺少 backend/"
[ -d "$PKG_ROOT/static" ] || die "离线包不完整：缺少 static/（请先在开发机执行 build_offline_package.ps1）"
[ -d "$PKG_ROOT/wheels" ] || die "离线包不完整：缺少 wheels/"

# ---- 2. 系统用户 ----
if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --shell /usr/sbin/nologin --home-dir "$DEPLOY_ROOT" "$APP_USER"
  log "已创建系统用户 $APP_USER"
fi

# ---- 3. 铺设文件（现场数据全保留）----
mkdir -p "$DEPLOY_ROOT/packages"
rsync -a --delete \
  --exclude "venv/" --exclude ".env" --exclude "docrelease.db" \
  --exclude "archive/" --exclude "sample_repo/" --exclude "static/" \
  "$PKG_ROOT/backend/" "$DEPLOY_ROOT/backend/"
rsync -a --delete "$PKG_ROOT/static/" "$DEPLOY_ROOT/backend/static/"
mkdir -p "$DEPLOY_ROOT/wheels"
rsync -a --delete "$PKG_ROOT/wheels/" "$DEPLOY_ROOT/wheels/"
rsync -a --delete "$PKG_ROOT/deploy/" "$DEPLOY_ROOT/deploy/"
if [ -f "$PKG_ROOT/MANIFEST.md" ]; then cp -f "$PKG_ROOT/MANIFEST.md" "$DEPLOY_ROOT/MANIFEST.md"; fi

# ---- 4. venv 与离线依赖 ----
VENV_PY="$DEPLOY_ROOT/backend/venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  python3.11 -m venv "$DEPLOY_ROOT/backend/venv"
  log "已创建 venv"
fi
"$VENV_PY" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)' \
  || die "venv Python 版本不是 3.11，请删除 $DEPLOY_ROOT/backend/venv 后重跑"
"$VENV_PY" -m pip install --no-index \
  --find-links "$DEPLOY_ROOT/wheels" -r "$DEPLOY_ROOT/backend/requirements.txt"

# ---- 5. .env 初始化（存在则保留现场配置）----
if [ ! -f "$DEPLOY_ROOT/backend/.env" ]; then
  cp "$DEPLOY_ROOT/deploy/env.template" "$DEPLOY_ROOT/backend/.env"
  log "已从模板初始化 .env"
fi

# ---- 6. systemd ----
sed -e "s#__APP_USER__#$APP_USER#g" \
    -e "s#__DEPLOY_ROOT__#$DEPLOY_ROOT#g" \
    -e "s#__PORT__#$PORT#g" \
    "$DEPLOY_ROOT/deploy/docrelease.service" > "/etc/systemd/system/${SERVICE_NAME}.service"
chown -R "$APP_USER":"$APP_USER" "$DEPLOY_ROOT"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null
systemctl restart "$SERVICE_NAME"

# ---- 7. 健康检查 ----
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

- [ ] **Step 2: 语法校验**

```powershell
& 'D:\Tools\Git\bin\bash.exe' -n 'D:\StudyProjects\ai-practice\doc-release\deploy\install.sh'
```

期望：无任何输出、退出码 0（`echo $LASTEXITCODE` 为 0）。语法错误会打印行号。

- [ ] **Step 3: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add doc-release/deploy/install.sh
git commit -m 'feat(doc-release): 部署机离线安装升级脚本 install.sh'
```

---

### Task 4: 开发机打包脚本 build_offline_package.ps1

**Files:**
- Create: `doc-release/deploy/build_offline_package.ps1`
- Modify: `.gitignore`（仓库根，追加一行 `doc-release/out/`）

- [ ] **Step 1: 创建打包脚本（完整内容如下）**

```powershell
# DocRelease 离线包构建脚本（开发机 Windows 执行）
# 用法：cd doc-release; .\deploy\build_offline_package.ps1 [-WheelSource platform|wsl]
# 产物：out/docrelease-offline-<日期>.zip
param(
    [ValidateSet("platform", "wsl")][string]$WheelSource = "platform",
    [string]$PythonCmd = "python"   # 仅 platform 模式用：任意本机 Python 的 pip 执行跨平台 download
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot   # doc-release/
$stamp = Get-Date -Format "yyyyMMdd"
$outDir = Join-Path $root "out\docrelease-offline-$stamp"
if (Test-Path $outDir) { $outDir = "$outDir-$(Get-Date -Format 'HHmmss')" }
Write-Host "[build] 输出目录：$outDir"

# 1. 前端构建（含 vue-tsc --noEmit 类型检查）
Push-Location (Join-Path $root "frontend")
try { npm run build } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }

# 2. 目录骨架
foreach ($d in @("backend", "deploy", "wheels")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $outDir $d) | Out-Null
}

# 3. 后端源码（排除运行时产物；robocopy 退出码 >=8 才是失败）
$excludeDirs = @("venv", "__pycache__", ".pytest_cache", ".idea", "archive", "sample_repo")
robocopy (Join-Path $root "backend") (Join-Path $outDir "backend") `
    /E /XD $excludeDirs /XF ".env" "docrelease.db" /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 复制后端源码失败：$LASTEXITCODE" }

# 4. 前端产物 → static/；deploy 脚手架
Copy-Item (Join-Path $root "frontend\dist") (Join-Path $outDir "static") -Recurse
Copy-Item (Join-Path $root "deploy\*") (Join-Path $outDir "deploy\") -Recurse

# 5. 下载 Linux 平台 wheel（Python 3.10 / manylinux）
$req = Join-Path $root "backend\requirements.txt"
if ($WheelSource -eq "wsl") {
    $reqWsl = (wsl wslpath -a ($req -replace '\\', '/')).Trim()
    $whlWsl = (wsl wslpath -a (($outDir + "\wheels") -replace '\\', '/')).Trim()
    wsl bash -c "python3.10 -m pip download -r '$reqWsl' -d '$whlWsl'"
    if ($LASTEXITCODE -ne 0) { throw "WSL wheel 下载失败" }
} else {
    & $PythonCmd -m pip download -r $req -d (Join-Path $outDir "wheels") `
        --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 `
        --python-version 3.11 --implementation cp --only-binary=:all:
    if ($LASTEXITCODE -ne 0) { throw "wheel 下载失败；个别包缺 manylinux wheel 时改用 -WheelSource wsl" }
}

# 6. wheel 平台校验
$bad = Get-ChildItem (Join-Path $outDir "wheels") -Filter "*win_amd64*"
if ($bad) { throw ("wheels 中混入 Windows 平台包：" + ($bad.Name -join ", ")) }
foreach ($must in @("tree_sitter-", "tree_sitter_language_pack-", "pydantic_core-")) {
    if (-not (Get-ChildItem (Join-Path $outDir "wheels") -Filter "$must*")) {
        throw "缺少关键二进制 wheel：$must（改用 -WheelSource wsl 重试）"
    }
}

# 7. MANIFEST.md
$commit = (git -C $root rev-parse HEAD).Trim()
$dirty = (git -C $root status --porcelain) -join "; "
if ($dirty) { Write-Warning "工作区有未提交改动，MANIFEST 记录的 commit 可能与包内容不一致" }
@(
    "# DocRelease 离线包",
    "- 构建时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "- 源码 commit：$commit",
    "- wheel 来源：$WheelSource（目标 Python 3.11 / manylinux）",
    "- 包结构：backend/（后端源码）static/（前端产物）wheels/（离线依赖）deploy/（安装脚手架）",
    "- 部署：解压后在包内 deploy/ 执行 sudo bash install.sh（详见 deploy/README.md）"
) | Set-Content (Join-Path $outDir "MANIFEST.md") -Encoding utf8

# 8. 压缩
$zip = "$outDir.zip"
Compress-Archive -Path $outDir -DestinationPath $zip -Force
Write-Host "[build] 完成：$zip"
Write-Host "[build] wheel 数量：$((Get-ChildItem (Join-Path $outDir 'wheels')).Count)"
```

- [ ] **Step 2: 根 .gitignore 追加产物目录**

读取仓库根 `.gitignore` 末尾，追加一行（若无则新建文件写入）：

```
doc-release/out/
```

- [ ] **Step 3: 真实执行打包验证（需外网访问 PyPI）**

```powershell
cd D:\StudyProjects\ai-practice\doc-release
.\deploy\build_offline_package.ps1
```

期望：
- 控制台输出 `[build] 完成：...docrelease-offline-20261015.zip`；
- `out\docrelease-offline-*\wheels\` 内**无任何** `*win_amd64*` 文件；
  `tree_sitter-*`、`tree_sitter_language_pack-*`、`pydantic_core-*` 均为 `manylinux`/`abi3` 标签；
- `out\docrelease-offline-*\static\index.html` 存在；
- `MANIFEST.md` 含当前 git commit。

若 platform 模式因个别包缺 manylinux wheel 失败：改用 `.\deploy\build_offline_package.ps1 -WheelSource wsl`（需 WSL 内已装 Python 3.11）。

- [ ] **Step 4: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add doc-release/deploy/build_offline_package.ps1 .gitignore
git commit -m 'feat(doc-release): 开发机离线包构建脚本与产物忽略规则'
```

---

### Task 5: README 部署入口 + 收尾回归

**Files:**
- Modify: `doc-release/backend/README.md`

- [ ] **Step 1: backend/README.md 增加「部署」一节**

在 `## 归档` 小节之后追加：

```markdown
## 部署

内网 Linux 离线部署（单端口同源托管 + systemd）：构建离线包、安装/升级/回滚
见 [`deploy/README.md`](../deploy/README.md)；设计方案见仓库根
`docs/superpowers/specs/2026-10-15-doc-release-deploy-design.md`。
```

- [ ] **Step 2: 全量测试回归**

```powershell
cd D:\StudyProjects\ai-practice\doc-release\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

期望：全部通过。

- [ ] **Step 3: 开发模式冒烟（确认部署改动不破坏本地双进程模式）**

终端 A：

```powershell
cd D:\StudyProjects\ai-practice\doc-release\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

终端 B（验证后 Ctrl+C 关闭终端 A）：

```powershell
curl.exe -s http://127.0.0.1:8000/api/health          # 期望 {"status":"ok"}
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8000/   # 期望 404（无 static/，开发模式不变）
```

- [ ] **Step 4: 提交**

```powershell
cd D:\StudyProjects\ai-practice
git add doc-release/backend/README.md
git commit -m 'docs(doc-release): README 增加部署入口'
```

---

## 任务依赖与边界

- Task 1 → Task 2/3/4 相互独立，但建议按序执行（Task 1 是唯一代码改动，最先合入）
- Task 4 Step 3 需外网（PyPI）；Task 3/4 的脚本在部署机上的真实行为验证属于**内网机验收**（deploy/README.md 第四节清单），不在本计划内
- 全程不修改既有业务代码与既有测试；Task 1 新增函数在 `static/` 缺失时为空操作
