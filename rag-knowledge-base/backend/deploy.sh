#!/usr/bin/env bash
# ============================================================
# RAG 知识库问答系统 - 生产环境部署脚本
# 使用方式: chmod +x deploy.sh && ./deploy.sh [命令]
# 命令: deploy | start | stop | restart | status | logs | backup | clean
# ============================================================

set -euo pipefail

# ==================== 配置 ====================
COMPOSE_DIR="$(cd "$(dirname "$0")/docker" && pwd)"
PROD_COMPOSE="${COMPOSE_DIR}/docker-compose.prod.yml"
ENV_FILE="$(cd "$(dirname "$0")" && pwd)/.env.prod"
BACKUP_DIR="$(cd "$(dirname "$0")" && pwd)/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "${BLUE}[STEP]${NC}  $*"; }

# ==================== 前置检查 ====================
preflight_check() {
    log_step "执行前置检查..."

    # 检查 Docker
    if ! command -v docker &>/dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi

    # 检查 Docker Compose
    if ! docker compose version &>/dev/null; then
        log_error "Docker Compose V2 未安装"
        exit 1
    fi

    # 检查 .env.prod 文件
    if [ ! -f "$ENV_FILE" ]; then
        log_error ".env.prod 文件不存在，请从模板创建并填写配置"
        log_warn  "cp .env.prod.example .env.prod && vim .env.prod"
        exit 1
    fi

    # 检查 API Key 是否已修改
    if grep -q "sk-your-production-api-key-here" "$ENV_FILE"; then
        log_error "请先在 .env.prod 中设置真实的 DEEPSEEK_API_KEY"
        exit 1
    fi

    log_info "前置检查通过 ✓"
}

# ==================== 部署 ====================
cmd_deploy() {
    preflight_check

    log_step "构建并启动生产环境..."

    cd "$COMPOSE_DIR"
    docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" build --no-cache
    docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" up -d

    log_step "等待服务就绪..."
    sleep 10

    # 检查服务状态
    cmd_status

    log_info "部署完成！"
    echo ""
    echo "  服务访问地址:"
    echo "  ─────────────────────────────────"
    echo "  API:        http://localhost:80"
    echo "  Health:     http://localhost:80/health"
    echo "  Prometheus: http://localhost:9090"
    echo "  Grafana:    http://localhost:3000"
    echo "  ─────────────────────────────────"
    echo ""
}

# ==================== 启动 ====================
cmd_start() {
    log_step "启动所有服务..."
    cd "$COMPOSE_DIR"
    docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" up -d
    log_info "所有服务已启动"
}

# ==================== 停止 ====================
cmd_stop() {
    log_step "停止所有服务..."
    cd "$COMPOSE_DIR"
    docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" down
    log_info "所有服务已停止"
}

# ==================== 重启 ====================
cmd_restart() {
    log_step "重启所有服务..."
    cd "$COMPOSE_DIR"
    docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" restart
    log_info "所有服务已重启"
}

# ==================== 热更新代码 ====================
cmd_update() {
    log_step "热更新 API 服务（零停机）..."
    cd "$COMPOSE_DIR"
    docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" build rag-api
    docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" up -d --no-deps rag-api
    log_info "API 服务已更新"
}

# ==================== 状态 ====================
cmd_status() {
    log_step "服务状态:"
    cd "$COMPOSE_DIR"
    docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" ps
    echo ""

    # 健康检查
    log_step "健康检查:"
    if curl -sf http://localhost:80/health > /dev/null 2>&1; then
        log_info "API 健康检查通过 ✓"
    else
        log_warn "API 健康检查失败（服务可能仍在启动中）"
    fi
}

# ==================== 日志 ====================
cmd_logs() {
    local service="${1:-}"
    cd "$COMPOSE_DIR"
    if [ -n "$service" ]; then
        docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" logs -f --tail=100 "$service"
    else
        docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" logs -f --tail=50
    fi
}

# ==================== 数据备份 ====================
cmd_backup() {
    log_step "备份持久化数据..."
    mkdir -p "$BACKUP_DIR"

    local backup_name="rag_backup_${TIMESTAMP}"
    local backup_path="${BACKUP_DIR}/${backup_name}"
    mkdir -p "$backup_path"

    # 备份 Docker volumes
    cd "$COMPOSE_DIR"
    for vol in chroma_data redis_data; do
        log_info "备份 volume: ${vol}"
        docker run --rm \
            -v "docker_${vol}":/data:ro \
            -v "${backup_path}":/backup \
            alpine \
            tar czf "/backup/${vol}.tar.gz" -C /data .
    done

    # 备份环境变量（不含敏感信息的摘要）
    echo "# Backup created at ${TIMESTAMP}" > "${backup_path}/backup_meta.txt"
    grep -v "API_KEY" "$ENV_FILE" >> "${backup_path}/backup_meta.txt"

    log_info "备份完成: ${backup_path}"
    ls -lh "$backup_path"
}

# ==================== 清理 ====================
cmd_clean() {
    log_warn "即将清理所有容器、网络和悬空镜像（数据卷不受影响）"
    read -p "确认继续? (y/N): " confirm
    if [ "$confirm" = "y" ]; then
        cd "$COMPOSE_DIR"
        docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" down --remove-orphans
        docker image prune -f
        log_info "清理完成（数据卷已保留）"
    else
        log_info "已取消"
    fi
}

# ==================== 完全清除（含数据） ====================
cmd_destroy() {
    log_error "警告：此操作将删除所有数据（包括向量库、缓存、监控数据）！"
    read -p "输入 'DESTROY' 确认: " confirm
    if [ "$confirm" = "DESTROY" ]; then
        cd "$COMPOSE_DIR"
        docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" down -v --remove-orphans
        log_warn "所有服务和数据已完全删除"
    else
        log_info "已取消"
    fi
}

# ==================== 帮助 ====================
cmd_help() {
    echo "RAG 知识库问答系统 - 生产部署工具"
    echo ""
    echo "用法: $0 <命令> [参数]"
    echo ""
    echo "命令:"
    echo "  deploy          构建并部署所有服务"
    echo "  start           启动已停止的服务"
    echo "  stop            停止所有服务"
    echo "  restart         重启所有服务"
    echo "  update          热更新 API 代码（零停机）"
    echo "  status          查看服务状态与健康检查"
    echo "  logs [服务名]    查看实时日志"
    echo "  backup          备份持久化数据"
    echo "  clean           清理容器和悬空镜像"
    echo "  destroy         删除所有服务和数据（不可恢复！）"
    echo "  help            显示此帮助信息"
}

# ==================== 路由 ====================
case "${1:-help}" in
    deploy)   cmd_deploy ;;
    start)    cmd_start ;;
    stop)     cmd_stop ;;
    restart)  cmd_restart ;;
    update)   cmd_update ;;
    status)   cmd_status ;;
    logs)     cmd_logs "${2:-}" ;;
    backup)   cmd_backup ;;
    clean)    cmd_clean ;;
    destroy)  cmd_destroy ;;
    help|*)   cmd_help ;;
esac
