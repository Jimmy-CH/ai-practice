# 数据分析 Agent 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个数据分析 Agent，用户以自然语言提问，Agent 通过 ReAct 循环自动生成 SQL、查询数据库并返回结果。

**Architecture:** FastAPI 后端 + LangChain AgentExecutor（Phase 1）+ Vue 3 前端。Agent 使用 ReAct 模式（Thought → Action → Observation 循环），通过 SQL 查询工具访问 SQLite 示例数据库。

**Tech Stack:** Python 3.11, FastAPI, LangChain, SQLAlchemy, SQLite, Vue 3, TypeScript, Vite

**Spec:** `docs/superpowers/specs/2026-09-01-data-analysis-agent-design.md`

---

## 文件结构总览

```
data-agent/
├── backend/
│   ├── app/
│   │   ├── __init__.py              # 空文件
│   │   ├── main.py                  # FastAPI 入口，lifespan 初始化
│   │   ├── config.py                # Settings 类，读取 .env
│   │   ├── database.py              # SQLAlchemy async engine + session
│   │   ├── models/
│   │   │   ├── __init__.py          # 空文件
│   │   │   └── demo_data.py         # Product, Order, OrderItem 模型
│   │   ├── agent/
│   │   │   ├── __init__.py          # 空文件
│   │   │   ├── tools.py             # sql_query 工具（@tool 装饰器）
│   │   │   ├── prompt.py            # ReAct prompt 模板
│   │   │   └── langchain_agent.py   # AgentExecutor 组装 + run_agent()
│   │   ├── api/
│   │   │   ├── __init__.py          # 空文件
│   │   │   ├── router.py            # 汇总路由
│   │   │   └── agent.py             # POST /query, GET /schemas
│   │   └── schemas/
│   │       ├── __init__.py          # 空文件
│   │       └── agent.py             # AgentQueryRequest/Response, AgentStep
│   ├── requirements.txt
│   ├── .env
│   └── seed_data.py                 # 示例数据初始化脚本
└── frontend/
    ├── src/
    │   ├── App.vue
    │   ├── main.ts
    │   ├── api/
    │   │   └── agent.ts             # API 调用封装
    │   ├── components/
    │   │   └── AgentChat.vue        # 对话主组件
    │   └── composables/
    │       └── useAgentChat.ts      # Agent 交互逻辑
    ├── index.html
    ├── package.json
    ├── tsconfig.json
    ├── tsconfig.app.json
    ├── tsconfig.node.json
    └── vite.config.ts
```

---

## Task 1: 后端项目脚手架

**Files:**
- Create: `data-agent/backend/requirements.txt`
- Create: `data-agent/backend/.env`
- Create: `data-agent/backend/app/__init__.py`

- [ ] **Step 1: 创建目录结构**

```powershell
cd D:\StudyProjects\ai-practice
New-Item -ItemType Directory -Path "data-agent\backend\app\models" -Force
New-Item -ItemType Directory -Path "data-agent\backend\app\agent" -Force
New-Item -ItemType Directory -Path "data-agent\backend\app\api" -Force
New-Item -ItemType Directory -Path "data-agent\backend\app\schemas" -Force
```

- [ ] **Step 2: 创建 requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
aiosqlite==0.20.0
python-dotenv==1.0.1
pydantic==2.9.2
langchain==0.3.1
langchain-openai==0.2.1
langchain-community==0.3.1
```

- [ ] **Step 3: 创建 .env**

```
DATABASE_URL=sqlite+aiosqlite:///./agent_demo.db
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

- [ ] **Step 4: 创建空的 __init__.py 文件**

在 `data-agent/backend/app/`、`models/`、`agent/`、`api/`、`schemas/` 各创建一个空的 `__init__.py`。

- [ ] **Step 5: 创建虚拟环境并安装依赖**

```powershell
cd D:\StudyProjects\ai-practice\data-agent\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

- [ ] **Step 6: 提交**

```bash
git add data-agent/backend/requirements.txt data-agent/backend/.env data-agent/backend/app/__init__.py data-agent/backend/app/models/__init__.py data-agent/backend/app/agent/__init__.py data-agent/backend/app/api/__init__.py data-agent/backend/app/schemas/__init__.py
git commit -m "chore: scaffold data-agent backend project"
```

---

## Task 2: 配置管理 + 数据库连接

**Files:**
- Create: `data-agent/backend/app/config.py`
- Create: `data-agent/backend/app/database.py`

- [ ] **Step 1: 创建 config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "Data Analysis Agent"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agent_demo.db")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


settings = Settings()
```

