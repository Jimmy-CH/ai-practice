# P0: Agent 智能增强 — 多轮上下文 + 表格展示 + 追问建议

## 概述

为 Data Analysis Agent 增加三项核心智能增强：多轮对话上下文记忆、查询结果结构化表格展示、智能追问建议生成。

## 功能 A：多轮对话上下文

### 目标

Agent 能理解追问（如"再详细看看第二个品类"），基于之前的对话上下文生成更精准的回答。

### 方案

- 全量拼接最近 5 轮问答历史到 ReAct prompt
- 前端自动从当前会话消息中提取历史

### 接口变更

`POST /api/agent/query` 请求体新增 `history` 字段：

```json
{
  "question": "再详细看看第二个品类",
  "history": [
    {"role": "user", "content": "各品类销售额是多少"},
    {"role": "agent", "content": "各品类销售额如下：电子产品..."}
  ]
}
```

### Prompt 改造

在 `REACT_PROMPT_TEMPLATE` 中新增 `{history}` 占位符，注入格式：

```
以下是之前的对话历史，你可以参考上下文来理解用户的追问：
用户: 各品类销售额是多少
助手: 各品类销售额如下：电子产品...
---
当前问题: 再详细看看第二个品类
```

如果 history 为空，则只显示当前问题。

### 后端实现

- `run_agent(question, history)` 接收 history 参数
- 将 history 格式化为文本注入 prompt
- `stream_agent` 同步改造

### 前端实现

- `useAgentChat.ts` 的 `sendQuestion` 自动从 messages 中提取最近 5 轮 user/agent 对
- 作为 history 字段传给后端

---

## 功能 B：查询结果结构化表格展示

### 目标

Agent 返回的 Observation 中包含表格数据时，自动渲染为可交互的 el-table。

### 方案

- 复用已有的 `parseObservationTable` 函数
- 在 AgentChat.vue 中，对每条 agent 消息尝试解析表格
- 如果解析成功，在 answer 上方渲染 el-table（支持排序）
- 保留导出 CSV 按钮

### 布局

```
思考过程 (可折叠)
─────────────────
┌────────┬──────┬──────┐
│category│ sum  │count │  ← el-table
│电子    │156271│ 120  │
│服装    │ 98450│  85  │
└────────┴──────┴──────┘
[📥 导出 CSV]
─────────────────
各品类销售总额如下：电子产品...  ← answer
─────────────────
[各品类月度趋势?] [哪个品类增长最快?]  ← 追问建议
```

---

## 功能 C：智能追问建议

### 目标

Agent 回答后，自动生成 2-3 个相关追问建议，降低用户思考成本。

### 方案

- 在 ReAct prompt 末尾指令中要求 Agent 在答案后附带"建议追问"
- 后端从 answer 中解析建议追问，放入 `suggestions` 字段
- 前端渲染为可点击按钮

### Prompt 指令

```
在给出最终答案后，请在答案末尾另起一行，以"建议追问："开头，列出 2-3 个用户可以追问的相关问题，每个问题用"｜"分隔。
例如：建议追问：各品类月度趋势如何？｜哪个品类增长最快？｜Top 5 商品是哪些？
```

### 接口变更

响应新增 `suggestions` 字段：

```json
{
  "answer": "各品类销售总额如下...",
  "suggestions": ["各品类月度趋势如何？", "哪个品类增长最快？"],
  "steps": [...],
  "success": true
}
```

### 后端解析

从 answer 中提取"建议追问："后的内容，按"｜"分割为列表，从 answer 中移除该部分。

### 前端渲染

在回答下方，如果有 suggestions，渲染为可点击的 el-tag 或按钮，点击后直接发送该问题。

---

## 文件变更清单

| 文件 | 变更内容 |
|------|----------|
| `backend/app/agent/prompt.py` | 新增 `{history}` 占位符 + 追问指令 |
| `backend/app/agent/langchain_agent.py` | `run_agent`/`stream_agent` 接收 history + 解析 suggestions |
| `backend/app/schemas/agent.py` | 请求新增 history，响应新增 suggestions |
| `backend/app/api/agent.py` | 传递 history 参数 |
| `frontend/src/api/agent.ts` | 接口新增 history/suggestions 字段 |
| `frontend/src/composables/useAgentChat.ts` | 自动携带 history |
| `frontend/src/components/AgentChat.vue` | 表格渲染 + 追问按钮 |
