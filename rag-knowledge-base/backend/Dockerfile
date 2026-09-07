# ============================================================
# 多阶段构建 - RAG 知识库问答系统生产镜像
# ============================================================

# ---------- Stage 1: 构建依赖 ----------
FROM python:3.11-slim AS builder

WORKDIR /build

# 安装构建工具（部分 Python 包需要编译）
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- Stage 2: 生产运行镜像 ----------
FROM python:3.11-slim AS production

LABEL maintainer="RAG Knowledge Base Team"
LABEL description="企业级 RAG 知识库问答系统 - 生产环境"

# 创建非 root 运行用户
RUN groupadd -r raguser && useradd -r -g raguser -d /app -s /sbin/nologin raguser

WORKDIR /app

# 从 builder 阶段复制已安装的依赖
COPY --from=builder /install /usr/local

# 复制应用代码
COPY app/ ./app/

# 创建运行时目录（数据通过 volume 挂载）
RUN mkdir -p /app/uploaded_files /app/chroma_db && \
    chown -R raguser:raguser /app

# 切换到非 root 用户
USER raguser

# 环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_ENDPOINT="https://hf-mirror.com" \
    HF_HUB_DISABLE_SSL_VERIFICATION=1

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/health'); assert r.status_code == 200" || exit 1

# 暴露端口
EXPOSE 8000

# 生产启动命令（多 worker 进程）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--loop", "uvloop", "--http", "httptools"]
