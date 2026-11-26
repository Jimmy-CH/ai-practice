# doc-release 部署双模式（非 root 用户级）+ 在线 pip 改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** doc-release 部署支持非 root 用户级安装（`systemctl --user`）与 root 系统级双模式；交付形态从离线 wheel 包改为源码包 + 部署机在线 pip。

**Architecture:** `install.sh` 按 uid 自动分叉：root 走 `/opt/docrelease` + `/etc/systemd/system` + 系统用户；非 root 走 `~/docrelease` + `~/.config/systemd/user` + `systemctl --user`。模式相关变量（DEPLOY_ROOT/APP_USER/UNIT_DIR）全部在 if/else 分支内赋值。构建脚本删除 wheel 下载/校验。结构复刻 `ai-material-generator/deploy/install.sh`（WSL 已验证先例）。

**Tech Stack:** bash（set -euo pipefail）、systemd（系统/用户单元 + lingering）、PowerShell 5.1（构建脚本）、WSL（Linux 侧真实验证环境）

**Spec:** `docs/superpowers/specs/2026-10-16-doc-release-nonroot-deploy-design.md`

---

## 环境注意事项（执行前必读）

1. 终端是 **PowerShell 5.1**：多命令用 `;` 分隔（不支持 `&&`）；git commit 消息一律**单引号**包裹。
2. WSL 路径前缀用 `/mnt/d/...`；WSL 默认用户非 root；WSL 仅 Python 3.14（目标机 3.11.11），故 WSL 验证用 sed 放宽版本要求的**副本**，产品脚本绝不改。
3. WSL 直连 bash 不经 logind 会话，`systemctl --user` 需先以 root 执行一次 `loginctl enable-linger <用户>` 激活用户总线。
4. WSL `/tmp` 会被回收：验证产物一律放 `$HOME`。
5. `doc-release/out/` 已被根 .gitignore 忽略，验证脚本放 `doc-release/out/wsl-verify/` 不入库。
6. PS 5.1 + `$ErrorActionPreference="Stop"` 下 npm 的 stderr 在重定向环境会误杀构建——构建脚本内已用 `cmd /c "npm run build 2>&1"` 包裹（先例验证过），不要改回直接调用。
7. build_package.ps1 含中文注释，**必须保留 UTF-8 BOM**（无 BOM 时 PS 5.1 按 GBK 解析产生 mojibake 与虚假语法错误）。

---

### Task 1: install.sh 双模式重写 + .gitattributes 行尾保护

**Files:**
- Create: `doc-release/.gitattributes`
- Modify(整体重写): `doc-release/deploy/install.sh`

- [ ] **Step 1: 新建 .gitattributes**

```
# 部署脚本行尾保护：bash 在 Linux 执行 CRLF 脚本会报错
*.sh text eol=lf
```

- [ ] **Step 2: 整体重写 install.sh**

用 Write 工具整体覆盖 `doc-release/deploy/install.sh`，完整内容如下（LF 行尾）：

