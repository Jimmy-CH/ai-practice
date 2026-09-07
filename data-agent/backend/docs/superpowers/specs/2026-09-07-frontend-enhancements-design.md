# 前端登录/用户管理 + Agent 体验增强 — 设计文档

## 概述

在现有 Data Analysis Agent 项目基础上，分两阶段增加功能：

- **第一阶段**：前端登录页面 + 用户管理页面（含后端补充 API），让已有的认证和 RBAC 系统在前端完整可用
- **第二阶段**：Agent 体验增强 — 对话历史持久化、流式响应（SSE）、数据可视化图表、结果导出 CSV/Excel

## 技术选型

| 组件 | 方案 |
|------|------|
| 前端路由 | Vue Router 4 |
| UI 组件库 | Element Plus |
| 图表库 | ECharts + vue-echarts |
| 流式响应 | SSE（Server-Sent Events） |
| CSV 导出 | papaparse |
| 状态管理 | Vue Reactivity（ref/reactive，不引入 Pinia） |
| Token 存储 | localStorage + axios 拦截器 |

## 第一阶段：前端登录 + 用户管理

### 前端文件结构

```
frontend/src/
├── api/
│   ├── agent.ts          # 现有 Agent API
│   ├── auth.ts           # 新增：登录 API
│   └── users.ts          # 新增：用户管理 API
├── components/
│   ├── AgentChat.vue     # 现有（第二阶段改造）
│   ├── LoginView.vue     # 新增：登录页
│   └── UserManage.vue    # 新增：用户管理页
├── composables/
│   ├── useAgentChat.ts   # 现有（第二阶段改造）
│   └── useAuth.ts        # 新增：认证状态管理
├── router/
│   └── index.ts          # 新增：Vue Router 配置
├── layouts/
│   └── MainLayout.vue    # 新增：Element Plus 布局
├── App.vue               # 改造：路由出口
└── main.ts               # 改造：注册 Element Plus + Router
```

### 前端路由

| 路径 | 页面 | 权限 |
|------|------|------|
| `/login` | 登录页 | 公开 |
| `/` | Agent 聊天主页面 | 需登录（editor/admin） |
| `/users` | 用户管理 | 需登录（admin） |

路由守卫：全局前置守卫检查 localStorage 中是否有 access_token，无 token 重定向到 `/login`。

### 布局设计（MainLayout.vue）

使用 Element Plus `el-container`：

- **顶栏**（el-header）：左侧项目标题，右侧当前用户名 + 角色标签 + 退出登录按钮
- **左侧边栏**（el-aside）：el-menu 导航菜单，包含「Agent 对话」和「用户管理」两项
- **主内容区**（el-main）：`<router-view />` 根据路由切换

### 登录页（LoginView.vue）

- 居中卡片式登录表单
- 使用 el-form + el-input + el-button
- 字段：用户名、密码
- 登录成功后：存储 access_token 和 refresh_token 到 localStorage，跳转到 `/`
- 登录失败：el-message 提示错误信息

### 认证状态管理（useAuth.ts）

```typescript
// 核心功能
export function useAuth() {
  const token = ref(localStorage.getItem('access_token') || '')
  const user = ref<UserInfo | null>(null)

  // 登录：调用 /api/auth/login，存储 token
  async function login(username: string, password: string): Promise<void>

  // 退出：清除 token 和用户信息，跳转 /login
  function logout(): void

  // 刷新 token：调用 /api/auth/refresh
  async function refreshToken(): Promise<void>

  // 获取当前用户信息：调用 /api/users/me
  async function fetchUser(): Promise<void>

  // 是否已登录
  const isAuthenticated = computed(() => !!token.value)

  return { token, user, isAuthenticated, login, logout, refreshToken, fetchUser }
}
```

### Axios 拦截器

在 `api/` 层统一配置 axios 实例：

- **请求拦截器**：自动附加 `Authorization: Bearer <access_token>`
- **响应拦截器**：
  - 401 → 尝试刷新 token，失败则清除 token 跳转 `/login`
  - 403 → el-message 提示权限不足
  - 使用请求队列避免并发刷新

### 用户管理页（UserManage.vue）

仅 admin 角色可访问。使用 Element Plus 组件：

- **el-table**：展示用户列表
  - 列：ID、用户名、邮箱、手机号、角色（el-tag）、状态（el-switch）、创建时间、操作
- **角色分配**：el-select 下拉选择角色，修改后调用 `PUT /api/users/{id}/role`
- **启用/禁用**：el-switch 切换，调用 `PUT /api/users/{id}/active`
- **删除用户**：el-popconfirm 确认后调用 `DELETE /api/users/{id}`

