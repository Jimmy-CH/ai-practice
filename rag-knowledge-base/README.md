# 企业级 RAG 知识库问答 API

基于 RAG（Retrieval-Augmented Generation）架构的企业级知识库问答系统。用户上传文档后，系统自动解析、分块、向量化入库，用户可通过自然语言提问，系统检索相关上下文并调用 LLM 生成带引用来源的回答。

## 技术架构

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Client    │────>│   FastAPI 网关    │────>│   DeepSeek   │
└─────────────┘     └────────┬─────────┘     │  (LLM 生成)  │
                             │                └──────────────┘
                    ┌────────┼────────┐
                    │        │        │
              ┌─────▼──┐ ┌──▼───┐ ┌──▼──────────┐
              │ChromaDB│ │Redis │ │  Prometheus  │
              │(向量库) │ │(缓存)│ │  + Grafana   │
              └────────┘ └──────┘ │  (可观测性)   │
                                  └──────────────┘
```

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| Web 框架 | FastAPI | 异步 API，自带 Swagger 文档 |
| LLM | DeepSeek Chat | 通过 OpenAI 兼容接口调用 |
| Embedding | OpenAI text-embedding-3-small | 文档向量化 |
| 向量数据库 | ChromaDB | 本地持久化存储 |
| 语义缓存 | Redis + Redis Vector Store | 相似问题缓存命中 |
| 文档解析 | LangChain (PyPDF / TextLoader) | 支持 PDF、TXT |
| 分块策略 | RecursiveCharacterTextSplitter | 500 字符/块，50 字符重叠 |
| 监控 | Prometheus + Grafana | 请求指标自动采集 |
| 部署 | Docker Compose | 一键编排全部服务 |

## 项目结构

```
rag-knowledge-base/
├── app/
│   ├── api/
│   │   ├── endpoints.py        # API 路由（上传、问答）
│   │   └── schemas.py          # 请求/响应模型（待实现）
│   ├── core/
│   │   ├── rag_pipeline.py     # RAG 引擎（文档入库 + 问答链路）
│   │   ├── cache.py            # 语义缓存（Redis 向量检索）
│   │   ├── metrics.py          # Prometheus 监控配置
│   │   └── retrieval.py        # 检索策略（待实现）
│   ├── ingestion/
│   │   ├── parsers.py          # 文档解析器（待实现）
│   │   ├── chunking.py         # 分块策略（待实现）
│   │   └── embedings.py        # Embedding 封装（待实现）
│   ├── services/
│   │   ├── llm_service.py      # LLM 服务封装（待实现）
│   │   └── vector_db.py        # 向量库服务封装（待实现）
│   ├── config.py               # 全局配置（Pydantic Settings）
│   └── main.py                 # 应用入口
├── docker/
│   ├── docker-compose.yml      # 服务编排
│   └── prometheus.yml          # Prometheus 抓取配置
├── tests/                      # 测试目录
├── .env                        # 环境变量（API Key 等）
└── requirements.txt            # Python 依赖
```

## 快速开始

### 1. 环境要求

- Python 3.11+
- Redis（语义缓存，可选）
- DeepSeek API Key
- OpenAI API Key（用于 Embedding）

### 2. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

编辑项目根目录下的 `.env` 文件：

```env
# DeepSeek LLM
DEEPSEEK_API_KEY=sk-your-deepseek-key
LLM_MODEL=deepseek-chat

# OpenAI Embedding
OPENAI_API_KEY=sk-your-openai-key
EMBEDDING_MODEL=text-embedding-3-small

# Redis（Docker 部署时设为 redis，本地运行设为 localhost）
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 4. 启动服务

```bash
# 本地开发模式（热重载）
python -m uvicorn app.main:app --reload

# 生产模式
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5. Docker 一键部署（含 Redis + Prometheus + Grafana）

```bash
cd docker
docker-compose up -d
```

| 服务 | 地址 |
|------|------|
| RAG API | http://localhost:8000 |
| Swagger 文档 | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000（admin / admin） |

## API 接口

### 健康检查

```
GET /health
```

```json
{ "status": "healthy", "version": "2.0.0" }
```

### 上传文档

```
POST /upload
Content-Type: multipart/form-data
```

| 参数 | 类型 | 说明 |
|------|------|------|
| file | File | PDF 或 TXT 文件 |

响应：

```json
{
  "status": "processing",
  "filename": "report.pdf",
  "message": "文档已接收，正在后台解析入库"
}
```

> 文档解析与向量化在后台异步执行，不阻塞 API 响应。

### 知识库问答

```
POST /v1/ask
Content-Type: application/json
```

```json
{ "question": "公司的年假政策是什么？" }
```

响应：

```json
{
  "answer": "根据知识库中的信息，公司年假政策如下...",
  "sources": [
    {
      "index": 1,
      "source": "employee-handbook.pdf",
      "page": 12,
      "snippet": "员工入职满一年后享有15天带薪年假..."
    }
  ],
  "latency_ms": 2345.67
}
```

### 监控指标

```
GET /metrics
```

Prometheus 格式的指标数据，包含请求延迟、状态码分布等。

## 核心流程

```
文档上传 ──> 后台解析 ──> 文本分块 ──> Embedding 向量化 ──> ChromaDB 入库
                                                                      │
用户提问 ──> 向量检索 Top-K ──> 构造 Prompt ──> DeepSeek 生成 ──> 返回回答 + 引用来源
```

1. **文档入库**：用户上传 PDF/TXT → 后台异步解析 → RecursiveCharacterTextSplitter 分块 → OpenAI Embedding 向量化 → 写入 ChromaDB
2. **知识问答**：用户提问 → ChromaDB 向量检索 Top-K 相关片段 → 拼接上下文构造 Prompt → DeepSeek 生成回答 → 返回回答 + 引用来源

## 配置说明

所有配置通过 `app/config.py` 的 `Settings` 类管理，支持环境变量和 `.env` 文件：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DEEPSEEK_API_KEY` | - | DeepSeek API 密钥 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek 接口地址 |
| `LLM_MODEL` | `deepseek-chat` | 对话模型名称 |
| `OPENAI_API_KEY` | - | OpenAI API 密钥（Embedding 用） |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | 向量模型名称 |
| `VECTOR_DB_PATH` | `./chroma_db` | ChromaDB 持久化路径 |
| `CHUNK_SIZE` | `500` | 文档分块大小（字符数） |
| `CHUNK_OVERLAP` | `50` | 分块重叠大小 |
| `TOP_K` | `5` | 检索返回的最相关片段数 |
| `REDIS_HOST` | `localhost` | Redis 地址 |
| `REDIS_PORT` | `6379` | Redis 端口 |