```bash
#!/usr/bin/env bash
# DocRelease 安装/升级脚本（在部署机的部署包目录内执行）
# 用法：sudo bash install.sh   # 系统级：/opt/docrelease + 系统服务
#       bash install.sh        # 用户级：~/docrelease + systemctl --user（无需 root）
# 可覆盖：DEPLOY_ROOT PORT APP_USER（非 root 模式 APP_USER 固定为当前用户）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(dirname "$SCRIPT_DIR")"
IS_ROOT=0
if [ "$(id -u)" -eq 0 ]; then IS_ROOT=1; fi

if [ "$IS_ROOT" -eq 1 ]; then
  DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/docrelease}"
  APP_USER="${APP_USER:-docrelease}"
  UNIT_DIR="/etc/systemd/system"
else
  DEPLOY_ROOT="${DEPLOY_ROOT:-$HOME/docrelease}"
  APP_USER="$(id -un)"
  UNIT_DIR="$HOME/.config/systemd/user"
  # su/部分环境缺少该变量时 systemctl --user 无法连接用户总线
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
fi
SERVICE_NAME="docrelease"
PORT="${PORT:-8080}"
XINGYU_URL="${XINGYU_URL:-http://10.130.13.74:8060/api/chat/chat}"

log() { echo "[install] $*"; }
die() { echo "[install][ERROR] $*" >&2; exit 1; }
# systemd 操作封装：root 用系统总线，普通用户用用户总线
svc() {
  if [ "$IS_ROOT" -eq 1 ]; then systemctl "$@"; else systemctl --user "$@"; fi
}

# ---- 0. 模式说明 ----
if [ "$IS_ROOT" -eq 1 ]; then
  log "以 root 安装：系统级部署（$DEPLOY_ROOT + 系统服务）"
else
  log "以普通用户 $(id -un) 安装：用户级部署（$DEPLOY_ROOT + systemctl --user）"
  log "注意：服务随用户会话存活；登出/重启后自动拉起需管理员执行一次：sudo loginctl enable-linger $APP_USER"
fi

# ---- 1. 前置检查 ----
command -v python3.11 >/dev/null || die "缺少 python3.11，请先安装（如 apt install python3.11）"
command -v git >/dev/null || die "缺少 git：示例仓库生成与『注册本地仓库』功能依赖它"
command -v rsync >/dev/null || die "缺少 rsync"
if curl -sS --max-time 5 -o /dev/null "$XINGYU_URL"; then
  log "星语网关可达"
else
  log "警告：星语网关暂不可达（$XINGYU_URL），继续安装；运行期 LLM 步骤将失败/降级"
fi
[ -d "$PKG_ROOT/backend" ] || die "部署包不完整：缺少 backend/"
[ -d "$PKG_ROOT/static" ] || die "部署包不完整：缺少 static/（请先在开发机执行 build_package.ps1）"
[ -d "$PKG_ROOT/deploy" ] || die "部署包不完整：缺少 deploy/"

# 升级场景：先停旧服务释放端口（首次安装无单元则跳过）
UNIT_PATH="$UNIT_DIR/${SERVICE_NAME}.service"
if [ -f "$UNIT_PATH" ]; then
  log "检测到已安装的 ${SERVICE_NAME}，先停止以完成升级"
  svc stop "$SERVICE_NAME" || true
fi
if ss -ltn 2>/dev/null | grep -q ":${PORT} "; then
  die "端口 ${PORT} 被其他进程占用，请先释放，或以 PORT=其他端口 重跑"
fi

# ---- 2. 系统用户（仅 root 模式；用户级直接用当前用户）----
if [ "$IS_ROOT" -eq 1 ]; then
  if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd --system --shell /usr/sbin/nologin --home-dir "$DEPLOY_ROOT" "$APP_USER"
    log "已创建系统用户 $APP_USER"
  fi
fi

# ---- 3. 铺设文件（现场数据全保留：venv/.env/docrelease.db/archive/sample_repo）----
mkdir -p "$DEPLOY_ROOT/packages"
rsync -a --delete \
  --exclude "venv/" --exclude ".env" --exclude "docrelease.db" \
  --exclude "archive/" --exclude "sample_repo/" --exclude "static/" \
  "$PKG_ROOT/backend/" "$DEPLOY_ROOT/backend/"
rsync -a --delete "$PKG_ROOT/static/" "$DEPLOY_ROOT/backend/static/"
rsync -a --delete "$PKG_ROOT/deploy/" "$DEPLOY_ROOT/deploy/"
if [ -f "$PKG_ROOT/MANIFEST.md" ]; then cp -f "$PKG_ROOT/MANIFEST.md" "$DEPLOY_ROOT/MANIFEST.md"; fi

# ---- 4. venv 与在线依赖 ----
VENV_PY="$DEPLOY_ROOT/backend/venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  rm -rf "$DEPLOY_ROOT/backend/venv"
  if ! python3.11 -m venv "$DEPLOY_ROOT/backend/venv"; then
    rm -rf "$DEPLOY_ROOT/backend/venv"
    die "venv 创建失败：Debian/Ubuntu 需先安装 venv 组件（如 apt install python3.11-venv）后重跑"
  fi
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

# ---- 6. systemd（root 写系统单元；用户级写 ~/.config/systemd/user 且删除 User= 行）----
mkdir -p "$UNIT_DIR"
if [ "$IS_ROOT" -eq 1 ]; then
  sed -e "s#__APP_USER__#$APP_USER#g" \
      -e "s#__DEPLOY_ROOT__#$DEPLOY_ROOT#g" \
      -e "s#__PORT__#$PORT#g" \
      "$DEPLOY_ROOT/deploy/docrelease.service" > "$UNIT_PATH"
  chown -R "$APP_USER":"$APP_USER" "$DEPLOY_ROOT"
else
  sed -e "s#__APP_USER__#$APP_USER#g" \
      -e "s#__DEPLOY_ROOT__#$DEPLOY_ROOT#g" \
      -e "s#__PORT__#$PORT#g" \
      -e "/^User=/d" \
      -e "s#^WantedBy=multi-user.target#WantedBy=default.target#" \
      "$DEPLOY_ROOT/deploy/docrelease.service" > "$UNIT_PATH"
fi
svc daemon-reload
svc enable "$SERVICE_NAME" >/dev/null
svc restart "$SERVICE_NAME"

# ---- 7. 用户级 lingering 检查（决定登出/重启后服务是否存活）----
if [ "$IS_ROOT" -ne 1 ]; then
  if ! loginctl show-user "$APP_USER" 2>/dev/null | grep -q '^Linger=yes'; then
    log "警告：lingering 未启用，您登出后服务将停止；重启机器后也不会自启。"
    log "请管理员执行一次：sudo loginctl enable-linger $APP_USER"
  fi
fi

# ---- 8. 健康检查（30 秒硬超时，单次请求也受剩余时间约束）----
log "等待服务就绪…"
deadline=$(( $(date +%s) + 30 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  remain=$(( deadline - $(date +%s) ))
  [ "$remain" -lt 1 ] && break
  if curl -sf --connect-timeout 2 --max-time "$remain" "http://127.0.0.1:${PORT}/api/health" >/dev/null; then
    log "安装完成：http://<本机>:${PORT}/（systemctl status ${SERVICE_NAME} 查看状态）"
    exit 0
  fi
  sleep 1
done
echo "[install][ERROR] 健康检查未通过（30 秒超时），排查：journalctl -u ${SERVICE_NAME} -n 50" >&2
[ "$IS_ROOT" -ne 1 ] && echo "[install][提示] 用户级服务日志：journalctl --user -u ${SERVICE_NAME} -n 50" >&2
exit 1
```

