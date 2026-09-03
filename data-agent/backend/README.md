# Data Analysis Agent

基于 LangChain ReAct Agent 的自然语言数据分析助手。用户通过自然语言提问，Agent 自动生成 SQL 查询数据库并返回分析结果。

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| AI Agent | LangChain + ReAct |
| LLM | DeepSeek Chat |
| ORM | SQLAlchemy 2.0 (Async) |
| 数据库 | SQLite |
| 数据校验 | Pydantic v2 |
| 认证 | JWT (python-jose) + bcrypt |
| OAuth | Authlib (GitHub / 微信) |

## 项目结构

```
backend/
├── app/
│   ├── agent/              # Agent 核心逻辑
│   │   ├── langchain_agent.py  # ReAct Agent 组装与执行
│   │   ├── prompt.py           # ReAct Prompt 模板
│   │   └── tools.py            # SQL 只读查询工具
│   ├── api/                # API 路由层
│   │   ├── agent.py            # Agent 接口（RBAC 保护）
│   │   ├── auth.py             # 登录/注册/OAuth 回调
│   │   └── router.py           # 路由汇总
│   ├── auth/               # 认证与权限模块
│   │   ├── service.py          # JWT 签发/密码哈希
│   │   ├── dependencies.py     # get_current_user / require_role
│   │   ├── oauth.py            # GitHub / 微信 OAuth 客户端
│   │   └── schemas.py          # Token / 登录请求模型
│   ├── users/              # 用户管理模块
│   │   ├── models.py           # User / Role / OAuthAccount
│   │   ├── service.py          # 用户注册/查询/角色分配
│   │   ├── router.py           # 用户管理 API
│   │   └── schemas.py          # 用户请求/响应模型
│   ├── models/             # SQLAlchemy 数据模型
│   │   └── demo_data.py        # Product / Order / OrderItem
│   ├── schemas/            # Pydantic 请求/响应模型
│   │   └── agent.py
│   ├── config.py           # 配置管理（环境变量）
│   ├── database.py         # 异步数据库引擎
│   └── main.py             # FastAPI 应用入口
├── seed_data.py            # 示例数据初始化脚本
├── requirements.txt
└── .env                    # 环境变量配置
```

## 核心功能

### ReAct Agent 工作流

Agent 采用 LangChain 的 ReAct（Reasoning + Acting）模式，执行流程如下：

1. **接收问题** — 用户提交自然语言问题（如"各品类销售总额是多少？"）
2. **思考 (Thought)** — LLM 分析问题，规划查询策略
3. **行动 (Action)** — 生成 SQL 查询语句
4. **观察 (Observation)** — 执行 SQL 获取结果
5. **循环** — 重复步骤 2-4，直到得出最终答案
6. **返回结果** — 包含最终答案和完整的推理步骤

### SQL 安全机制

- 仅允许 `SELECT` 查询
- 禁止 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER`、`CREATE`、`TRUNCATE` 等写操作
- 查询结果最多返回 50 行

### 数据库模型

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `products` | 商品信息 | id, name, category, price, created_at |
| `orders` | 订单信息 | id, customer_name, order_date, status |
| `order_items` | 订单明细 | id, order_id, product_id, quantity, unit_price |

## 快速开始

### 1. 环境要求

- Python 3.11+
- DeepSeek API Key（[申请地址](https://platform.deepseek.com/)）

### 2. 安装依赖

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
```

### 3. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
DATABASE_URL=sqlite+aiosqlite:///./agent_demo.db
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
SECRET_KEY=your_jwt_secret_key_here
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
WECHAT_APP_ID=
WECHAT_APP_SECRET=
```

### 4. 初始化示例数据

```bash
python seed_data.py
```

该脚本会生成 3 个角色（admin/editor/viewer）、21 个商品、100 个订单及关联的订单明细数据。

### 5. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

服务启动后访问 API 文档：`http://localhost:8000/docs`

## 认证与权限

### 角色说明

| 角色 | 权限 |
|------|------|
| admin | 所有操作 |
| editor | Agent 查询 + 查看表结构 |
| viewer | 仅查看表结构 |

### 获取 Token

```bash
# 注册
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "123456"}'

# 登录
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username_or_phone": "testuser", "password": "123456"}'
```

### 使用 Token

所有 `/api/agent/*` 和 `/api/users/*` 接口需要在请求头中携带 Token：

```bash
curl http://localhost:8000/api/agent/schemas \
  -H "Authorization: Bearer <your_access_token>"
```

## API 接口

### POST `/api/agent/query` — 提交数据分析问题

**请求体：**

```json
{
  "question": "各品类的销售总额是多少？"
}
```

**响应示例：**

```json
{
  "answer": "各品类销售总额如下：电子产品 156,271 元，服装 98,450 元...",
  "steps": [
    { "type": "thought", "content": "需要查询各品类销售额，需关联 products、order_items 表" },
    { "type": "action", "content": "SQL: SELECT p.category, SUM(oi.quantity * oi.unit_price)..." },
    { "type": "observation", "content": "电子产品 | 156271.0\n服装 | 98450.0\n..." },
    { "type": "thought", "content": "已得出最终答案" }
  ],
  "success": true
}
```

### GET `/api/agent/schemas` — 获取数据库表结构

返回所有可查询表的结构信息，供前端展示或 Agent 参考。

## 提问示例

- 各品类的销售总额是多少？
- 最近一个月销量最高的商品 Top 10？
- 每位客户的平均订单金额是多少？
- 哪个品类的商品种类最多？
- 订单金额超过 1000 元的订单有哪些？