### 后端新增 API（第一阶段）

#### 启用/禁用用户

```
PUT /api/users/{user_id}/active
Body: { "is_active": true/false }
Response: UserOut
权限: admin
```

约束：不能禁用自己。

#### 删除用户

```
DELETE /api/users/{user_id}
Response: { "message": "用户已删除" }
权限: admin
```

约束：不能删除自己、不能删除最后一个 admin。

#### 后端文件变更

| 文件 | 变更 |
|------|------|
| `app/users/router.py` | 新增 `PUT /{user_id}/active` 和 `DELETE /{user_id}` |
| `app/users/service.py` | 新增 `update_user_active()` 和 `delete_user()` |
| `app/users/schemas.py` | 新增 `UpdateActiveRequest` |

## 第二阶段：Agent 体验增强

### 1. 对话历史持久化

#### 新增数据模型

```python
# app/models/conversation.py

class Conversation(Base):
    __tablename__ = "conversations"
    id: int (PK)
    user_id: int (FK → users.id)
    title: str (String(100))  # 取第一条用户消息的前 20 字
    created_at: datetime
    updated_at: datetime
    messages: list["Message"] (relationship)

class Message(Base):
    __tablename__ = "messages"
    id: int (PK)
    conversation_id: int (FK → conversations.id)
    role: str (String(10))  # "user" / "agent"
    content: str (Text)
    steps: str (Text, default="[]")  # JSON 序列化的 AgentStep 列表
    created_at: datetime
```

#### 新增 API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/conversations` | GET | 获取当前用户的会话列表（按 updated_at 倒序） |
| `/api/conversations` | POST | 创建新会话（title 可选，默认"新对话"） |
| `/api/conversations/{id}` | GET | 获取某会话的完整消息记录 |
| `/api/conversations/{id}` | DELETE | 删除会话及其所有消息 |

权限：所有登录用户。用户只能访问自己的会话。

#### 前端改造

- AgentChat.vue 左侧增加会话列表面板（可折叠）
- 新建对话 / 切换对话 / 删除对话
- 每次 Agent 问答完成后，自动将消息存入当前会话
- 进入页面时加载会话列表，点击切换加载消息记录

#### 后端文件变更

| 文件 | 变更 |
|------|------|
| `app/models/conversation.py` | 新增 Conversation、Message 模型 |
| `app/api/conversation.py` | 新增对话管理 API 路由 |
| `app/schemas/conversation.py` | 新增请求/响应模型 |
| `app/services/conversation.py` | 新增对话管理业务逻辑 |
| `app/api/router.py` | 注册 conversation 路由 |
| `app/agent/langchain_agent.py` | run_agent 返回后自动保存消息 |

### 2. 流式响应（SSE）

#### 后端 SSE 端点

新增 `POST /api/agent/query/stream`，使用 FastAPI `StreamingResponse` + `text/event-stream`：

```
event: thought
data: {"content": "需要查询 products 表..."}

event: action
data: {"content": "sql_query", "input": "SELECT ..."}

event: observation
data: {"content": "查询结果..."}

event: answer
data: {"content": "最终答案..."}

event: done
data: {"success": true, "conversation_id": 1}
```

实现方式：使用 LangChain 的 `astream_events` API 获取 Agent 中间步骤，通过 asyncio.Queue 传递给 StreamingResponse。SSE 流结束后，自动将对话保存到 conversation 表中（复用第一阶段的持久化逻辑）。

**注意**：SSE 端点同样需要保存对话历史，在流结束时（`done` 事件前）自动创建/更新 Conversation 和 Message 记录。

#### 前端 SSE 接收

使用 `fetch` + `ReadableStream` 接收 SSE 事件（因为 EventSource 不支持 POST 请求和自定义 Header）：

```typescript
async function* streamQuestion(question: string): AsyncGenerator<SSEEvent> {
  const response = await fetch('/api/agent/query/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ question })
  })
  const reader = response.body!.getReader()
  // 解析 SSE 文本流，yield 每个事件
}
```

前端逐步渲染：思考步骤实时追加显示，最终答案在 `answer` 事件后渲染。

#### 后端文件变更

| 文件 | 变更 |
|------|------|
| `app/api/agent.py` | 新增 `POST /query/stream` SSE 端点 |
| `app/agent/langchain_agent.py` | 新增 `stream_agent()` 异步生成器函数 |

### 3. 数据可视化图表

#### 方案

