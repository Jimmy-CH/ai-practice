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