要点自查（重写后目视核对）：模式变量三分支内赋值；wheels 全部消失；lingering 在健康检查**之前**；`svc` 封装贯穿所有 systemd 操作；git 前置检查保留。

- [ ] **Step 3: bash 语法检查（WSL）**

Run: `wsl bash -n /mnt/d/StudyProjects/ai-practice/doc-release/deploy/install.sh`
Expected: 无输出，退出码 0

- [ ] **Step 4: LF 行尾字节校验（PowerShell）**

```powershell
$bytes = [IO.File]::ReadAllBytes('D:\StudyProjects\ai-practice\doc-release\deploy\install.sh')
'has-cr: ' + ($bytes -contains 13)
```

Expected: `has-cr: False`（无 CR 字节 = 纯 LF）

- [ ] **Step 5: 提交**

```powershell
git add doc-release/.gitattributes doc-release/deploy/install.sh
git commit -m 'feat: doc-release install.sh 双模式(root系统级/非root用户级)+在线pip; gitattributes 固定 sh 行尾'
git ls-files --eol doc-release/deploy/install.sh
```

Expected: 最后一行输出含 `i/lf w/lf`

---

### Task 2: WSL 非 root 真实执行验证（验证副本，产品脚本不动）

**Files:**
- Create(临时,不入库): `doc-release/out/wsl-verify/prepare.sh`、`verify.sh`、`cleanup.sh`

背景：bash -n 无法暴露模式变量作用域错误，必须真实非 root 执行一次。WSL 无 3.11 且无真实依赖，**预期健康检查超时 exit 1**，其余环节（铺设/venv/pip/单元写入用户目录/svc --user 总线/enable）必须全部走通。

