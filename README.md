# AI Practice

AI 全栈实践项目集合，涵盖从基础 AI 对话到企业级知识库问答的完整技术栈探索。每个子项目均为独立的前后端分离应用，围绕大模型（LLM）能力展开，逐步深入不同 AI 应用场景。

## 项目总览

| 子项目 | 说明 | 核心技术 |
|--------|------|----------|
| [ai-chat-demo](#1-ai-chat-demo) | AI 对话演示版 | FastAPI + Vue 3 + DeepSeek SSE 流式对话 |
| [ai-chat](#2-ai-chat) | AI 对话完整版 | 用户认证 + JWT + SSE 断点续传 + 全异步架构 |
| [data-agent](#3-data-agent) | 数据分析 Agent | LangChain ReAct Agent + SQL 工具 + RBAC 权限 |
| [rag-knowledge-base](#4-rag-knowledge-base) | RAG 知识库问答 | ChromaDB 向量检索 + 语义缓存 + 可观测性 |

## 技术栈

**后端：** Python 3.11+ · FastAPI · SQLAlchemy 2.0 (Async) · LangChain · ChromaDB · Redis · DeepSeek API · OpenAI API

**前端：** Vue 3 · TypeScript · Vite · Pinia · Vue Router · Element Plus · Axios

**基础设施：** Docker Compose · Prometheus · Grafana

---

## 1. ai-chat-demo

> 最小可运行的 AI 流式对话演示，快速验证 DeepSeek SSE 流式输出能力。

**后端** (`ai-chat-demo/backend`)：单文件 FastAPI 应用，集成 DeepSeek 流式对话、健康检查、断线续传（`resume_from`）。无数据库、无认证，开箱即用。

**前端** (`ai-chat-demo/frontend`)：轻量 Vue 3 应用，展示 SSE 流式接收与逐字渲染。

```
ai-chat-demo/
├── backend/     # FastAPI + DeepSeek 流式对话（单文件）
└── frontend/    # Vue 3 + TypeScript 流式展示
```

---

## 2. ai-chat

> 在 ai-chat-demo 基础上完善的企业级 AI 对话系统，增加用户认证与断点续传。

**后端** (`ai-chat/ai-chat-backend`)：
- 用户注册 / 登录，密码 bcrypt 哈希，JWT 认证（24h 有效期）
- SSE 流式对话，支持 `resume_from` 断点续传
- SQLAlchemy 2.0 异步 ORM，自动建表
- 支持 SQLite（默认）/ MySQL 切换

**前端** (`ai-chat/ai-chat-frontend`)：
- Vue 3 + TypeScript + Vite
- Pinia 状态管理 + Vue Router 路由守卫
- 登录 / 注册 / 对话三个页面

```
ai-chat/
├── ai-chat-backend/     # FastAPI + JWT 认证 + SSE 断点续传
└── ai-chat-frontend/    # Vue 3 + Pinia + Vue Router
```

---

## 3. data-agent

> 基于 LangChain ReAct Agent 的自然语言数据分析助手。用户用自然语言提问，Agent 自动生成 SQL 查询数据库并返回分析结果。

**核心能力：**
- **ReAct Agent 工作流**：Thought → Action → Observation 循环，自动规划查询策略
- **SQL 安全机制**：仅允许 SELECT 查询，禁止写操作，结果限制 50 行
- **RBAC 权限控制**：admin / editor / viewer 三级角色
- **OAuth 登录**：支持 GitHub / 微信第三方登录
- **示例数据**：商品、订单、订单明细，支持 `seed_data.py` 一键初始化

```
data-agent/
├── backend/     # FastAPI + LangChain ReAct Agent + JWT + OAuth
└── frontend/    # Vue 3 + 对话式交互界面
```

---

## 4. rag-knowledge-base

> 企业级 RAG（Retrieval-Augmented Generation）知识库问答系统。用户上传文档，系统自动解析、分块、向量化入库，支持自然语言问答并返回引用来源。

**核心能力：**
- **文档入库**：PDF / TXT 上传 → 后台异步解析 → RecursiveCharacterTextSplitter 分块 → OpenAI Embedding 向量化 → ChromaDB 持久化
- **知识问答**：向量检索 Top-K → 构造 Prompt → DeepSeek 生成带引用的回答
- **语义缓存**：Redis Vector Store 缓存相似问题，减少重复调用
- **可观测性**：Prometheus 指标采集 + Grafana 可视化面板
- **Docker 一键部署**：docker-compose 编排全部服务

```
rag-knowledge-base/
├── backend/     # FastAPI + LangChain + ChromaDB + Redis + Prometheus
├── frontend/    # Vue 3 + Element Plus + Markdown 渲染
├── docker/      # docker-compose + Prometheus 配置
└── tests/       # pytest 测试套件
```

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 22+ / npm
- DeepSeek API Key（[申请地址](https://platform.deepseek.com/)）
- OpenAI API Key（rag-knowledge-base 的 Embedding 用）

### 运行任意子项目

每个子项目均可独立启动，以 `ai-chat` 为例：

**后端：**

```powershell
cd ai-chat/ai-chat-backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 配置 .env 文件（参考各子项目 README）
uvicorn app.main:app --reload
```

**前端：**

```powershell
cd ai-chat/ai-chat-frontend
npm install
npm run dev
```

各子项目的详细配置说明请参考对应目录下的 `README.md`。

## 项目架构

```
ai-practice/
├── ai-chat-demo/            # ① 流式对话演示（最小 Demo）
│   ├── backend/             #   FastAPI 单文件 + DeepSeek
│   └── frontend/            #   Vue 3 轻量前端
├── ai-chat/                 # ② 完整 AI 对话系统
│   ├── ai-chat-backend/     #   FastAPI + JWT + SSE 断点续传
│   └── ai-chat-frontend/    #   Vue 3 + Pinia + Router
├── data-agent/              # ③ 数据分析 Agent
│   ├── backend/             #   LangChain ReAct + SQL 工具 + RBAC
│   └── frontend/            #   Vue 3 对话式交互
├── rag-knowledge-base/      # ④ RAG 知识库问答
│   ├── backend/             #   RAG 管线 + 向量检索 + 语义缓存
│   ├── frontend/            #   Vue 3 + Element Plus
│   ├── docker/              #   Docker Compose 编排
│   └── tests/               #   pytest 测试
└── docs/                    # 设计文档
```

## 学习路径建议

```
ai-chat-demo ──→ ai-chat ──→ data-agent ──→ rag-knowledge-base
  (SSE 流式)     (认证+续传)   (Agent 工具)    (RAG + 工程化)
```

1. **ai-chat-demo**：理解 LLM 流式输出（SSE）与前后端对接
2. **ai-chat**：学习用户认证、JWT、数据库 ORM、断点续传
3. **data-agent**：掌握 LangChain Agent、ReAct 模式、工具调用
4. **rag-knowledge-base**：深入 RAG 架构、向量数据库、语义缓存、监控部署

## License

MIT
