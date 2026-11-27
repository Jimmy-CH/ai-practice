# ai-stream-demo 实现说明

> 本文是实现层面的说明，面向维护者与学习者。需求与取舍见 [设计说明](./ai-stream-demo-设计说明.md)，任务拆分见 [实施计划](./ai-stream-demo-实施计划.md)。
> 文中不包含任何密钥；`DEEPSEEK_API_KEY` 只通过 `.env` 注入，且 `.env` 不入库。

## 1. 功能定位

`ai-stream-demo` 把 DeepSeek（OpenAI 兼容）的流式能力封装成一根「水龙头」：浏览器发一个问题，后端用 FastAPI 的 `StreamingResponse` 配合异步生成器逐 token 推送标准 SSE，末尾在 `finally` 补 `data: [DONE]`。

它解决的问题与学习重点：

- `StreamingResponse` + `async def` 生成器 `yield` 的推送机制
- OpenAI SDK `chat.completions.create(stream=True)` 的逐块消费
- HTTP 分块传输（`Transfer-Encoding: chunked`、无 `Content-Length`）
- 跨源流式请求的 CORS 预检
- `finally` 保证终止哨兵 `[DONE]` 必达
- 「攒包 / 不结束 / 白屏 / 乱码」等常见坑位的规避

非目标：多轮持久化、认证、断点续传、停止生成、后台流任务、前端框架与构建链。

## 2. 代码地图

```
ai-stream-demo/
├── backend/
│   ├── main.py            # 单文件应用：配置 + CORS + SSE 编码 + 两个接口
│   ├── requirements.txt   # fastapi / uvicorn / openai / dotenv / pytest / httpx
│   ├── pytest.ini         # asyncio auto、testpaths、pythonpath
│   ├── .env.example       # 环境变量模板（不含真实 Key）
│   ├── tests/test_stream.py
│   └── README.md          # 更偏使用者的启动与验证说明
└── frontend/
    └── index.html         # 原生 fetch + ReadableStream 消费
```

### 2.1 `backend/main.py` 符号职责

| 符号 | 职责 |
| --- | --- |
| `load_dotenv()` | 进程启动时加载同目录 `.env` |
| `DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL` | 上游模型配置，Key 为空时流接口直接拒绝 |
| `ALLOWED_ORIGINS` | 逗号分隔的允许来源，默认 `localhost:5500` 与 `127.0.0.1:5500` |
| `app` | FastAPI 实例 |
| `CORSMiddleware` | 允许预检与实际请求；来源精确匹配，不使用通配符 |
| `SSE_HEADERS` | `Cache-Control: no-cache, no-transform`、`X-Accel-Buffering: no` |
| `ChatMessage / ChatRequest` | 请求体校验：`role ∈ {system,user,assistant}`，`content: str`，可选 `model` |
| `sse_pack(data)` | 统一编码为 `data: <data>\n\n` |
| `sse_delta(content)` | 编码 OpenAI 形态的 token 事件 |
| `sse_error(exc)` | 编码 `{"error": {...}}`，消息截断 300 字符 |
| `get_client()` | 构造 `AsyncOpenAI`；**测试的 monkeypatch 注入点** |
| `health()` | `GET /api/health`，返回模型名与 `key_configured` |
| `stream_chat(request)` | `POST /api/stream`：流前校验 → 构造客户端 → 返回 `StreamingResponse` |
| `event_generator()` | 内部异步生成器：消费上游、逐块 `yield`、异常收敛、`finally` 补 `[DONE]` |

### 2.2 `backend/tests/test_stream.py`

- 假客户端 `FakeStream / FakeCompletions / FakeClient` 实现 `async for` 协议，不触网。
- `client` 为 async fixture：`httpx.ASGITransport(app=main.app)`，在进程内调用 ASGI。
- 5 个用例：健康检查、CORS 预检、正常流、上游异常仍发 `[DONE]`、缺 Key 返回 JSON。

### 2.3 `frontend/index.html`

单页原生实现：`fetch` → `response.body.getReader()` → `TextDecoder(stream: true)` → 按 `\n\n` 切事件块 → 解析 `data:` → `[DONE]` 结束 / `error` 提示；`AbortController` 支持重新发起时取消上一条流。

