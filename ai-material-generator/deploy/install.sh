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