- [ ] **Step 2: 创建 database.py**

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库 session。"""
    async with async_session() as session:
        yield session
```

- [ ] **Step 3: 提交**

```bash
git add data-agent/backend/app/config.py data-agent/backend/app/database.py
git commit -m "feat: add config and database module"
```

---

## Task 3: 数据模型

**Files:**
- Create: `data-agent/backend/app/models/demo_data.py`

- [ ] **Step 1: 创建数据模型**

```python
from datetime import datetime, date
from sqlalchemy import String, Integer, Float, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed")

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="order_items")
```

- [ ] **Step 2: 提交**

```bash
git add data-agent/backend/app/models/demo_data.py
git commit -m "feat: add product, order, order_item models"
```

---

## Task 4: 示例数据初始化

**Files:**
- Create: `data-agent/backend/seed_data.py`

- [ ] **Step 1: 创建 seed_data.py**

使用同步 SQLAlchemy（因为是独立脚本，不在 async 上下文中运行）：

```python
"""示例数据初始化脚本。可重复运行（先清空再插入）。"""
import random
from datetime import date, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database import Base
from app.models.demo_data import Product, Order, OrderItem

# 同步引擎（脚本用途）
SYNC_DB_URL = settings.DATABASE_URL.replace("+aiosqlite", "").replace("+aiomysql", "")
sync_engine = create_engine(SYNC_DB_URL)


PRODUCTS = [
    # 电子产品
    ("iPhone 15", "电子产品", 5999.0),
    ("MacBook Air", "电子产品", 8999.0),
    ("AirPods Pro", "电子产品", 1899.0),
    ("iPad Mini", "电子产品", 3799.0),
    ("机械键盘", "电子产品", 599.0),
    # 服装
    ("运动T恤", "服装", 129.0),
    ("牛仔裤", "服装", 299.0),
    ("羽绒服", "服装", 899.0),
    ("运动鞋", "服装", 499.0),
    ("棒球帽", "服装", 79.0),
    # 食品
    ("进口牛奶", "食品", 68.0),
    ("坚果礼盒", "食品", 128.0),
    ("有机鸡蛋", "食品", 39.0),
    ("精品咖啡", "食品", 89.0),
    # 家居
    ("台灯", "家居", 199.0),
    ("收纳箱", "家居", 49.0),
    ("四件套", "家居", 399.0),
    # 运动
    ("瑜伽垫", "运动", 99.0),
    ("跑步机", "运动", 2999.0),
    ("哑铃套装", "运动", 299.0),
]

CUSTOMERS = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十",
             "郑一", "冯二", "陈明", "林华", "黄强", "刘洋", "杨帆"]


def seed():
    Base.metadata.drop_all(sync_engine)
    Base.metadata.create_all(sync_engine)

    with Session(sync_engine) as session:
        # 插入商品
        products = []
        for name, category, price in PRODUCTS:
            p = Product(name=name, category=category, price=price)
            products.append(p)
        session.add_all(products)
        session.flush()

        # 生成订单（跨最近 3 个月）
        today = date.today()
        start_date = today - timedelta(days=90)
        orders = []
        for i in range(100):
            order_date = start_date + timedelta(days=random.randint(0, 89))
            customer = random.choice(CUSTOMERS)
            o = Order(customer_name=customer, order_date=order_date, status="completed")
            orders.append(o)
        session.add_all(orders)
        session.flush()

        # 生成订单明细
        for order in orders:
            n_items = random.randint(1, 5)
            chosen = random.sample(products, n_items)
            for product in chosen:
                qty = random.randint(1, 5)
                oi = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=qty,
                    unit_price=product.price,
                )
                session.add(oi)

        session.commit()
        print(f"已插入 {len(products)} 个商品, {len(orders)} 个订单")


if __name__ == "__main__":
    seed()
```

- [ ] **Step 2: 运行 seed 脚本验证**

```powershell
cd D:\StudyProjects\ai-practice\data-agent\backend
.\venv\Scripts\Activate.ps1
python seed_data.py
```

Expected: `已插入 20 个商品, 100 个订单`

- [ ] **Step 3: 提交**

```bash
git add data-agent/backend/seed_data.py
git commit -m "feat: add seed data script with demo products and orders"
```

---

## Task 5: SQL 查询工具

**Files:**
- Create: `data-agent/backend/app/agent/tools.py`

- [ ] **Step 1: 创建 SQL 查询工具**

工具使用同步 SQLAlchemy（LangChain 工具在 sync 上下文执行）：

```python
"""Agent 工具定义：SQL 只读查询。"""
from sqlalchemy import create_engine, text
from langchain_core.tools import tool
from app.config import settings

# 同步引擎供工具使用
SYNC_DB_URL = settings.DATABASE_URL.replace("+aiosqlite", "").replace("+aiomysql", "")
sync_engine = create_engine(SYNC_DB_URL)

FORBIDDEN_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]


def _check_sql_safety(query: str) -> str | None:
    """检查 SQL 是否安全。返回 None 表示安全，否则返回错误信息。"""
    cleaned = query.strip().upper()
    if not cleaned.startswith("SELECT"):
        return "安全错误：只允许 SELECT 查询"
    for keyword in FORBIDDEN_KEYWORDS:
        # 检查子查询中是否包含危险关键字
        if keyword in cleaned and keyword != "SELECT":
            # CREATE TABLE / DROP TABLE 等可能在子查询中出现，简单检查
            if keyword in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"):
                return f"安全错误：禁止使用 {keyword} 语句"
    return None


@tool
def sql_query(query: str) -> str:
    """执行只读 SQL 查询。输入为 SELECT 语句，返回查询结果的文本表格。
    可用表：products(id, name, category, price, created_at),
    orders(id, customer_name, order_date, status),
    order_items(id, order_id, product_id, quantity, unit_price)
    """
    safety_error = _check_sql_safety(query)
    if safety_error:
        return safety_error

    try:
        with sync_engine.connect() as conn:
            result = conn.execute(text(query))
            columns = list(result.keys())
            rows = result.fetchall()

            if not rows:
                return "查询结果为空"

            # 格式化为文本表格
            header = " | ".join(columns)
            separator = "-" * len(header)
            lines = [header, separator]
            for row in rows[:50]:  # 限制最多返回 50 行
                lines.append(" | ".join(str(v) for v in row))

            if len(rows) > 50:
                lines.append(f"... (共 {len(rows)} 行，仅显示前 50 行)")

            return "\n".join(lines)

    except Exception as e:
        return f"SQL 执行错误: {str(e)}"
```

- [ ] **Step 2: 手动验证工具**

在 Python REPL 中快速测试：

```powershell
cd D:\StudyProjects\ai-practice\data-agent\backend
.\venv\Scripts\Activate.ps1
python -c "from app.agent.tools import sql_query; print(sql_query.invoke({'query': 'SELECT count(*) FROM products'}))"
```

Expected: 包含 `1` 的表格输出

- [ ] **Step 3: 提交**

```bash
git add data-agent/backend/app/agent/tools.py
git commit -m "feat: add sql_query tool with safety checks"
```

---

## Task 6: ReAct Prompt 模板

**Files:**
- Create: `data-agent/backend/app/agent/prompt.py`

- [ ] **Step 1: 创建 ReAct prompt**

```python
"""ReAct Agent 的 prompt 模板。"""

REACT_PROMPT_TEMPLATE = """你是一个数据分析助手，可以通过 SQL 查询数据库来回答用户的问题。