## 3. 数据链路

```
浏览器 http://localhost:5500
   │  ① 预检 OPTIONS /api/stream（带 Origin 与 Access-Control-Request-Method）
   ▼
FastAPI :8000  CORSMiddleware → 200 + Access-Control-Allow-Origin
   │  ② POST /api/stream  {"messages":[...]}
   │     流前校验：Key 缺失 → 500 JSON；messages 为空 → 400 JSON
   │     校验通过才创建 StreamingResponse（此时才进入 200 流）
   ▼
event_generator()
   │  ③ await client.chat.completions.create(..., stream=True)
   │  ④ async for chunk: delta = chunk.choices[0].delta.content
   │       非空 → yield "data: {choices:[{delta:{content}}]}\n\n"
   │  ⑤ 异常：yield "data: {\"error\":{...}}\n\n"
   │  ⑥ finally：yield "data: [DONE]\n\n"（客户端已断开则跳过）
   ▼
浏览器 ReadableStream
   │  ⑦ 逐块解码、切事件、累加文本、切换状态
   ▼
页面状态：空闲 → 连接中… → 生成中… → 完成 / 出错 / 已取消
```

关键顺序：**校验必须在返回 `StreamingResponse` 之前**。一旦响应以 200 开始，就无法再把状态码改成 400/500。

## 4. 数据契约（请求体与线格式）

项目无数据库、无持久化；唯一的数据契约是 HTTP 请求体与 SSE 线格式。

### 4.1 请求

```http
POST /api/stream
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "用一句话问候我"}
  ],
  "model": null
}
```

- `messages` 为必填数组；为空返回 `400 {"detail":"messages 不能为空"}`。
- `role` 仅允许 `system / user / assistant`；结构非法由 FastAPI 返回 `422`。
- `model` 可省略，省略时用 `DEEPSEEK_MODEL`。

### 4.2 响应头

| 头 | 值 | 说明 |
| --- | --- | --- |
| `Content-Type` | `text/event-stream; charset=utf-8` | SSE |
| `Cache-Control` | `no-cache, no-transform` | 禁止缓存与转换 |
| `X-Accel-Buffering` | `no` | 关闭 Nginx 类代理缓冲 |
| `Transfer-Encoding` | `chunked` | 由 ASGI 服务器产生 |
| `Content-Length` | 不存在 | 不预知总长度 |

### 4.3 SSE 事件

正常 token：

```
data: {"choices": [{"delta": {"content": "今天"}}]}

data: {"choices": [{"delta": {"content": "也要"}}]}

data: [DONE]

```

流内错误：

```
data: {"error": {"type": "upstream_error", "message": "RuntimeError: ..."}}

data: [DONE]

```

- 每个事件以空行（`\n\n`）结束。
- `[DONE]` 是字面量，不是 JSON。
- 错误 `message` 截断到 300 字符，避免回显上游完整报错或敏感信息。

### 4.4 健康检查

```http
GET /api/health
→ 200 {"status":"ok","model":"deepseek-chat","key_configured":true}
```

## 5. 口径与不变量

1. **校验先于流**：Key 与请求体校验都在 `StreamingResponse` 创建前完成。
2. **哨兵必达**：只要对端仍连接，最后一条事件一定是 `data: [DONE]`；正常结束与上游异常都走同一 `finally`。
3. **空块跳过**：`chunk.choices` 为空或 `delta.content` 为空的 chunk 不产生事件。
4. **异常收敛**：流开始后的任何 `Exception` 都转成 `error` 事件，绝不把堆栈直接抛给客户端。
5. **取消不吞**：`CancelledError / GeneratorExit` 一律 `raise`；通过 `client_gone` 标记避免在已关闭的生成器中再 `yield [DONE]`（否则会触发 `RuntimeError: async generator ignored GeneratorExit`）。
6. **不攒包**：不启用 `GZipMiddleware`、不设置 `Content-Length`，保证逐字到达。
7. **CORS 精确**：`allow_origins` 来自 `ALLOWED_ORIGINS`，不使用 `["*"]` 与 `allow_credentials=True` 的组合。
8. **无状态**：一次请求对应一个生成器，无会话、无落库、无后台任务；进程重启不保留任何流。

