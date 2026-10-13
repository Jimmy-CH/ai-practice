# 📊 Data Analysis Agent

基于 LLM 的智能数据分析平台，通过自然语言对话完成数据查询、可视化和分享。

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Vue](https://img.shields.io/badge/Vue-3-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## ✨ 功能特性

### 🤖 智能 Agent
- **自然语言查询** — 用中文提问，Agent 自动生成 SQL 并查询数据库
- **多轮对话上下文** — 支持追问和深入分析，记住最近 5 轮对话
- **智能追问建议** — 每次回答后自动生成 2-3 个相关追问
- **数据可视化** — 自动识别图表需求，生成 ECharts 图表（柱状/折线/饼图）
- **表格展示** — 查询结果自动渲染为可排序的交互表格
- **CSV 导出** — 一键导出查询结果

### 📁 数据源管理
- **CSV 上传建表** — 上传 CSV 文件自动创建数据表
- **表描述增强** — 为表和列添加中文描述，提升 Agent 理解精度
- **动态 Schema** — Agent 自动感知用户上传的数据表

### 📈 仪表盘
- 总营收、总订单、总商品数、本月营收 4 大核心指标
- 近 30 天每日营收趋势图
- 品类销售分布饼图
- Top 10 热销商品柱状图

### 🔗 协作与分享
- **查询收藏** — 保存常用查询，一键执行
- **结果分享** — 生成分享链接，无需登录即可查看
- **定时报告** — 设置每日/每周定时查询任务，手动触发执行

### 🎨 用户体验
- **暗黑模式** — 一键切换明亮/暗黑主题
- **响应式布局** — 桌面端侧栏 + 移动端抽屉菜单
- **个人中心** — 数据统计概览、最近收藏/分享、偏好设置

### 🔐 认证与权限
- **JWT 认证** — Access Token + Refresh Token 双令牌机制
- **OAuth 登录** — 支持 GitHub / 微信第三方登录
- **短信登录** — 手机号 + 验证码登录
- **RBAC 权限** — admin / editor / viewer 三级角色控制

### 📊 管理后台
- **用户管理** — 增删改查、角色分配、启用/禁用
- **操作审计** — 全量操作日志，支持按类型筛选
- **用量统计** — 查询趋势图、Top 活跃用户、热门查询排行

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────┐
│                   Frontend                       │
│  Vue 3 + TypeScript + Element Plus + ECharts    │
│  Vite 构建 | CSS 变量主题系统 | 响应式布局        │
└──────────────────────┬──────────────────────────┘
                       │ REST API + SSE
┌──────────────────────┴──────────────────────────┐
│                   Backend                        │
│  FastAPI + SQLAlchemy (Async) + Uvicorn         │
│  LangChain ReAct Agent + DeepSeek LLM           │
│  JWT + OAuth (Authlib) + RBAC                   │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────┐
│                   Database                       │
│  SQLite (aiosqlite async + sync dual engine)    │
│  内置表: products / orders / order_items         │
│  用户表: data_sources / saved_queries / ...      │
└─────────────────────────────────────────────────┘
```

## 📂 项目结构

```
data-agent/
├── backend/
│   ├── app/
│   │   ├── agent/              # LangChain Agent 核心
│   │   │   ├── langchain_agent.py  # ReAct Agent 组装
│   │   │   ├── prompt.py           # Prompt 模板（含动态 Schema）
│   │   │   └── tools.py            # SQL 查询 + 图表生成工具
│   │   ├── api/                # API 路由层
│   │   │   ├── agent.py            # Agent 查询 / 仪表盘 / Schema
│   │   │   ├── auth.py             # 登录 / OAuth / 角色
│   │   │   ├── audit.py            # 审计日志 / 用量统计
│   │   │   ├── conversation.py     # 会话历史
│   │   │   ├── datasource.py       # 数据源上传管理
│   │   │   ├── query.py            # 收藏查询
│   │   │   ├── report.py           # 定时报告
│   │   │   ├── share.py            # 查询分享
│   │   │   └── router.py           # 路由注册
│   │   ├── auth/               # 认证逻辑
│   │   │   ├── dependencies.py     # JWT 依赖注入
│   │   │   ├── oauth.py            # OAuth 提供商配置
│   │   │   └── service.py          # 认证服务
│   │   ├── models/             # ORM 模型
│   │   │   ├── conversation.py
│   │   │   ├── datasource.py
│   │   │   ├── query.py
│   │   │   ├── share.py
│   │   │   ├── audit.py
│   │   │   └── report.py
│   │   ├── schemas/            # Pydantic Schema
│   │   ├── users/              # 用户模块
│   │   ├── config.py           # 配置（环境变量）
│   │   ├── database.py         # 数据库引擎（async + sync）
│   │   └── main.py             # FastAPI 入口
│   ├── requirements.txt
│   └── .env                    # 环境变量配置
│
└── frontend/
    ├── src/
    │   ├── api/                # API 封装层
    │   │   ├── agent.ts
    │   │   ├── auth.ts
    │   │   ├── audit.ts
    │   │   ├── conversation.ts
    │   │   ├── datasource.ts
    │   │   ├── query.ts
    │   │   ├── report.ts
    │   │   ├── share.ts
    │   │   └── users.ts
    │   ├── components/         # 页面组件
    │   │   ├── AgentChat.vue       # Agent 对话主页面
    │   │   ├── Dashboard.vue       # 仪表盘
    │   │   ├── DataSourceView.vue  # 数据源管理
    │   │   ├── ReportView.vue      # 定时报告
    │   │   ├── AuditView.vue       # 审计统计
    │   │   ├── ProfileView.vue     # 个人中心
    │   │   ├── UserManage.vue      # 用户管理
    │   │   ├── SharedView.vue      # 分享查看（公开）
    │   │   └── LoginView.vue       # 登录页
    │   ├── composables/        # 组合式函数
    │   │   ├── useAgentChat.ts
    │   │   ├── useAuth.ts
    │   │   └── useTheme.ts
    │   ├── layouts/
    │   │   └── MainLayout.vue      # 主布局（响应式）
    │   ├── router/
    │   │   └── index.ts
    │   ├── styles/
    │   │   └── themes.css          # 明亮/暗黑主题变量
    │   └── utils/
    │       └── export.ts           # CSV 导出 + 表格解析
    ├── package.json
    └── vite.config.ts
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Node.js 18+
- DeepSeek API Key（或其他 OpenAI 兼容 LLM）

### 后端启动

```bash
cd backend

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
# 编辑 .env 文件，填入以下配置：
# DEEPSEEK_API_KEY=your_api_key
# DEEPSEEK_BASE_URL=https://api.deepseek.com
# JWT_SECRET_KEY=your_secret_key

# 初始化示例数据
python seed_data.py

# 创建管理员账号
python create_admin.py

# 启动服务
uvicorn app.main:app --reload --port 8000
```

### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 http://localhost:5173 即可使用。

## 🔧 配置说明

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `DEEPSEEK_API_KEY` | LLM API Key | 必填 |
| `DEEPSEEK_BASE_URL` | LLM API 地址 | `https://api.deepseek.com` |
| `DATABASE_URL` | 数据库连接 | `sqlite+aiosqlite:///./agent_demo.db` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | 必填 |
| `JWT_ALGORITHM` | JWT 算法 | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token 过期时间 | `30` |
| `GITHUB_CLIENT_ID` | GitHub OAuth ID | 可选 |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth Secret | 可选 |

## 📡 API 概览

| 模块 | 路径前缀 | 说明 |
|------|---------|------|
| Agent | `/api/agent` | 自然语言查询、流式响应、仪表盘 |
| Auth | `/api/auth` | 登录、注册、OAuth、角色管理 |
| Users | `/api/users` | 用户 CRUD、个人信息、密码修改 |
| Conversation | `/api/conversations` | 会话历史管理 |
| DataSource | `/api/datasource` | 数据源上传、描述编辑 |
| Queries | `/api/queries` | 收藏查询 CRUD |
| Share | `/api/share` | 查询分享创建与查看 |
| Reports | `/api/reports` | 定时报告管理 |
| Audit | `/api/audit` | 审计日志、用量统计 |

## 🗺️ 路线图

- [ ] 多数据源连接（MySQL / PostgreSQL）
- [ ] 仪表盘自定义拖拽布局
- [ ] 定时报告自动执行（后台任务调度）
- [ ] 邮件 / Webhook 通知推送
- [ ] 查询结果评论与协作
- [ ] 数据导入向导（Excel 多 Sheet 解析）

## 📄 License

MIT