你可以使用以下工具：
{tools}

使用以下格式进行思考和行动：

Question: 用户输入的问题
Thought: 你应该时刻思考该怎么做
Action: 要采取的动作，必须是 [{tool_names}] 之一
Action Input: 动作的输入参数
Observation: 动作的结果
... (Thought/Action/Action Input/Observation 可以重复多次)
Thought: 我现在知道最终答案了
Final Answer: 对用户问题的最终回答

重要规则：
1. Action 只能是 sql_query
2. Action Input 必须是合法的 SELECT SQL 语句
3. 只使用 SELECT 语句，不要尝试修改数据
4. 如果 SQL 执行出错，分析错误原因并修正后重试

数据库表结构：
- products: id(整数), name(文本), category(文本), price(浮点数), created_at(日期时间)
- orders: id(整数), customer_name(文本), order_date(日期), status(文本)
- order_items: id(整数), order_id(整数,外键→orders.id), product_id(整数,外键→products.id), quantity(整数), unit_price(浮点数)

开始！

Question: {input}
{agent_scratchpad}"""
```

- [ ] **Step 2: 提交**

```bash
git add data-agent/backend/app/agent/prompt.py
git commit -m "feat: add ReAct prompt template with schema info"
```

---

## Task 7: LangChain Agent 组装

**Files:**
- Create: `data-agent/backend/app/agent/langchain_agent.py`

- [ ] **Step 1: 组装 Agent**

```python
"""LangChain ReAct Agent 组装。"""
from typing import List
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate

from app.config import settings
from app.agent.tools import sql_query
from app.agent.prompt import REACT_PROMPT_TEMPLATE


class AgentStep(BaseModel):
    type: str      # "thought" | "action" | "observation"
    content: str


class AgentResult(BaseModel):
    answer: str
    steps: List[AgentStep]
    success: bool


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model="deepseek-chat",
        temperature=0,
    )


def _parse_intermediate_steps(steps) -> List[AgentStep]:
    """将 LangChain 的 intermediate_steps 解析为前端友好的步骤列表。"""
    result_steps = []
    for action, observation in steps:
        # Thought 部分在 action.log 中
        if action.log and action.log.strip():
            for line in action.log.strip().split("\n"):
                line = line.strip()
                if line.startswith("Thought:"):
                    result_steps.append(AgentStep(
                        type="thought",
                        content=line.replace("Thought:", "").strip()
                    ))
                elif line.startswith("Action:"):
                    result_steps.append(AgentStep(
                        type="action",
                        content=line.replace("Action:", "").strip()
                    ))

        # Action Input
        if action.tool_input:
            result_steps.append(AgentStep(
                type="action",
                content=f"SQL: {action.tool_input}"
            ))

        # Observation
        result_steps.append(AgentStep(
            type="observation",
            content=str(observation)
        ))

    return result_steps


async def run_agent(question: str) -> AgentResult:
    """运行数据分析 Agent。"""
    llm = _build_llm()
    tools = [sql_query]

    prompt = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)

    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        max_iterations=5,
        verbose=True,
        handle_parsing_errors=True,
    )

    try:
        result = await executor.ainvoke({"input": question})
        steps = _parse_intermediate_steps(result.get("intermediate_steps", []))

        # 添加最终 Thought（如果有）
        if "output" in result:
            steps.append(AgentStep(type="thought", content="已得出最终答案"))

        return AgentResult(
            answer=result.get("output", "抱歉，我无法回答这个问题。"),
            steps=steps,
            success=True,
        )
    except Exception as e:
        return AgentResult(
            answer=f"Agent 执行出错: {str(e)}",
            steps=[],
            success=False,
        )
```

- [ ] **Step 2: 提交**

```bash
git add data-agent/backend/app/agent/langchain_agent.py
git commit -m "feat: add LangChain ReAct agent with AgentExecutor"
```

---

## Task 8: API 层 — Schemas + Endpoints

**Files:**
- Create: `data-agent/backend/app/schemas/agent.py`
- Create: `data-agent/backend/app/api/agent.py`
- Create: `data-agent/backend/app/api/router.py`
- Create: `data-agent/backend/app/main.py`

- [ ] **Step 1: 创建 schemas/agent.py**

```python
from typing import List
from pydantic import BaseModel


class AgentQueryRequest(BaseModel):
    question: str


class AgentStepResponse(BaseModel):
    type: str      # "thought" | "action" | "observation"
    content: str


class AgentQueryResponse(BaseModel):
    answer: str
    steps: List[AgentStepResponse]
    success: bool


class TableSchema(BaseModel):
    table_name: str
    columns: List[dict]


class SchemasResponse(BaseModel):
    tables: List[TableSchema]
```

- [ ] **Step 2: 创建 api/agent.py**

```python
from fastapi import APIRouter
from app.schemas.agent import AgentQueryRequest, AgentQueryResponse, AgentStepResponse, SchemasResponse, TableSchema
from app.agent.langchain_agent import run_agent

router = APIRouter(prefix="/agent", tags=["Agent"])

DB_SCHEMA = [
    TableSchema(
        table_name="products",
        columns=[
            {"name": "id", "type": "INTEGER", "description": "商品ID"},
            {"name": "name", "type": "TEXT", "description": "商品名称"},
            {"name": "category", "type": "TEXT", "description": "商品品类"},
            {"name": "price", "type": "REAL", "description": "商品价格"},
            {"name": "created_at", "type": "DATETIME", "description": "创建时间"},
        ],
    ),
    TableSchema(
        table_name="orders",
        columns=[
            {"name": "id", "type": "INTEGER", "description": "订单ID"},
            {"name": "customer_name", "type": "TEXT", "description": "客户姓名"},
            {"name": "order_date", "type": "DATE", "description": "订单日期"},
            {"name": "status", "type": "TEXT", "description": "订单状态"},
        ],
    ),
    TableSchema(
        table_name="order_items",
        columns=[
            {"name": "id", "type": "INTEGER", "description": "明细ID"},
            {"name": "order_id", "type": "INTEGER", "description": "订单ID(外键)"},
            {"name": "product_id", "type": "INTEGER", "description": "商品ID(外键)"},
            {"name": "quantity", "type": "INTEGER", "description": "数量"},
            {"name": "unit_price", "type": "REAL", "description": "单价"},
        ],
    ),
]


@router.post("/query", response_model=AgentQueryResponse)
async def query(request: AgentQueryRequest):
    """提交自然语言问题，Agent 执行 ReAct 循环后返回结果。"""
    result = await run_agent(request.question)
    return AgentQueryResponse(
        answer=result.answer,
        steps=[AgentStepResponse(type=s.type, content=s.content) for s in result.steps],
        success=result.success,
    )


@router.get("/schemas", response_model=SchemasResponse)
async def get_schemas():
    """获取数据库表结构信息。"""
    return SchemasResponse(tables=DB_SCHEMA)
```

- [ ] **Step 3: 创建 api/router.py**

```python
from fastapi import APIRouter
from app.api import agent

api_router = APIRouter(prefix="/api")
api_router.include_router(agent.router)
```

- [ ] **Step 4: 创建 main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.database import engine, Base
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
```

- [ ] **Step 5: 启动后端验证**

```powershell
cd D:\StudyProjects\ai-practice\data-agent\backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8001
```

用浏览器访问 `http://localhost:8001/docs` 确认 Swagger UI 正常显示。

- [ ] **Step 6: 提交**

```bash
git add data-agent/backend/app/schemas/agent.py data-agent/backend/app/api/agent.py data-agent/backend/app/api/router.py data-agent/backend/app/main.py
git commit -m "feat: add FastAPI endpoints for agent query and schemas"
```

---

## Task 9: 前端项目脚手架

**Files:**
- Create: `data-agent/frontend/` 整个前端项目

- [ ] **Step 1: 用 Vite 创建 Vue 3 + TypeScript 项目**

```powershell
cd D:\StudyProjects\ai-practice\data-agent
npm create vite@latest frontend -- --template vue-ts
cd frontend
npm install
npm install axios
```

- [ ] **Step 2: 配置 vite.config.ts 代理**

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3001,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 3: 提交**

```bash
git add data-agent/frontend/
git commit -m "chore: scaffold frontend with Vue 3 + TypeScript + Vite"
```

---

## Task 10: 前端 — API 层 + Composable

**Files:**
- Create: `data-agent/frontend/src/api/agent.ts`
- Create: `data-agent/frontend/src/composables/useAgentChat.ts`

- [ ] **Step 1: 创建 api/agent.ts**

```typescript
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface AgentStep {
  type: 'thought' | 'action' | 'observation'
  content: string
}

export interface AgentQueryResponse {
  answer: string
  steps: AgentStep[]
  success: boolean
}

export async function queryAgent(question: string): Promise<AgentQueryResponse> {
  const { data } = await api.post<AgentQueryResponse>('/agent/query', { question })
  return data
}

export interface TableSchema {
  table_name: string
  columns: { name: string; type: string; description: string }[]
}

export async function getSchemas(): Promise<TableSchema[]> {
  const { data } = await api.get<{ tables: TableSchema[] }>('/agent/schemas')
  return data.tables
}
```

- [ ] **Step 2: 创建 composables/useAgentChat.ts**

```typescript
import { ref } from 'vue'
import { queryAgent, type AgentQueryResponse, type AgentStep } from '../api/agent'

export interface ChatMessage {
  role: 'user' | 'agent'
  content: string
  steps?: AgentStep[]
  loading?: boolean
}

export function useAgentChat() {
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)

  async function sendQuestion(question: string) {
    // 添加用户消息
    messages.value.push({ role: 'user', content: question })

    // 添加加载中的 agent 消息
    const agentMsg: ChatMessage = { role: 'agent', content: '', loading: true }
    messages.value.push(agentMsg)
    isLoading.value = true

    try {
      const result = await queryAgent(question)
      const idx = messages.value.length - 1
      messages.value[idx] = {
        role: 'agent',
        content: result.answer,
        steps: result.steps,
        loading: false,
      }
    } catch (error: any) {
      const idx = messages.value.length - 1
      messages.value[idx] = {
        role: 'agent',
        content: `请求失败: ${error.message}`,
        steps: [],
        loading: false,
      }
    } finally {
      isLoading.value = false
    }
  }

  return { messages, isLoading, sendQuestion }
}
```

- [ ] **Step 3: 提交**

```bash
git add data-agent/frontend/src/api/agent.ts data-agent/frontend/src/composables/useAgentChat.ts
git commit -m "feat: add frontend API client and agent chat composable"
```

---

## Task 11: 前端 — AgentChat 组件

**Files:**
- Create: `data-agent/frontend/src/components/AgentChat.vue`
- Modify: `data-agent/frontend/src/App.vue`

- [ ] **Step 1: 创建 AgentChat.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useAgentChat } from '../composables/useAgentChat'

const { messages, isLoading, sendQuestion } = useAgentChat()
const inputText = ref('')

const quickQuestions = [
  '查询上月销量最高的商品',
  '各品类销售额对比',
  '最近30天订单趋势',
  '哪个客户下单最多',
]

function handleSend() {
  const q = inputText.value.trim()
  if (!q || isLoading.value) return
  inputText.value = ''
  sendQuestion(q)
}

function handleQuick(q: string) {
  if (isLoading.value) return
  sendQuestion(q)
}

function stepColor(type: string): string {
  switch (type) {
    case 'thought': return '#3b82f6'
    case 'action': return '#f59e0b'
    case 'observation': return '#10b981'
    default: return '#6b7280'
  }
}

function stepLabel(type: string): string {
  switch (type) {
    case 'thought': return '💭 Thought'
    case 'action': return '⚡ Action'
    case 'observation': return '👁 Observation'
    default: return type
  }
}
</script>

<template>
  <div class="agent-chat">
    <div class="messages">
      <div v-for="(msg, i) in messages" :key="i" :class="['message', msg.role]">
        <div class="bubble">
          <div v-if="msg.role === 'user'" class="user-text">{{ msg.content }}</div>
          <template v-else>
            <div v-if="msg.loading" class="loading">Agent 正在思考...</div>
            <template v-else>
              <div v-if="msg.steps && msg.steps.length" class="steps-panel">
                <details open>
                  <summary>思考过程 ({{ msg.steps!.length }} 步)</summary>
                  <div v-for="(step, j) in msg.steps" :key="j" class="step">
                    <span class="step-tag" :style="{ background: stepColor(step.type) }">
                      {{ stepLabel(step.type) }}
                    </span>
                    <pre class="step-content">{{ step.content }}</pre>
                  </div>
                </details>
              </div>
              <div class="answer">{{ msg.content }}</div>
            </template>
          </template>
        </div>
      </div>
    </div>

    <div class="quick-questions">
      <button v-for="q in quickQuestions" :key="q" @click="handleQuick(q)" :disabled="isLoading">
        {{ q }}
      </button>
    </div>

    <div class="input-area">
      <input
        v-model="inputText"
        @keyup.enter="handleSend"
        :disabled="isLoading"
        placeholder="输入你的问题..."
      />
      <button @click="handleSend" :disabled="isLoading || !inputText.trim()">发送</button>
    </div>
  </div>
</template>

<style scoped>
.agent-chat {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 900px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message {
  margin-bottom: 16px;
}

.message.user .bubble {
  background: #3b82f6;
  color: white;
  border-radius: 12px 12px 0 12px;
  padding: 12px 16px;
  max-width: 70%;
  margin-left: auto;
}

.message.agent .bubble {
  background: #f3f4f6;
  border-radius: 12px 12px 12px 0;
  padding: 12px 16px;
  max-width: 85%;
}

.loading {
  color: #6b7280;
  font-style: italic;
}

.steps-panel {
  margin-bottom: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
  background: #fafafa;
}

.steps-panel summary {
  cursor: pointer;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.step {
  margin-bottom: 8px;
}

.step-tag {
  display: inline-block;
  color: white;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  margin-right: 8px;
}

.step-content {
  margin: 4px 0 0 0;
  padding: 6px 10px;
  background: white;
  border-radius: 4px;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
}

.answer {
  font-size: 15px;
  line-height: 1.6;
  color: #111827;
}

.quick-questions {
  padding: 8px 20px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.quick-questions button {
  padding: 6px 12px;
  border: 1px solid #d1d5db;
  border-radius: 16px;
  background: white;
  cursor: pointer;
  font-size: 13px;
}

.quick-questions button:hover {
  background: #f3f4f6;
}

.input-area {
  display: flex;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid #e5e7eb;
}

.input-area input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
}

.input-area button {
  padding: 10px 20px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}

.input-area button:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}
</style>
```

- [ ] **Step 2: 修改 App.vue**

```vue
<script setup lang="ts">
import AgentChat from '@/components/AgentChat.vue'
</script>

<template>
  <div id="app">
    <header>
      <h1>📊 数据分析 Agent</h1>
    </header>
    <AgentChat />
  </div>
</template>

<style>
body {
  margin: 0;
  background: #ffffff;
}

header {
  text-align: center;
  padding: 16px;
  background: #1f2937;
  color: white;
}

header h1 {
  margin: 0;
  font-size: 20px;
}
</style>
```

- [ ] **Step 3: 启动前端验证**

```powershell
cd D:\StudyProjects\ai-practice\data-agent\frontend
npm run dev
```

浏览器访问 `http://localhost:3001`，确认页面正常渲染。

- [ ] **Step 4: 提交**

```bash
git add data-agent/frontend/src/
git commit -m "feat: add AgentChat component with step visualization"
```

---

## Task 12: 端到端集成验证

- [ ] **Step 1: 确保后端运行**

```powershell
cd D:\StudyProjects\ai-practice\data-agent\backend
.\venv\Scripts\Activate.ps1
python seed_data.py
uvicorn app.main:app --reload --port 8001
```

- [ ] **Step 2: 确保前端运行**

```powershell
cd D:\StudyProjects\ai-practice\data-agent\frontend
npm run dev
```

- [ ] **Step 3: 测试核心场景**

在浏览器中访问 `http://localhost:3001`，依次测试：

1. 点击"查询上月销量最高的商品" → 观察 Agent 的 Thought/Action/Observation 步骤 → 确认返回正确结果
2. 点击"各品类销售额对比" → 确认 Agent 生成带 GROUP BY 的 SQL
3. 在输入框中输入"哪个客户下单最多" → 确认 Agent 能处理不同问题

- [ ] **Step 4: 最终提交**

```bash
git add .
git commit -m "feat: data analysis agent complete - phase 1"
```

---

## 验证清单

| 验证项 | 预期结果 |
|--------|---------|
| `python seed_data.py` | 输出 "已插入 20 个商品, 100 个订单" |
| `GET /api/agent/schemas` | 返回 3 张表的结构信息 |
| `POST /api/agent/query` 提问 | 返回 answer + steps，steps 包含 thought/action/observation |
| 前端页面加载 | 显示标题、输入框、预设问题按钮 |
| 点击预设问题 | 展示 Agent 思考过程 + 最终回答 |
| SQL 安全：尝试 DROP TABLE | 工具拒绝执行，返回安全错误 |