## 6. 接口与调度

### 6.1 接口一览

| 方法 | 路径 | 成功 | 失败 |
| --- | --- | --- | --- |
| GET | `/api/health` | `200` JSON | — |
| POST | `/api/stream` | `200` SSE 流 | `500` 缺 Key / `400` 空 messages / `422` 结构非法（均为普通 JSON） |

### 6.2 调度模型

- 无任务队列、无调度器、无后台协程。
- 生命周期完全由 `StreamingResponse` 驱动：响应开始 → 生成器启动；响应结束/客户端断开 → 生成器结束或取消。
- 上游客户端由 `get_client()` 在请求内创建；测试通过 `monkeypatch.setattr(main, "get_client", ...)` 替换。

### 6.3 配置与启动

`.env`（由 `.env.example` 复制，切勿入库）：

```ini
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
ALLOWED_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
```

```powershell
# 后端 :8000
cd ai-stream-demo/backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000

# 前端 :5500（另开终端；独立端口才会真实触发 CORS）
cd ai-stream-demo/frontend
python -m http.server 5500
```

## 7. 验证与排障

### 7.1 自动化验证

```powershell
cd ai-stream-demo/backend
.\venv\Scripts\python.exe -m pytest -q
# 5 passed
```

覆盖：健康检查、CORS 预检、正常流顺序与 `[DONE]`、上游异常仍发 `[DONE]`、缺 Key 返回 JSON 500。

### 7.2 真实联调证据（2026-11-27）

使用 httpx 对运行中的服务发起真实流式请求，观测到：

- `status: 200`
- `content-type: text/event-stream; charset=utf-8`
- `transfer-encoding: chunked`
- `content-length: None`
- token 分片按 `0.90s → 1.14s → 1.15s → … → 1.28s` 递增到达
- 末尾 `data: [DONE]`

浏览器访问 `http://localhost:5500`：页面状态 `空闲 → 生成中… → 完成`，输出完整无报错；后端日志同时出现 `OPTIONS /api/stream 200` 与 `POST /api/stream 200`，证明预检与实际请求都走通。

### 7.3 排障表

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| 页面一直「连接中…」 | 后端未启动、端口不符、被 CORS 拦截 | 先 `curl http://127.0.0.1:8000/api/health`；确认 Origin 在 `ALLOWED_ORIGINS` |
| 状态卡「生成中…」不结束 | 漏发 `[DONE]` | 确认 `finally` 分支未被异常绕过 |
| 忽然白屏或无提示 | 流内异常被直接抛出 | 用 `error` 事件收敛，不允许 `Exception` 穿透生成器 |
| `422 json_invalid` | 请求体不是合法 JSON（常见于终端引号转义） | 用 `--data-binary @body.json` 或客户端 JSON 序列化 |
| `500 未配置 DEEPSEEK_API_KEY` | `.env` 缺失、位置不对或未重启 | 在 `backend/` 下创建 `.env`，重启 uvicorn（`.env` 仅启动时读取） |
| 预检报 Disallowed CORS origin | 来源不在允许列表 | 在 `.env` 的 `ALLOWED_ORIGINS` 追加该来源并重启 |
| 中文/emoji 乱码 | 前端按字节切 JSON | 必须 `TextDecoder(stream: true)` 且按 `\n\n` 切块 |
| 文字一次全出现（非逐字） | GZip、`Content-Length` 或代理缓冲 | 不启用压缩、不设长度、加 `no-transform` 与 `X-Accel-Buffering: no` |
| 客户端断开后后端报 `RuntimeError` | 在已关闭的生成器中 `yield` | 用 `client_gone` 标记，断开时跳过 `[DONE]` 写入 |

### 7.4 改动时的自检清单

- 新增事件类型时，同步更新前端解析分支与本文「4.3 SSE 事件」。
- 调整错误消息时，保留 300 字符截断，避免泄漏上游细节。
- 改动 CORS 时，先跑 `test_cors_preflight`，再用真实预检验证。
- 任何涉及 `finally` 的改动，必须新增一条「异常仍以 `[DONE]` 收尾」的断言。