- [ ] **Step 1: 写 prepare.sh 到 `doc-release/out/wsl-verify/prepare.sh`**

```bash
#!/usr/bin/env bash
# 构造 doc-release 非 root 安装验证包（产品脚本不动，版本要求仅在副本上放宽）
set -euo pipefail
SRC=/mnt/d/StudyProjects/ai-practice/doc-release
PKG="$HOME/docrelease-verify/pkg"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
systemctl --user stop docrelease 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/docrelease.service"
systemctl --user daemon-reload 2>/dev/null || true

rm -rf "$HOME/docrelease-verify" "$HOME/docrelease"
mkdir -p "$PKG/deploy" "$PKG/backend" "$PKG/static"

# install.sh 副本：python3.11 → python3（WSL 仅 3.14），版本断言同步放宽
sed -e 's/python3\.11/python3/g' -e 's/(3, 11)/(3, 14)/' \
  "$SRC/deploy/install.sh" > "$PKG/deploy/install.sh"
cp "$SRC/deploy/docrelease.service" "$PKG/deploy/"
cp "$SRC/deploy/env.template" "$PKG/deploy/"

# 最小 backend：空 requirements 使 pip install 秒过（验证目标是脚本流程而非依赖）
: > "$PKG/backend/requirements.txt"
echo '<!doctype html><title>docrelease-verify</title>' > "$PKG/static/index.html"
echo "prepare-done user=$(id -un) uid=$(id -u)"
```

- [ ] **Step 2: 写 verify.sh 到 `doc-release/out/wsl-verify/verify.sh`**

```bash
#!/usr/bin/env bash
# 以非 root 真实执行 install.sh 副本并断言用户级安装行为
set -uo pipefail
[ "$(id -u)" -ne 0 ] || { echo "默认 WSL 用户是 root，无法验证非 root 模式"; exit 1; }
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
PORT="${PORT:-8080}"
PKG="$HOME/docrelease-verify/pkg"

bash "$PKG/deploy/install.sh"
RC=$?
echo "install-rc=$RC"

FAIL=0
check() { # check <描述> <命令...>
  local desc="$1"; shift
  if "$@"; then echo "PASS: $desc"; else echo "FAIL: $desc"; FAIL=1; fi
}

[ "$RC" -eq 1 ] || { echo "FAIL: 期望健康检查超时 exit 1，实际 $RC"; FAIL=1; }
UNIT="$HOME/.config/systemd/user/docrelease.service"
check "单元写入用户目录" test -f "$UNIT"
check "User= 行已删除" bash -c "! grep -q '^User=' '$UNIT'"
check "WantedBy=default.target" grep -q '^WantedBy=default.target' "$UNIT"
check "端口 $PORT 已注入" grep -q -- "--port $PORT" "$UNIT"
check "部署根指向 ~/docrelease" grep -q "$HOME/docrelease/backend/venv/bin/python" "$UNIT"
check "未写 /etc/systemd/system" test ! -e /etc/systemd/system/docrelease.service
check "backend 已铺设" test -f "$HOME/docrelease/backend/requirements.txt"
check "static 已铺设" test -f "$HOME/docrelease/backend/static/index.html"
check "deploy 已铺设" test -f "$HOME/docrelease/deploy/install.sh"
check ".env 已初始化" test -f "$HOME/docrelease/backend/.env"
check "venv 已创建" test -x "$HOME/docrelease/backend/venv/bin/python"
check "单元已 enable" bash -c "systemctl --user is-enabled docrelease"

if [ "$FAIL" -eq 0 ]; then echo "ALL-CHECKS-PASSED"; else echo "SOME-CHECKS-FAILED"; exit 1; fi
```

- [ ] **Step 3: 写 cleanup.sh 到 `doc-release/out/wsl-verify/cleanup.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
systemctl --user disable docrelease >/dev/null 2>&1 || true
systemctl --user stop docrelease >/dev/null 2>&1 || true
rm -f "$HOME/.config/systemd/user/docrelease.service"
systemctl --user daemon-reload
rm -rf "$HOME/docrelease" "$HOME/docrelease-verify"
echo "cleanup-done"
```

