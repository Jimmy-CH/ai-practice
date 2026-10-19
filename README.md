# AI Practice

AI 全栈实践项目集合，涵盖从基础 AI 对话、数据分析 Agent、RAG 知识库，到内容生成、物料生产与发布文档自动化的完整技术栈探索。每个子项目均为独立的前后端分离应用，围绕大模型（LLM）能力展开，逐步深入不同 AI 应用场景。

## 项目总览

| 子项目 | 说明 | 核心技术 |
|--------|------|----------|
| [ai-chat-demo](#1-ai-chat-demo) | AI 对话演示版 | FastAPI + Vue 3 + DeepSeek SSE 流式对话 |
| [ai-chat](#2-ai-chat) | AI 对话完整版 | 用户认证 + JWT + SSE 断点续传 + 全异步架构 |
| [data-agent](#3-data-agent) | 数据分析 Agent | LangChain ReAct Agent + SQL 工具 + RBAC 权限 |
| [rag-knowledge-base](#4-rag-knowledge-base) | RAG 知识库问答 | ChromaDB 向量检索 + 语义缓存 + 可观测性 |
| [doc-release](#5-doc-release) | 发布文档自动生成（释文） | 五步异步流水线 + SSE + tree-sitter AST + 星语 LLM |
| [content-workbench](#6-content-workbench) | 内容生产发布工作台 | 多资料生成 + 证据引用 + 审核与审计闭环 |
| [ai-material-generator](#7-ai-material-generator) | AI 运营物料智能生成助手 | 文档解析 + 六类物料 + 审核工作流 + 品牌模板 PPTX |

## 技术栈

**后端：** Python 3.11+ · FastAPI · SQLAlchemy 2.0 (Async) · LangChain · ChromaDB · Redis · SQLite · python-docx · python-pptx · DeepSeek / 星语（Xingyu）LLM · OpenAI Embedding

**前端：** Vue 3 · TypeScript · Vite · Pinia · Vue Router · Element Plus · Axios · Playwright（E2E）

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

## 5. doc-release

> 输入任意 git 仓库的变更范围（base..head），自动生成发布文档三件套：发布检查清单（CSV）、产品说明（Markdown）、溯源数据（JSON）。

**核心能力：**
- **五步异步流水线**：定位范围 → 收集 diff → tree-sitter AST 解析 → LLM 业务化改写 → 确定性渲染并归档
- **SSE 实时推送**：步骤状态 / 终端日志 / 进度事件驱动三栏工作台；断线指数退避重连、刷新恢复现场
- **结构化中间层**：LLM 只产出 JSON 功能点，产物由确定性渲染器生成，可溯源可比对
- **内置示例仓库**：order-center 含补丁 / 功能 / 大版本三大变更场景，首次启动自动生成
- **发布历史**：运行回看、按口径（业务/技术）与脱敏开关即时重渲染、导出与删除
- **交互演示页**：根目录 `demo-app.html` 提供产品交互演示

```
doc-release/
├── backend/     # FastAPI + 五步流水线 + tree-sitter + SSE
└── frontend/    # Vue 3 + Element Plus 三栏工作台 + 发布历史
```

---

## 6. content-workbench

> 内容生产发布工作台：输入活动主题、产品文档、操作手册等资料，一键产出公告、FAQ、海报文案，经人工审核后下载或创建模拟发布任务。

**核心能力：**
- **多资料生成**：围绕同一活动主题组织多份资料，统一生成三类内容物料
- **证据约束**：生成结果与引用资料绑定，审核时可查看引用来源，降低无依据表述
- **审核与审计**：editor 创建、编辑、提交，reviewer 查看引用后通过 / 驳回，全程审计日志
- **资产与发布**：审核通过的资产支持下载，并可创建模拟发布任务
- **端到端验证**：pytest 覆盖后端流程，Playwright 覆盖前端主流程

```
content-workbench/
├── backend/     # FastAPI + SQLAlchemy async + SQLite + DeepSeek
├── frontend/    # Vue 3 + Element Plus + Pinia + Playwright E2E
└── docs/        # 用户手册与使用指南
```

---

## 7. ai-material-generator

> AI 运营物料智能生成助手：输入版本迭代文档（文本或 .docx），自动解析功能点、变更优化、注意事项、风险提示四类要点，一键生成面向不同受众的六类运营物料初稿。

**核心能力：**
- **文档输入**：支持粘贴正文或上传 .docx；上传后自动提取正文回填输入框，可继续编辑或一键清空
- **要点解析**：四类要点结构化展示，支持条目级增删改并保存复用
- **六类物料 × 三类受众**：版本宣发稿、网点操作指引、FAQ 问答库、行者推送话术、海报脚本、培训课件大纲
- **缓存与编辑**：解析结果与生成结果自动缓存，切换受众 / 物料类型优先复用；生成内容可直接编辑
- **审核工作流**：保存草稿 → 提交审核 → reviewer 通过 / 驳回；仅审核通过的资产可下载 Markdown
- **海报配图**：海报脚本可调用星语文生图生成配图，支持预览、下载、删除
- **培训课件 PPT**：培训课件大纲一键导出 16:9 可编辑 PPTX，套用圆通品牌模板（封面 / 目录 / 章节页 / 封底），实时生成不落盘
- **内网部署**：提供 deploy 安装脚本，依赖在线 pip 安装，支持 Linux 非 root 用户部署

```
ai-material-generator/
├── backend/     # FastAPI + SQLAlchemy async + python-docx/python-pptx + 星语/DeepSeek
├── frontend/    # Vue 3 + Element Plus + Pinia
└── deploy/      # 内网部署脚本与 systemd 配置
```

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 22+ / npm
- DeepSeek API Key（[申请地址](https://platform.deepseek.com/)）或星语（Xingyu）大模型网关
- OpenAI API Key（rag-knowledge-base 的 Embedding 用）

### 运行任意子项目

每个子项目均可独立启动，以 `ai-chat` 为例：

**后端：**

```powershell
cd ai-chat/ai-chat-backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 配置 .env 文件（参考各子项目 README；ai-material-generator 默认星语，可切换 DeepSeek）
uvicorn app.main:app --reload
```

**前端：**

```powershell
cd ai-chat/ai-chat-frontend
npm install
npm run dev
```

各子项目的详细配置、默认端口、内置账号与测试方式请参考对应目录下的 `README.md`。

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
├── doc-release/             # ⑤ 发布文档自动生成（释文）
│   ├── backend/             #   五步流水线 + tree-sitter + 星语 LLM
│   ├── frontend/            #   Vue 3 三栏工作台 + 发布历史
│   └── sample_repo/         #   内置示例仓库（order-center）
├── content-workbench/       # ⑥ 内容生产发布工作台
│   ├── backend/             #   FastAPI + 多资料生成 + 审核/审计
│   ├── frontend/            #   Vue 3 + Element Plus + Playwright E2E
│   └── docs/                #   用户手册
├── ai-material-generator/   # ⑦ AI 运营物料智能生成助手
│   ├── backend/             #   FastAPI + python-docx/python-pptx + 星语/DeepSeek
│   ├── frontend/            #   Vue 3 + Element Plus
│   └── deploy/              #   内网部署脚本
├── docs/superpowers/        # 设计与实施文档（specs / plans）
└── demo-app.html            # 释文 DocRelease 交互演示页
```

## 学习路径建议

```
ai-chat-demo ──→ ai-chat ──→ data-agent ──→ rag-knowledge-base
                                              │
                                              ▼
                     doc-release ←── content-workbench ←── ai-material-generator
```

1. **ai-chat-demo**：理解 LLM 流式输出（SSE）与前后端对接
2. **ai-chat**：学习用户认证、JWT、数据库 ORM、断点续传
3. **data-agent**：掌握 LangChain Agent、ReAct 模式、工具调用
4. **rag-knowledge-base**：深入 RAG 架构、向量数据库、语义缓存、监控部署
5. **ai-material-generator**：练习业务文档解析、物料生成、审核流与模板化 Office 导出
6. **content-workbench**：掌握多资料证据约束生成、审核审计与发布闭环
7. **doc-release**：打通代码变更解析、异步流水线、SSE 进度与确定性文档渲染

## License

MIT
