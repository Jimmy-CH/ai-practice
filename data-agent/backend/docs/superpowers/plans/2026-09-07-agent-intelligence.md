# P0: Agent 智能增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 Agent 增加多轮对话上下文、查询结果表格展示、智能追问建议三项能力。

**Architecture:** 后端改造 prompt 模板注入对话历史和追问指令，API 层接收/传递 history 参数，解析 suggestions；前端自动携带历史消息，渲染表格和追问按钮。

**Tech Stack:** LangChain, FastAPI, Vue 3, Element Plus

**设计文档:** `docs/superpowers/specs/2026-09-07-agent-intelligence-design.md`

---

### Task 1: 后端 Prompt 改造 + Schema 更新

**Files:**
- Modify: `backend/app/agent/prompt.py`
- Modify: `backend/app/schemas/agent.py`

- [ ] **Step 1: 修改 prompt.py**

在 `REACT_PROMPT_TEMPLATE` 中：
1. 在 "Question: {input}" 之前插入 `{history}` 占位符
2. 在规则列表末尾追加第 8 条追问指令

将完整文件替换为：

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
1. Action 只能是 sql_query 或 generate_chart
2. Action Input 必须是合法的 SELECT SQL 语句或 generate_chart 参数
3. 只使用 SELECT 语句，不要尝试修改数据
4. 如果 SQL 执行出错，分析错误原因并重试
5. 当用户的问题涉及数据对比、趋势、占比等可视化需求时，在 sql_query 获取数据后，使用 generate_chart 工具生成图表
6. generate_chart 的 Action Input 必须是一个完整的 JSON 字符串，格式如：{{"chart_type": "bar", "title": "标题", "labels": "[\"A\",\"B\"]", "values": "[10,20]"}}
7. generate_chart 的 labels 和 values 字段值必须是 JSON 数组字符串
8. 在给出 Final Answer 后，请在答案末尾另起一行，以"建议追问："开头，列出 2-3 个用户可以追问的相关问题，每个问题用"｜"分隔。例如：建议追问：各品类月度趋势如何？｜哪个品类增长最快？｜Top 5 商品是哪些？

数据库表结构：
- products: id(整数), name(文本), category(文本), price(浮点数), created_at(日期时间)
- orders: id(整数), customer_name(文本), order_date(日期), status(文本)
- order_items: id(整数), order_id(整数,外键→orders.id), product_id(整数,外键→products.id), quantity(整数), unit_price(浮点数)

{history}
开始！