- [ ] **Step 4: 执行 prepare 并激活 lingering**

```powershell
wsl bash /mnt/d/StudyProjects/ai-practice/doc-release/out/wsl-verify/prepare.sh
```

Expected: 输出 `prepare-done user=<用户名> uid=1000`

```powershell
$u = (wsl id -un).Trim(); wsl -u root loginctl enable-linger $u; 'linger-enabled: ' + $u
```

Expected: `linger-enabled: <用户名>`（无报错）

- [ ] **Step 5: 真实执行验证（约 60-90 秒）**

Run: `wsl bash /mnt/d/StudyProjects/ai-practice/doc-release/out/wsl-verify/verify.sh`（timeout 设 ≥180 秒）
Expected: 末行 `ALL-CHECKS-PASSED`（install 本身以健康检查超时 exit 1 属预期，前述 12 项 check 全 PASS）

故障预案：
- 端口 8080 被占（WSL2 镜像网络可能透出 Windows 监听）：改跑 `wsl bash -c "PORT=18080 bash /mnt/d/StudyProjects/ai-practice/doc-release/out/wsl-verify/verify.sh"`
- `systemctl --user` 连不上用户总线：`wsl --shutdown` 后从 Step 4 顺序重跑（冷启动后 linger 生效）
- 出现 FAIL：按输出定位，**修复产品 install.sh 后重新从 Step 1 跑一遍全流程**

- [ ] **Step 6: 清理**

```powershell
wsl bash /mnt/d/StudyProjects/ai-practice/doc-release/out/wsl-verify/cleanup.sh
Remove-Item D:\StudyProjects\ai-practice\doc-release\out\wsl-verify -Recurse -Force
```

Expected: `cleanup-done`；本地临时脚本删除（out/ 本就不入库）

- [ ] **Step 7: 提交（仅当 Step 5 触发了产品脚本修复）**

```powershell
git add doc-release/deploy/install.sh
git commit -m 'fix: install.sh 非root真实验证问题修复'
```

---

### Task 3: 构建脚本改造（build_offline_package.ps1 → build_package.ps1）

**Files:**
- Rename + Modify: `doc-release/deploy/build_offline_package.ps1` → `doc-release/deploy/build_package.ps1`

策略：git mv 保留历史；用 SearchReplace 编辑以**保住文件头的 UTF-8 BOM**（Write 重写会丢 BOM）。

- [ ] **Step 1: 行尾归一 + BOM 确保（防 CRLF 导致后续精确匹配失败）**

```powershell
$p = 'D:\StudyProjects\ai-practice\doc-release\deploy\build_offline_package.ps1'
$t = [IO.File]::ReadAllText($p)
$t = $t.Replace("`r`n", "`n")
[IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($true)))
$b = [IO.File]::ReadAllBytes($p)
'first-bytes: ' + (($b[0..2] | ForEach-Object { $_.ToString('X2') }) -join ' ')
'has-cr: ' + ($b -contains 13)
```

Expected: `first-bytes: EF BB BF`；`has-cr: False`

- [ ] **Step 2: git mv 重命名**

```powershell
git mv doc-release/deploy/build_offline_package.ps1 doc-release/deploy/build_package.ps1
```

Expected: 无输出，退出码 0

- [ ] **Step 3: SearchReplace 编辑 `doc-release/deploy/build_package.ps1`（单次调用，按序 11 组替换）**

1. `# DocRelease 离线包构建脚本（开发机 Windows 执行）` → `# DocRelease 部署包构建脚本（开发机 Windows 执行）`
2. `# 用法：cd doc-release; .\deploy\build_offline_package.ps1 [-WheelSource platform|wsl]` → `# 用法：cd doc-release; .\deploy\build_package.ps1`
3. `# 产物：out/docrelease-offline-<日期>.zip` → `# 产物：out/docrelease-package-<日期>.zip（依赖由部署机在线安装，不含 wheels）`
4. 删除 param 块：

   原：
   ```
   param(
       [ValidateSet("platform", "wsl")][string]$WheelSource = "platform",
       [string]$PythonCmd = "python"   # 仅 platform 模式用：任意本机 Python 的 pip 执行跨平台 download
   )
   $ErrorActionPreference = "Stop"
   ```
   新：
   ```
   $ErrorActionPreference = "Stop"
   ```
