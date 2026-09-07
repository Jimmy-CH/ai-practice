# RAG 知识库问答系统 - 生产环境部署指南

## 目录

- [架构概览](#架构概览)
- [前置要求](#前置要求)
- [快速部署](#快速部署)
- [配置说明](#配置说明)
- [HTTPS 配置](#https-配置)
- [运维操作](#运维操作)
- [监控与告警](#监控与告警)
- [安全加固](#安全加固)
- [性能调优](#性能调优)
- [故障排查](#故障排查)

---

## 架构概览

```
                    ┌─────────────┐
                    │   Client    │
                    └──────┬──────┘
                           │ :80/:443
                    ┌──────▼──────┐
                    │    Nginx    │  反向代理 / 限流 / SSL
                    └──────┬──────┘
                           │ internal
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
   │  RAG API    │ │ Prometheus  │ │  Grafana    │
   │  (FastAPI)  │ │  :9090      │ │  :3000      │
   │  4 workers  │ └─────────────┘ └─────────────┘
   └──────┬──────┘
          │ internal
   ┌──────▼──────┐
   │    Redis    │  语义缓存
   │  (Stack)    │
   └─────────────┘
          │
   ┌──────▼──────┐
   │  ChromaDB   │  向量持久化
   │  (volume)   │
   └─────────────┘
```

### 服务组件

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| rag-api | 自构建 | 8000(内部) | FastAPI 应用，4 worker 进程 |
| nginx | nginx:1.27-alpine | 80/443 | 反向代理、限流、SSL |
| redis | redis/redis-stack:7.4 | 6379(内部) | 语义缓存 |
| prometheus | prom/prometheus:v3.5.0 | 9090 | 指标采集与告警 |
| grafana | grafana/grafana:11.6.0 | 3000 | 监控可视化 |

### 网络隔离

- **rag-external**: Nginx、Prometheus、Grafana（可对外暴露端口）
- **rag-internal**: RAG API、Redis（仅内部访问，不暴露端口）

---

## 前置要求

### 服务器配置

| 环境 | CPU | 内存 | 磁盘 | 说明 |
|------|-----|------|------|------|
| 最低 | 2 核 | 4 GB | 20 GB | 开发/测试 |
| 推荐 | 4 核 | 8 GB | 50 GB | 生产环境 |
| 高负载 | 8 核 | 16 GB | 100 GB | 高并发场景 |

### 软件要求

```bash
# Docker Engine 24.0+
docker --version

# Docker Compose V2
docker compose version
```

### 网络要求

- 入站: 80/443 (HTTP/HTTPS)
- 出站: api.deepseek.com (LLM API)、hf-mirror.com (模型下载)

---

## 快速部署

### 1. 准备环境变量

```bash
# 复制生产环境配置模板
cp .env.prod .env.prod.local

# 编辑配置（必须修改 API Key 和域名）
vim .env.prod.local
```

**必须修改的配置项:**

```bash
DEEPSEEK_API_KEY=sk-your-real-api-key    # 替换为真实 API Key
ALLOWED_ORIGINS=https://your-domain.com   # 替换为实际域名
DOMAIN_NAME=your-domain.com               # Nginx server_name
```

### 2. 一键部署

```bash
chmod +x deploy.sh
./deploy.sh deploy
```

### 3. 验证部署

```bash
# 检查服务状态
./deploy.sh status

# 健康检查
curl http://localhost/health

# 查看日志
./deploy.sh logs rag-api
```

### 4. 访问服务

| 服务 | 地址 |
|------|------|
| API | http://your-domain.com |
| 健康检查 | http://your-domain.com/health |
| Prometheus | http://your-domain.com:9090 |
| Grafana | http://your-domain.com:3000 |

---

## 配置说明

### 环境变量 (.env.prod)

```bash
# ==================== LLM 配置 ====================
DEEPSEEK_API_KEY=sk-xxx              # DeepSeek API 密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# ==================== Embedding 模型 ====================
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# ==================== 业务参数 ====================
CHUNK_SIZE=500       # 文档分块大小
CHUNK_OVERLAP=50     # 分块重叠字符数
TOP_K=5              # 检索返回片段数

# ==================== 生产环境 ====================
ALLOWED_ORIGINS=https://your-domain.com  # CORS 白名单
LOG_LEVEL=WARNING                        # 日志级别
```

### 资源限制 (docker-compose.prod.yml)

各服务已配置 CPU/内存限制，可根据实际情况调整:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
```

### 日志轮转

所有服务均配置了日志轮转:

```yaml
logging:
  driver: json-file
  options:
    max-size: "50m"   # 单文件最大 50MB
    max-file: "5"     # 保留 5 个文件
    compress: "true"  # 旧日志自动压缩
```

---

## HTTPS 配置

### 1. 获取 SSL 证书

```bash
# Let's Encrypt 免费证书
certbot certonly --standalone -d your-domain.com

# 证书复制到项目目录
mkdir -p docker/nginx/ssl
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem docker/nginx/ssl/
cp /etc/letsencrypt/live/your-domain.com/privkey.pem docker/nginx/ssl/
```

### 2. 修改 Nginx 配置

编辑 `docker/nginx/conf.d/rag-api.conf`，取消 SSL 相关注释:

```nginx
listen 443 ssl http2;
ssl_certificate     /etc/nginx/ssl/fullchain.pem;
ssl_certificate_key /etc/nginx/ssl/privkey.pem;

# HTTP → HTTPS 重定向
if ($scheme = http) {
    return 301 https://$server_name$request_uri;
}
```

### 3. 修改 docker-compose.prod.yml

```yaml
nginx:
  ports:
    - "80:80"
    - "443:443"    # 取消注释
  volumes:
    - ./nginx/ssl:/etc/nginx/ssl:ro   # 取消注释
```

### 4. 重启 Nginx

```bash
./deploy.sh restart
```

---

## 运维操作

### 部署脚本命令

```bash
./deploy.sh deploy     # 构建并部署
./deploy.sh start      # 启动服务
./deploy.sh stop       # 停止服务
./deploy.sh restart    # 重启服务
./deploy.sh update     # 热更新 API（零停机）
./deploy.sh status     # 查看状态
./deploy.sh logs       # 查看全部日志
./deploy.sh logs api   # 查看 API 日志
./deploy.sh backup     # 备份数据
./deploy.sh clean      # 清理容器
./deploy.sh destroy    # 完全删除（含数据！）
```

### 数据备份

```bash
# 手动备份
./deploy.sh backup

# 定时备份 (crontab)
0 2 * * * /path/to/deploy.sh backup >> /var/log/rag-backup.log 2>&1
```

### 数据恢复

```bash
# 解压备份文件
cd backups/rag_backup_XXXXXXXX_XXXXXX
docker run --rm -v docker_chroma_data:/data -v $(pwd):/backup alpine sh -c "cd /data && tar xzf /backup/chroma_data.tar.gz"
```

### 热更新流程

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 热更新（仅重建 API 容器，不影响其他服务）
./deploy.sh update

# 3. 验证
curl http://localhost/health
```

---

## 监控与告警

### Prometheus 指标

已自动采集以下指标:

- `http_requests_total` - 请求总数（按状态码分组）
- `http_request_duration_seconds` - 请求延迟分布
- `process_resident_memory_bytes` - 进程内存使用

### Grafana 仪表盘

首次登录 Grafana (http://localhost:3000):

- 默认用户: `admin`
- 默认密码: 在 `.env.prod` 中配置 `GRAFANA_ADMIN_PASSWORD`

Prometheus 数据源已自动配置。

### 告警规则

已配置以下告警规则 (`docker/alert_rules.yml`):

| 告警 | 条件 | 严重级别 |
|------|------|----------|
| RAGServiceDown | 服务失联 > 1 分钟 | Critical |
| RAGHighLatency | P95 延迟 > 10s | Warning |
| RAGHighErrorRate | 5xx 错误率 > 5% | Critical |
| RAGHighMemory | 内存 > 1.5GB | Warning |
| RedisDown | Redis 不可用 | Critical |

### 接入告警通知

编辑 `docker/prometheus.yml`，配置 Alertmanager:

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

---

## 安全加固

### 检查清单

- [ ] 修改 DEEPSEEK_API_KEY 为真实密钥
- [ ] 修改 Grafana 默认密码
- [ ] 配置 CORS 白名单（ALLOWED_ORIGINS）
- [ ] 启用 HTTPS
- [ ] Redis 不暴露外部端口
- [ ] /metrics 端点限制内网访问
- [ ] 配置日志级别为 WARNING

### API 限流

Nginx 已配置接口级限流:

| 接口 | 限流策略 |
|------|----------|
| /upload | 5 请求/分钟/IP |
| /v1/ask | 30 请求/分钟/IP |
| /health | 不限流 |

### 敏感数据保护

```bash
# .env.prod 已加入 .gitignore
# 生产环境使用 Docker Secrets 管理密钥
echo "sk-xxx" | docker secret create deepseek_api_key -
```

---

## 性能调优

### Worker 数量

根据 CPU 核心数调整 Uvicorn worker 数量（编辑 Dockerfile）:

```dockerfile
# 推荐: CPU 核数 * 2 + 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "8"]
```

### Embedding 模型

根据场景选择模型:

| 模型 | 维度 | 速度 | 质量 | 适用场景 |
|------|------|------|------|----------|
| all-MiniLM-L6-v2 | 384 | 快 | 中 | 英文为主 |
| paraphrase-multilingual-MiniLM-L12-v2 | 384 | 中 | 高 | 多语言含中文 |
| bge-large-zh-v1.5 | 1024 | 慢 | 高 | 中文场景 |

### Redis 缓存阈值

编辑 `app/core/cache.py`:

```python
self.similarity_threshold = 0.95  # 降低 → 更多缓存命中，但可能不准确
```

### ChromaDB 优化

对于大规模文档（>10万片段），建议切换到 ChromaDB 客户端-服务器模式。

---

## 故障排查

### 常见问题

**1. API 启动失败**

```bash
# 查看日志
./deploy.sh logs rag-api

# 常见原因:
# - DEEPSEEK_API_KEY 未配置
# - Redis 未就绪（检查 depends_on）
# - 端口 8000 被占用
```

**2. 问答响应慢**

```bash
# 检查 LLM API 延迟
curl -w "@curl-format.txt" -o /dev/null -s https://api.deepseek.com/v1/chat/completions

# 检查 Redis 缓存命中率
docker exec rag-redis redis-cli INFO keyspace

# 查看 Prometheus 指标
curl http://localhost:9090/api/v1/query?query=http_request_duration_seconds
```

**3. 内存不足**

```bash
# 查看各服务内存使用
docker stats

# 调整 docker-compose.prod.yml 中的资源限制
```

**4. 向量库数据丢失**

```bash
# 确认 volume 存在
docker volume ls | grep chroma

# 从备份恢复
./deploy.sh stop
# 执行数据恢复命令
./deploy.sh start
```

### 日志查看

```bash
# 实时查看所有服务日志
./deploy.sh logs

# 查看指定服务最近 100 行
./deploy.sh logs rag-api --tail=100

# 进入容器查看
docker exec -it rag-api sh
cat /proc/1/fd/1
```

---

## 目录结构

```
backend/
├── Dockerfile                    # 生产镜像构建
├── .env.prod                     # 生产环境变量模板
├── deploy.sh                     # 部署运维脚本
├── docker/
│   ├── docker-compose.prod.yml   # 生产环境编排
│   ├── docker-compose.yml        # 开发环境编排
│   ├── prometheus.yml            # Prometheus 配置
│   ├── alert_rules.yml           # 告警规则
│   ├── nginx/
│   │   ├── nginx.conf            # Nginx 主配置
│   │   ├── conf.d/
│   │   │   └── rag-api.conf      # API 反向代理
│   │   └── ssl/                  # SSL 证书（需自行添加）
│   └── grafana/
│       └── provisioning/         # Grafana 自动配置
└── DEPLOYMENT.md                 # 本文档
```

---

## CI/CD 集成示例

### GitHub Actions

```yaml
name: Deploy RAG API

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to server
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_KEY }}
          script: |
            cd /opt/rag-knowledge-base/backend
            git pull origin main
            ./deploy.sh update
```

---

## 升级与维护

### 版本升级

```bash
# 1. 备份数据
./deploy.sh backup

# 2. 拉取最新代码
git pull origin main

# 3. 重建镜像并部署
./deploy.sh deploy
```

### 依赖更新

```bash
# 在开发环境更新依赖
pip install -U -r requirements.txt

# 重新构建 Docker 镜像
./deploy.sh deploy
```

---

> **提示**: 生产环境首次部署后，建议执行完整的安全审计和压力测试。