Question: {input}
{agent_scratchpad}"""
```

- [ ] **Step 2: 修改 schemas/agent.py**

新增 `HistoryMessage` 模型，`AgentQueryRequest` 新增 `history` 字段，`AgentQueryResponse` 新增 `suggestions` 字段：

在文件末尾追加：

```python
class HistoryMessage(BaseModel):
    role: str   # "user" | "agent"
    content: str
```

修改 `AgentQueryRequest`：

```python
class AgentQueryRequest(BaseModel):
    question: str
    history: List[HistoryMessage] = []
```

修改 `AgentQueryResponse`：

```python
class AgentQueryResponse(BaseModel):
    answer: str
    steps: List[AgentStepResponse]
    success: bool
    chart_data: Optional[ChartData] = None
    suggestions: List[str] = []
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/agent/prompt.py backend/app/schemas/agent.py
git commit -m "feat: add history context and suggestions to prompt and schemas"
```

---

### Task 2: 后端 Agent 逻辑改造

**Files:**
- Modify: `backend/app/agent/langchain_agent.py`
- Modify: `backend/app/api/agent.py`

- [ ] **Step 1: 修改 langchain_agent.py**

1. 新增 `_format_history` 函数
2. 新增 `_parse_suggestions` 函数
3. `run_agent` 和 `stream_agent` 接收 `history` 参数

在文件顶部 import 区新增：

```python
from typing import List, Dict
```

在 `_build_llm` 函数之后，`_parse_intermediate_steps` 之前，添加：

```python
def _format_history(history: List[Dict[str, str]]) -> str:
    """将对话历史格式化为 prompt 文本。"""
    if not history:
        return ""
    lines = ["以下是之前的对话历史，你可以参考上下文来理解用户的追问："]
    for msg in history[-10:]:  # 最多 10 条（5 轮）
        role = "用户" if msg["role"] == "user" else "助手"
        lines.append(f"{role}: {msg['content'][:200]}")
    lines.append("---")
    return "\n".join(lines)


def _parse_suggestions(answer: str) -> tuple[str, List[str]]:
    """从 answer 中提取追问建议，返回 (清理后的 answer, suggestions)。"""
    suggestions = []
    for marker in ["建议追问：", "建议追问:"]:
        if marker in answer:
            idx = answer.index(marker)
            suggestion_text = answer[idx + len(marker):].strip()
            answer = answer[:idx].strip()
            suggestions = [s.strip() for s in suggestion_text.split("｜") if s.strip()]
            if not suggestions:
                suggestions = [s.strip() for s in suggestion_text.split("|") if s.strip()]
            break
    return answer, suggestions
```

修改 `run_agent` 函数签名和内部逻辑：

```python
async def run_agent(question: str, history: List[Dict[str, str]] = None) -> AgentResult:
    """运行数据分析 Agent。"""
    logger.info(f"Agent 开始处理问题: {question[:100]}{'...' if len(question) > 100 else ''}")
    llm = _build_llm()
    tools = [sql_query, generate_chart]

    prompt = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)
    history_text = _format_history(history or [])

    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        max_iterations=5,
        verbose=True,
        handle_parsing_errors=True,
    )

    try:
        result = await executor.ainvoke({"input": question, "history": history_text})
        steps = _parse_intermediate_steps(result.get("intermediate_steps", []))

        # 检测图表数据
        chart_data = None
        for action, observation in result.get("intermediate_steps", []):
            if hasattr(action, 'tool') and action.tool == 'generate_chart':
                try:
                    chart_data = json.loads(observation)
                except (json.JSONDecodeError, TypeError):
                    pass

        raw_answer = result.get("output", "抱歉，我无法回答这个问题。")
        answer, suggestions = _parse_suggestions(raw_answer)

        if "output" in result:
            steps.append(AgentStep(type="thought", content="已得出最终答案"))

        logger.info(f"Agent 处理完成，共执行 {len(steps)} 个步骤")
        return AgentResult(
            answer=answer,
            steps=steps,
            success=True,
            chart_data=chart_data,
            suggestions=suggestions,
        )
    except Exception as e:
        logger.error(f"Agent 执行出错: {e}", exc_info=True)
        return AgentResult(
            answer=f"Agent 执行出错: {str(e)}",
            steps=[],
            success=False,
        )
```

同步修改 `stream_agent`：

```python
async def stream_agent(question: str, request, history: List[Dict[str, str]] = None):
    """流式运行 Agent，yield SSE 事件。"""
    llm = _build_llm()
    tools = [sql_query, generate_chart]
    prompt = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)
    history_text = _format_history(history or [])
    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent, tools=tools, max_iterations=5,
        verbose=True, handle_parsing_errors=True,
    )

    try:
        async for event in executor.astream_events({"input": question, "history": history_text}, version="v2"):
            if await request.is_disconnected():
                return

            kind = event.get("event", "")
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield f"event: thought\ndata: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = event["data"].get("input", {})
                yield f"event: action\ndata: {json.dumps({'content': tool_name, 'input': str(tool_input)}, ensure_ascii=False)}\n\n"
            elif kind == "on_tool_end":
                output = event["data"].get("output", "")
                yield f"event: observation\ndata: {json.dumps({'content': str(output)}, ensure_ascii=False)}\n\n"

        result = await executor.ainvoke({"input": question, "history": history_text})
        raw_answer = result.get("output", "")
        answer, suggestions = _parse_suggestions(raw_answer)
        yield f"event: answer\ndata: {json.dumps({'content': answer, 'suggestions': suggestions}, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json.dumps({'success': True})}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'content': str(e)})}\n\n"
```

- [ ] **Step 2: 修改 AgentResult 模型**

在 `langchain_agent.py` 的 `AgentResult` 类中新增 `suggestions` 字段：

```python
class AgentResult(BaseModel):
    answer: str
    steps: List[AgentStep]
    success: bool
    chart_data: dict | None = None
    suggestions: List[str] = []
```

- [ ] **Step 3: 修改 api/agent.py**

在 `query` 端点中传递 history：

```python
@router.post("/query", response_model=AgentQueryResponse)
async def query(
    request: AgentQueryRequest,
    _current_user: User = Depends(require_role("admin", "editor")),
):
    result = await run_agent(request.question, [h.dict() for h in request.history])
    return AgentQueryResponse(
        answer=result.answer,
        steps=[AgentStepResponse(type=s.type, content=s.content) for s in result.steps],
        success=result.success,
        chart_data=ChartData(**result.chart_data) if result.chart_data else None,
        suggestions=result.suggestions,
    )
```

在 `query_stream` 端点中传递 history：

```python
@router.post("/query/stream")
async def query_stream(
    request: Request,
    req: AgentQueryRequest,
    _current_user: User = Depends(require_role("admin", "editor")),
):
    return StreamingResponse(
        stream_agent(req.question, request, [h.dict() for h in req.history]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/agent/langchain_agent.py backend/app/api/agent.py
git commit -m "feat: add multi-turn context and suggestion parsing to agent"
```

---

### Task 3: 前端集成

**Files:**
- Modify: `frontend/src/api/agent.ts`
- Modify: `frontend/src/composables/useAgentChat.ts`
- Modify: `frontend/src/components/AgentChat.vue`

- [ ] **Step 1: 修改 api/agent.ts**

新增 `HistoryMessage` 接口，修改请求和响应：

```typescript
export interface HistoryMessage {
  role: 'user' | 'agent'
  content: string
}

export interface AgentQueryResponse {
  answer: string
  steps: AgentStep[]
  success: boolean
  suggestions?: string[]
}

export async function queryAgent(question: string, history: HistoryMessage[] = []): Promise<AgentQueryResponse> {
  const { data } = await api.post<AgentQueryResponse>('/agent/query', { question, history })
  return data
}
```

- [ ] **Step 2: 修改 useAgentChat.ts**

在 `sendQuestion` 中自动提取最近 5 轮历史：

```typescript
async function sendQuestion(question: string) {
  if (!currentConvId.value) {
    const conv = await createConversation(question.slice(0, 20))
    conversations.value.unshift(conv)
    currentConvId.value = conv.id
  }

  // 提取最近 5 轮对话历史
  const historyMsgs: HistoryMessage[] = []
  const nonLoadingMsgs = messages.value.filter(m => !m.loading)
  const recentPairs = nonLoadingMsgs.slice(-10)  // 最多 10 条 = 5 轮
  for (const m of recentPairs) {
    historyMsgs.push({ role: m.role, content: m.content })
  }

  messages.value.push({ role: 'user', content: question })
  const agentMsg: ChatMessage = { role: 'agent', content: '', loading: true }
  messages.value.push(agentMsg)
  isLoading.value = true

  try {
    const result = await queryAgent(question, historyMsgs)
    const idx = messages.value.length - 1
    messages.value[idx] = {
      role: 'agent',
      content: result.answer,
      steps: result.steps,
      loading: false,
      chart_data: (result as any).chart_data,
      suggestions: result.suggestions || [],
    }

    await saveMessage(currentConvId.value, 'user', question)
    await saveMessage(currentConvId.value, 'agent', result.answer, result.steps)
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
```

同时更新 `ChatMessage` 接口：

```typescript
export interface ChatMessage {
  role: 'user' | 'agent'
  content: string
  steps?: AgentStep[]
  loading?: boolean
  chart_data?: any
  suggestions?: string[]
}
```

- [ ] **Step 3: 修改 AgentChat.vue**

在 `<script setup>` 中新增导入：

```typescript
import { parseObservationTable } from '../utils/export'
```

（已有此导入，只需确保 `exportToCSV` 和 `parseObservationTable` 都导入了）

在 `<template>` 的 agent 消息渲染区域，做两处修改：

1. 在 `<div class="answer">` 之前，插入表格渲染区域：

```html
<div v-if="getObservationTable(msg)" style="margin: 8px 0;">
  <el-table :data="getObservationTableData(msg)" border size="small"
    style="width: 100%; margin-bottom: 8px;">
    <el-table-column v-for="col in getObservationHeaders(msg)" :key="col"
      :prop="col" :label="col" sortable min-width="120" />
  </el-table>
</div>
```

2. 在 `<div class="answer">` 之后、图表之前，插入追问建议区域：

```html
<div v-if="msg.suggestions && msg.suggestions.length" style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
  <el-button v-for="s in msg.suggestions" :key="s" size="small" round
    @click="handleQuick(s)" :disabled="isLoading">
    {{ s }}
  </el-button>
</div>
```

在 `<script setup>` 中添加辅助函数：

```typescript
function getObservationTable(msg: any): boolean {
  return parseObservationTable(msg.steps || []) !== null
}

function getObservationHeaders(msg: any): string[] {
  const table = parseObservationTable(msg.steps || [])
  return table ? table[0] : []
}

function getObservationTableData(msg: any): Record<string, string>[] {
  const table = parseObservationTable(msg.steps || [])
  if (!table || table.length < 2) return []
  const headers = table[0]
  return table.slice(1).map(row => {
    const obj: Record<string, string> = {}
    headers.forEach((h, i) => { obj[h] = row[i] || '' })
    return obj
  })
}
```

- [ ] **Step 4: 验证**

启动前后端，进行以下测试：
1. 提问"各品类销售额是多少" → 应看到表格 + 追问建议按钮
2. 点击追问建议中的某个问题 → 应能追问并得到基于上下文的回答
3. 确认表格支持排序

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/agent.ts frontend/src/composables/useAgentChat.ts
git add frontend/src/components/AgentChat.vue
git commit -m "feat: add multi-turn context, table display, and suggestion buttons"
```