5. `$outDir = Join-Path $root "out\docrelease-offline-$stamp"` → `$outDir = Join-Path $root "out\docrelease-package-$stamp"`
6. npm 构建加固（PS 5.1 stderr 误杀防护，对齐 ai-material-generator 验证版）：

   原：
   ```
   # 1. 前端构建（含 vue-tsc --noEmit 类型检查）
   Push-Location (Join-Path $root "frontend")
   try { npm run build } finally { Pop-Location }
   if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }
   ```
   新：
   ```
   # 1. 前端构建（含 vue-tsc --noEmit 类型检查；PS 5.1 下 npm 的 stderr 在重定向下
   #    会包装成 ErrorRecord 误杀构建，经 cmd 合并流后以 $LASTEXITCODE 判定成败）
   Push-Location (Join-Path $root "frontend")
   try { cmd /c "npm run build 2>&1" } finally { Pop-Location }
   if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }
   ```
7. `foreach ($d in @("backend", "deploy", "wheels")) {` → `foreach ($d in @("backend", "deploy")) {`
8. 整体删除 wheel 下载 + 校验两节（从 `# 5. 下载 Linux 平台 wheel（Python 3.11 / manylinux）` 起到 `# 7. MANIFEST.md` 前的全部内容），替换为节号重排：

   原（注意含行尾反引号续行）：
   ```
   # 5. 下载 Linux 平台 wheel（Python 3.11 / manylinux）
   $req = Join-Path $root "backend\requirements.txt"
   if ($WheelSource -eq "wsl") {
       $reqWsl = (wsl wslpath -a ($req -replace '\\', '/')).Trim()
       $whlWsl = (wsl wslpath -a (($outDir + "\wheels") -replace '\\', '/')).Trim()
       wsl bash -c "python3.11 -m pip download -r '$reqWsl' -d '$whlWsl'"
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
   ```
   新：
   ```
   # 5. MANIFEST.md
   ```
9. MANIFEST 内容：

   原：
   ```
   @(
       "# DocRelease 离线包",
       "- 构建时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
       "- 源码 commit：$commit",
       "- wheel 来源：$WheelSource（目标 Python 3.11 / manylinux）",
       "- 包结构：backend/（后端源码）static/（前端产物）wheels/（离线依赖）deploy/（安装脚手架）",
       "- 部署：解压后在包内 deploy/ 执行 sudo bash install.sh（详见 deploy/README.md）"
   ) | Set-Content (Join-Path $outDir "MANIFEST.md") -Encoding utf8
   ```
   新：
   ```
   @(
       "# DocRelease 部署包",
       "- 构建时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
       "- 源码 commit：$commit",
       "- 包结构：backend/（后端源码）static/（前端产物）deploy/（安装脚手架）",
       "- 部署：解压后在包内 deploy/ 执行 sudo bash install.sh（系统级）或 bash install.sh（用户级，无需 root），详见 deploy/README.md"
   ) | Set-Content (Join-Path $outDir "MANIFEST.md") -Encoding utf8
   ```
10. `# 8. 压缩` → `# 6. 压缩`
11. 删除 wheel 数量输出：

    原：
    ```
    Write-Host "[build] 完成：$zip"
    Write-Host "[build] wheel 数量：$((Get-ChildItem (Join-Path $outDir 'wheels')).Count)"
    ```
    新：
    ```
    Write-Host "[build] 完成：$zip"
    ```

- [ ] **Step 4: BOM 与 PS 语法校验**

```powershell
$b = [IO.File]::ReadAllBytes('D:\StudyProjects\ai-practice\doc-release\deploy\build_package.ps1')
'first-bytes: ' + (($b[0..2] | ForEach-Object { $_.ToString('X2') }) -join ' ')
$tks=$null; $errs=$null
[System.Management.Automation.Language.Parser]::ParseFile('D:\StudyProjects\ai-practice\doc-release\deploy\build_package.ps1', [ref]$tks, [ref]$errs) | Out-Null
'parse-errors: ' + $errs.Count
$errs | ForEach-Object { $_.Message }
```

