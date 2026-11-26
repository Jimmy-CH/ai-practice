# 数据分析 Agent 设计文档

## 概述

构建一个数据分析 Agent，让大模型拥有"双手"，能够自主规划步骤并调用外部工具完成复杂任务。Agent 通过 ReAct 模式（Thought → Action → Observation 循环）运作，核心工具为 SQL 查询，用户以自然语言提问，Agent 自动生成 SQL、查询数据库并返回结果。

采用两阶段渐进式实现：Phase 1 使用 LangChain 构建 ReAct Agent，Phase 2 使用 LangGraph 重构工作流编排。

## 技术选型

| 组件 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI | 异步 Web 框架 |
| AI 框架 Phase 1 | LangChain | ReAct Agent + 工具调用 |
| AI 框架 Phase 2 | LangGraph | 状态图工作流编排 |
| LLM | DeepSeek API | OpenAI 兼容接口 |
| 数据库 | SQLite（开发） | 通过 SQLAlchemy async 抽象层可切换 |
| ORM | SQLAlchemy 2.0 | 异步模式 |
| 前端 | Vue 3 + TypeScript + Vite | 单页面应用 |

## 项目结构

```
data-agent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # 数据库连接 + 抽象层
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── demo_data.py     # SQLAlchemy 示例数据模型
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── tools.py         # SQL 查询工具定义
│   │   │   ├── prompt.py        # ReAct prompt 模板
│   │   │   ├── langchain_agent.py   # Phase 1: LangChain ReAct Agent
│   │   │   └── langgraph_agent.py   # Phase 2: LangGraph Agent (预留)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   └── agent.py         # Agent 交互 API
│   │   └── schemas/
│   │       ├── __init__.py
│   │       └── agent.py         # 请求/响应模型
│   ├── requirements.txt
│   ├── .env
│   └── seed_data.py             # 示例数据初始化脚本
└── frontend/
    ├── src/
    │   ├── App.vue
    │   ├── main.ts
    │   ├── components/
    │   │   └── AgentChat.vue    # Agent 对话组件
    │   └── composables/
    │       └── useAgentChat.ts  # Agent 交互逻辑
    ├── package.json
    └── vite.config.ts
```

## 数据库层设计

### 数据库抽象层

`database.py` 提供统一的异步数据库访问接口，通过 `DATABASE_URL` 环境变量切换后端：
- 开发/演示：`sqlite+aiosqlite:///./agent_demo.db`
- 生产环境：`mysql+aiomysql://user:pass@host/db`

使用 SQLAlchemy async engine + async session，与现有 `ai-chat-backend` 保持一致。

### 示例数据模型

| 表名 | 字段 | 说明 |
|------|------|------|
| `products` | id, name, category, price, created_at | 商品表 |
| `orders` | id, customer_name, order_date, status | 订单表 |
| `order_items` | id, order_id(FK), product_id(FK), quantity, unit_price | 订单明细表 |

### 示例数据规模

- 约 20 个商品，分 4-5 个品类（电子产品、服装、食品、家居、运动）
- 约 100 个订单，跨 3 个月
- 每个订单 1-5 个商品明细
- 数据覆盖"上月"以确保查询有意义

### 数据初始化

`seed_data.py` 独立脚本，功能：
- 创建所有表
- 插入示例数据
- 支持重复运行（先清空再插入）

## Agent 核心设计（Phase 1 — LangChain）

### ReAct 循环

```
用户提问: "查询上月销量最高的商品"
    ↓
[Thought] 我需要查询订单明细，按商品汇总销量，按降序排列
    ↓
[Action] 调用 sql_query 工具
    参数: SELECT p.name, SUM(oi.quantity) as total_sold
          FROM order_items oi
          JOIN products p ON oi.product_id = p.id
          JOIN orders o ON oi.order_id = o.id
          WHERE o.order_date >= '2026-08-01' AND o.order_date < '2026-09-01'
          GROUP BY p.name
          ORDER BY total_sold DESC
    ↓
[Observation] 工具返回: [("商品A", 150), ("商品B", 120), ...]
    ↓
[Thought] 我已获得结果，销量最高的是商品A
    ↓
[Final Answer] 上月销量最高的商品是商品A，共售出150件
```

### 工具定义（tools.py）

使用 LangChain `@tool` 装饰器：

```python
@tool
def sql_query(query: str) -> str:
    """执行只读 SQL 查询。输入为 SELECT 语句，返回查询结果。"""
```