Agent 工具新增 `generate_chart`，当用户问题涉及数据可视化时，Agent 同时调用 `sql_query` 获取数据和 `generate_chart` 生成图表配置。

#### generate_chart 工具

```python
@tool
def generate_chart(chart_type: str, title: str, labels: str, values: str) -> str:
    """生成图表配置。
    chart_type: bar/line/pie
    title: 图表标题
    labels: JSON 数组字符串，如 '["A","B","C"]'
    values: JSON 数组字符串，如 '[100,200,300]'
    返回 ECharts option 的 JSON 配置字符串。
    """
```

#### chart_data 数据流

1. Agent 判断用户问题需要可视化时，调用 `sql_query` 获取数据，再调用 `generate_chart` 生成图表配置
2. `run_agent()` / `stream_agent()` 在解析 intermediate_steps 时，检测 `generate_chart` 工具的返回结果
3. 将图表配置 JSON 解析为 `ChartData` 对象，附加到 `AgentResult` 中返回
4. 前端从 `chart_data` 字段读取并渲染图表

#### chart_data 响应字段

`AgentQueryResponse` 新增可选字段：

```python
class ChartData(BaseModel):
    type: str          # "bar" | "line" | "pie"
    title: str
    x_axis: List[str]
    series: List[dict]  # [{"name": "销售额", "data": [...]}]

class AgentQueryResponse(BaseModel):
    answer: str
    steps: List[AgentStepResponse]
    success: bool
    chart_data: Optional[ChartData] = None  # 新增
```

#### 前端图表渲染

- AgentChat.vue 中检测 `chart_data` 字段
- 如果存在，使用 vue-echarts 渲染对应图表
- 图表显示在回答文本下方
- 支持柱状图（bar）、折线图（line）、饼图（pie）

#### 后端文件变更

| 文件 | 变更 |
|------|------|
| `app/agent/tools.py` | 新增 `generate_chart` 工具 |
| `app/agent/prompt.py` | prompt 中增加图表工具使用说明 |
| `app/agent/langchain_agent.py` | AgentResult 新增 chart_data 字段 |
| `app/schemas/agent.py` | 新增 ChartData 模型 |
| `app/api/agent.py` | DB_SCHEMA 中注册新工具 |

### 4. 结果导出 CSV/Excel

#### 方案

纯前端导出，无需后端改动。

- 在 Agent 回答区域增加「导出 CSV」按钮
- 从 Agent 的 SQL 查询结果（observation 步骤）中解析结构化数据
- 使用 `papaparse` 库将数据转为 CSV 并触发下载
- 文件名格式：`query_result_YYYYMMDD_HHmmss.csv`

#### 前端文件变更

| 文件 | 变更 |
|------|------|
| `components/AgentChat.vue` | 增加导出按钮 |
| `utils/export.ts` | 新增 CSV 导出工具函数 |

### 新增依赖

**后端**：无新增（现有依赖已足够）

**前端**：
```json
{
  "dependencies": {
    "vue-router": "^4.4.0",
    "element-plus": "^2.8.0",
    "echarts": "^5.5.0",
    "vue-echarts": "^7.0.0",
    "papaparse": "^5.4.0"
  },
  "devDependencies": {
    "@types/papaparse": "^5.3.0"
  }
}
```

## 错误处理

### 前端

| 场景 | 处理 |
|------|------|
| 401 Unauthorized | 自动刷新 token，失败则跳转登录页 |
| 403 Forbidden | el-message 提示「权限不足」 |
| 网络错误 | el-message 提示「网络连接失败」 |
| SSE 断连 | 自动重试 1 次，仍失败则显示错误提示 |

### 后端

| 场景 | 处理 |
|------|------|
| 会话不存在 | 404 |
| 访问他人会话 | 403 |
| 删除最后一个 admin | 400 |
| 禁用自己 | 400 |

## 分阶段交付计划

### 第一阶段（前端登录 + 用户管理）

1. 前端：安装 Element Plus + Vue Router，配置基础架构
2. 前端：实现登录页 + 认证状态管理 + axios 拦截器
3. 前端：实现 MainLayout 布局
4. 后端：新增启用/禁用、删除用户 API
5. 前端：实现用户管理页面
6. 集成测试

### 第二阶段（Agent 体验增强）

1. 后端：新增 Conversation/Message 数据模型 + API
2. 前端：AgentChat 接入对话历史
3. 后端：实现 SSE 流式响应端点
4. 前端：接入 SSE 流式渲染
5. 后端：新增 generate_chart 工具 + prompt 改造
6. 前端：ECharts 图表渲染
7. 前端：CSV 导出功能
8. 集成测试