Expected: `first-bytes: EF BB BF`；`parse-errors: 0`

- [ ] **Step 5: 目视核对最终结构**

Read `doc-release/deploy/build_package.ps1` 确认：6 个编号节（前端构建/目录骨架/后端源码/前端产物/MANIFEST/压缩）；全文无 wheels、无 -WheelSource、无 pip download；robocopy 排除清单未动。

- [ ] **Step 6: 提交**

```powershell
git add doc-release/deploy/build_package.ps1
git commit -m 'refactor: doc-release 构建脚本改为源码包(在线pip交付), 删除wheel下载与校验'
```

---

### Task 4: 文档同步

**Files:**
- Modify(整体重写): `doc-release/deploy/README.md`
- Modify: `doc-release/backend/README.md:77`
- Modify: `.gitignore:167`

- [ ] **Step 1: 整体重写 deploy/README.md**

用 Write 工具覆盖 `doc-release/deploy/README.md`，完整内容：

````markdown
# DocRelease 部署脚手架

内网 Linux 部署（设计文档：仓库根 `docs/superpowers/specs/2026-10-15-doc-release-deploy-design.md`、
`docs/superpowers/specs/2026-10-16-doc-release-nonroot-deploy-design.md`）。
单端口同源托管：uvicorn :8080 同时服务页面、API、SSE。交付形态为源码包，依赖由部署机在线 pip 安装。

## 一、开发机构建部署包（Windows）

```powershell
cd doc-release
.\deploy\build_package.ps1
```

产物：`out/docrelease-package-<日期>.zip`（backend 源码 + static 前端产物 + deploy 脚手架，不含 wheels）。
生成 MANIFEST.md 记录源码 commit。

## 二、上传与解压（部署机）

```bash
# 系统级（root）
sudo mkdir -p /opt/docrelease/packages
sudo unzip docrelease-package-<日期>.zip -d /opt/docrelease/packages/
# 用户级（非 root，任意可写位置）
mkdir -p ~/docrelease/packages
unzip docrelease-package-<日期>.zip -d ~/docrelease/packages/
```

## 三、安装 / 升级（同一入口）

前置：`python3.11`、`git`、`rsync`，部署机可访问 pip 源（内网源可用 `PIP_INDEX_URL` 覆盖）。
星语网关不通仅警告，不阻断安装。

```bash
cd <包目录>/deploy
sudo bash install.sh   # 系统级：/opt/docrelease + 系统服务 + 系统用户 docrelease
bash install.sh        # 用户级：~/docrelease + systemctl --user，全程无需 root
# 可覆盖默认值：DEPLOY_ROOT=... PORT=... APP_USER=...（APP_USER 仅 root 模式生效）
```

脚本行为：前置检查 →（升级时先停旧服务释放端口，首次安装直接检查端口）→
rsync 源码与 static（排除 venv/.env/docrelease.db/archive/sample_repo，现场数据保留）→
venv 缺失则创建（Python 3.11）→ 在线安装依赖 → .env 缺失则从模板初始化 →
安装并启动 systemd 服务 → lingering 提示（用户级）→ 健康检查（30 秒硬超时）。

用户级说明：
- 服务随用户会话存活；登出/重启后自动拉起，需管理员一次性执行 `sudo loginctl enable-linger <用户>`
- 常用命令：`systemctl --user status docrelease`、`journalctl --user -u docrelease -n 50`
- 不支持跨模式升级（如 root 安装后用非 root 升级）；旧服务占用端口会被端口检查拦截

## 四、部署后验证清单

1. `systemctl status docrelease`（用户级 `systemctl --user status docrelease`）→ active (running)
2. `curl http://<host>:8080/api/health` → `{"status":"ok"}`
3. 浏览器 `http://<host>:8080/` 工作台加载、仓库列表含 order-center；直刷 `/history` 不 404
4. 示例仓 v2.13.3→v2.13.4 跑一次：SSE 步骤/日志/进度实时推送，产物可预览下载，
   `archive/docs/release/v2.13.4/` 生成三个产物文件

## 五、升级与回滚