安全机制：
- 只允许 SELECT 语句（检查 SQL 开头是否为 SELECT）
- 禁止 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE
- 查询超时限制（防止慢查询）
- 返回格式化的文本表格

### Prompt 模板（prompt.py）

自定义 ReAct prompt，包含：
- 可用工具列表及描述
- Thought/Action/Observation 格式要求
- 数据库表结构信息（schema）：表名、字段名、字段类型、外键关系
- 安全约束（只读查询）
- 回答格式要求

### Agent 组装（langchain_agent.py）

- LLM：DeepSeek（通过 OpenAI 兼容接口）
- 工具集：[sql_query]
- 使用 LangChain `AgentExecutor` + ReAct prompt 构建（Phase 2 迁移到 LangGraph 的 `create_react_agent`）
- 最大迭代次数：5（防止无限循环）
- 返回完整中间步骤（intermediate_steps），供前端展示思考过程

### 核心函数签名

```python
async def run_agent(question: str) -> AgentResult:
    """
    运行数据分析 Agent。
    
    Args:
        question: 用户的自然语言问题
    
    Returns:
        AgentResult:
            - answer: str — 最终回答
            - steps: List[AgentStep] — 中间步骤列表
                每个 step 包含 type(thought/action/observation) 和 content
    """
```

## API 设计

### 请求/响应模型

```python
# 请求
class AgentQueryRequest(BaseModel):
    question: str  # 用户的自然语言问题

# 响应
class AgentStep(BaseModel):
    type: str      # "thought" | "action" | "observation"
    content: str   # 步骤内容

class AgentQueryResponse(BaseModel):
    answer: str              # 最终回答
    steps: List[AgentStep]   # 思考过程步骤
    success: bool            # 是否成功
```

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agent/query` | 提交问题，执行 Agent |
| GET | `/api/agent/schemas` | 获取数据库表结构信息（供前端展示） |

### 交互流程

```
前端 POST /api/agent/query  { "question": "查询上月销量最高商品" }
    ↓
后端 Agent 执行 ReAct 循环（可能耗时数秒）
    ↓
返回 JSON:
{
    "answer": "上月销量最高的是...",
    "steps": [
        {"type": "thought", "content": "我需要查询..."},
        {"type": "action", "content": "SELECT ..."},
        {"type": "observation", "content": "查询结果: ..."},
        {"type": "thought", "content": "已得到结果..."}
    ],
    "success": true
}
```

## 前端设计

### 界面布局

- 顶部：标题栏 "数据分析 Agent"
- 中间：对话区域
  - 用户提问气泡
  - Agent 思考过程展示区（可折叠的步骤面板）
    - 每个 step 显示类型标签（Thought/Action/Observation）+ 内容
    - 不同颜色区分不同类型（Thought=蓝色, Action=橙色, Observation=绿色）
  - 最终回答气泡（高亮显示）
- 底部：输入框 + 发送按钮 + 预设快捷问题

### 预设快捷问题

- "查询上月销量最高的商品"
- "各品类销售额对比"
- "最近30天订单趋势"
- "哪个客户下单最多"

### 交互流程

1. 用户输入自然语言问题（或点击预设问题）
2. 显示加载状态（Agent 正在思考...）
3. 收到响应后，先展示 steps（思考过程），再展示 final answer
4. 思考过程默认展开，用户可折叠

## Phase 2 预览：LangGraph 迁移

Phase 1 完成并验证后，Phase 2 将：

- 用 LangGraph 的 `StateGraph` 替代 LangChain 的 `AgentExecutor`
- 显式定义状态节点：
  - `agent_node`：LLM 推理，决定下一步行动
  - `tool_node`：执行 SQL 查询工具
  - `should_continue`：条件判断，决定是否继续循环
- 循环边控制 ReAct 循环：工具执行后回到 `agent_node`，直到 Agent 决定给出最终答案
- 支持流式输出每个节点的结果（SSE）
- 更好的错误处理和重试机制

Phase 2 是可选增强，Phase 1 已经是完整可用的系统。

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| SQL 语法错误 | Agent 观察错误信息，自动修正 SQL 重试 |
| 非 SELECT 语句 | 工具直接拒绝，返回错误提示 |
| Agent 超过最大迭代次数 | 返回已收集的信息 + 超时提示 |
| LLM API 调用失败 | 返回友好错误信息 |
| 数据库连接失败 | 返回连接错误提示 |

## 依赖清单

### 后端

```
fastapi
uvicorn
sqlalchemy
aiosqlite
python-dotenv
langchain
langchain-openai
langchain-community
```

### 前端

```
vue@3
typescript
vite
axios
```