- 升级：新包解压到 `packages/` 后重跑 `install.sh`（db/archive/sample_repo/.env 全保留）
- 回滚（用旧包覆盖部署目录后重启，`<部署根>` 为 /opt/docrelease 或 ~/docrelease）：

```bash
rsync -a --exclude "venv/" --exclude ".env" --exclude "docrelease.db" \
  --exclude "archive/" --exclude "sample_repo/" --exclude "static/" \
  <部署根>/packages/<旧包>/backend/ <部署根>/backend/
rsync -a <部署根>/packages/<旧包>/static/ <部署根>/backend/static/
sudo systemctl restart docrelease      # 用户级：systemctl --user restart docrelease
```
````

- [ ] **Step 2: backend/README.md 部署节措辞（SearchReplace 单处）**

原：`内网 Linux 离线部署（单端口同源托管 + systemd）：构建离线包、安装/升级/回滚`
新：`内网 Linux 部署（源码包 + 在线 pip，单端口同源托管 + systemd，root/非 root 双模式）：构建部署包、安装/升级/回滚`

（注：backend/README.md 中"测试离线可跑/e2e 打桩 LLM（离线）"等是**测试语义**，与部署交付形态无关，不改。）

- [ ] **Step 3: 根 .gitignore 注释措辞（SearchReplace 单处）**

原：`# doc-release 离线部署包构建产物`
新：`# doc-release 部署包构建产物`

- [ ] **Step 4: 提交**

```powershell
git add doc-release/deploy/README.md doc-release/backend/README.md .gitignore
git commit -m 'docs: doc-release 部署文档同步双模式与源码包交付'
```

---

### Task 5: 真实构建部署包 + 全量残留清扫（收尾验证）

**Files:** 无仓库改动预期（产物在 out/，不入库）

- [ ] **Step 1: 真实执行构建（含前端 npm build，timeout ≥600 秒）**

```powershell
cd D:\StudyProjects\ai-practice\doc-release; .\deploy\build_package.ps1; cd D:\StudyProjects\ai-practice
```

Expected: 末两行 `[build] 完成：D:\StudyProjects\ai-practice\doc-release\out\docrelease-package-<日期>.zip`

- [ ] **Step 2: 包结构断言**

```powershell
$pkg = Get-ChildItem D:\StudyProjects\ai-practice\doc-release\out -Directory -Filter 'docrelease-package-*' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
'backend-app: ' + (Test-Path (Join-Path $pkg.FullName 'backend\app'))
'static-index: ' + (Test-Path (Join-Path $pkg.FullName 'static\index.html'))
'deploy-install: ' + (Test-Path (Join-Path $pkg.FullName 'deploy\install.sh'))
'no-wheels: ' + (-not (Test-Path (Join-Path $pkg.FullName 'wheels')))
'zip-exists: ' + (Test-Path "$($pkg.FullName).zip")
'install-same: ' + ((Get-FileHash D:\StudyProjects\ai-practice\doc-release\deploy\install.sh).Hash -eq (Get-FileHash (Join-Path $pkg.FullName 'deploy\install.sh')).Hash)
Get-Content (Join-Path $pkg.FullName 'MANIFEST.md')
```

Expected: 前六项全 True/True/True/True/True/True；MANIFEST 共 5 行、标题"DocRelease 部署包"、无 wheel 来源行、部署行含双模式描述

- [ ] **Step 3: 残留引用清扫（deploy 目录 + backend/README 部署节）**

```powershell
Get-ChildItem D:\StudyProjects\ai-practice\doc-release\deploy -File | Select-String -Pattern 'wheel|离线|offline|build_offline'
Select-String -Path D:\StudyProjects\ai-practice\doc-release\backend\README.md -Pattern '离线部署|build_offline'
git status --porcelain
```

Expected: 前两条命令无输出（历史 spec/plan 文档是过往记录不改）；`git status` 干净（或仅 out/ 外的预期改动）

- [ ] **Step 4: 最终状态汇报**

汇总：commit 列表（`git log --oneline -6`）、WSL 验证结果、包构建结果，向用户报告完成状态与部署机验收提示（deploy/README.md 第四节清单）。
