# ai-stream-demo 设计说明

## 1. 功能定位

`ai-stream-demo` 是 AI Practice 项目集中的「流式接口封装实践」子项目：把 DeepSeek（OpenAI 兼容）的流式能力封装成一根「水龙头」——浏览器发一个问题，后端用 FastAPI 的 `StreamingResponse` 配合异步生成器逐 token 推送 `data:` 行，末尾在 `finally` 中补 `data: [DONE]` 供前端判定流结束。

本项目的学习目标不是做完整对话产品，而是把 HTTP 分块传输编码（chunked transfer）与流式接口的工程细节看清：

- `StreamingResponse` + `async def` 生成器 `yield` 的推送机制
- OpenAI SDK `stream=True` 的逐块消费
- CORS 预检与跨源流式响应
- `finally` 保证终止哨兵 `[DONE]` 必达
- 常见「攒包 / 不结束 / 白屏」坑位的成因与规避

与 `ai-chat-lite` 的区别：`ai-chat-lite` 用 httpx 手工消费 SSE、带认证与多会话持久化；本项目用 **OpenAI SDK** 封装上游，聚焦单轮请求的传输层与错误收敛，代码保持单文件教学形态。

## 2. 范围与非目标

完成项：

- 后端单文件 `main.py`：配置读取、CORS、`POST /api/stream`、`GET /api/health`
- OpenAI SDK 流式调用，逐 token 转发为标准 OpenAI SSE 线格式
- `finally` 无条件补 `data: [DONE]`，正常结束 / 上游异常均能善终
- 流开始前校验 API Key 与请求体，错误走普通 JSON（非流）
- 最小原生前端：`fetch` + `ReadableStream` 逐块解析、打字机渲染、错误提示
- 精简 pytest：正常流、异常收敛、未配置 Key、CORS 预检

非目标：

- 多轮会话持久化、认证、历史记录
- 断点续传、停止生成、后台流任务
- 前端框架 / 构建链 / Markdown 渲染
- 工具调用、RAG、多模型路由

## 3. 目录结构

```
ai-stream-demo/
├── backend/
│   ├── main.py            # 单文件：配置 + CORS + /api/stream + /api/health
│   ├── requirements.txt   # fastapi / uvicorn / openai / pytest / pytest-asyncio / httpx
│   ├── pytest.ini
│   ├── .env.example
│   ├── tests/
│   │   └── test_stream.py
│   └── README.md          # 启动、curl 验证、坑位清单
└── frontend/
    └── index.html         # 原生 fetch + ReadableStream 消费
```

前端**独立**跑在 `:5500`（`python -m http.server 5500`），后端 `:8000` 只提供接口。两者跨源，`POST` 携带 `Content-Type: application/json` 会触发预检 `OPTIONS`，CORS 配置因此有真实的验证场景，而不是同源托管下的摆设。

## 4. 关键技术决策

| 决策 | 选择 | 被否决方案与理由 |
| --- | --- | --- |
| 线格式 | 复刻 OpenAI SSE：`data: {"choices":[{"delta":{"content":...}}]}`，末尾 `data: [DONE]` | 纯文本流（哨兵易与正文冲突、协议不通用）；原始字节透传（`finally` 插 `[DONE]` 语义冲突、错误无法收敛） |
| 上游消费 | OpenAI SDK `AsyncOpenAI(...).chat.completions.create(stream=True)` + `async for chunk` | httpx 直连（本项目要练 SDK 封装） |
| 前端形态 | 原生 HTML，独立端口 5500 | 后端静态托管（同源后 CORS 失去意义） |
| 收尾 | `try/finally` 中 `yield "[DONE]"` | 只在正常分支发送（异常时前端永远等不到结束） |

## 5. 数据链路

```
浏览器 :5500
  │  POST /api/stream  {messages:[...]}   (跨源，先 OPTIONS 预检)
  ▼
FastAPI :8000
  │  1. 校验 API Key / 请求体  ── 失败 → 普通 JSON 4xx/5xx（不进入流）
  │  2. 构造 AsyncOpenAI(base_url, api_key)
  │  3. 返回 StreamingResponse(event_generator(), text/event-stream)
  ▼
event_generator()
  │  try:
  │    stream = await client.chat.completions.create(model, messages, stream=True)
  │    async for chunk in stream:
  │        delta = chunk.choices[0].delta.content
  │        if delta: yield sse_pack(delta)          # data: {...}\n\n
  │  except asyncio.CancelledError:
  │    raise                                       # 客户端断开：只清理，不吞
  │  except Exception as exc:
  │    yield sse_error(exc)                        # data: {"error": {...}}
  │  finally:
  │    yield "data: [DONE]\n\n"                     # 终止哨兵必达
  ▼
浏览器 ReadableStream
  │  getReader() → TextDecoder → 按 \n\n 切块 → 解析 data:
  │  delta.textContent += content；[DONE] → 结束态；error → 提示
```

## 6. 线格式契约

响应头：

- `Content-Type: text/event-stream; charset=utf-8`
- `Cache-Control: no-cache, no-transform`
- `X-Accel-Buffering: no`
- 不设置 `Content-Length`，由 ASGI 服务器按 chunked 输出
- 不启用 `GZipMiddleware`

正常事件（每个 token 一条）：

```
data: {"choices":[{"delta":{"content":"你"}}]}

data: {"choices":[{"delta":{"content":"好"}}]}

data: [DONE]

```

错误事件（流已开始后）：

```
data: {"error":{"type":"upstream_error","message":"HTTP 401: ..."}}

data: [DONE]

```

不变量：

1. 只要对端仍连接，流的最后一条事件必为 `data: [DONE]`；客户端主动断开时对端已消失，不再尝试写入（也无法送达）。
2. 每个 `data:` 行都是单行 JSON 或字面量 `[DONE]`，块之间以空行分隔。
3. `delta.content` 为空/缺失的 chunk 直接跳过，不产出空事件。

## 7. 坑位清单（避坑实践核心）

| 坑 | 现象 | 正确做法 |
| --- | --- | --- |
| `finally` 不发 `[DONE]` | 前端 reader 永远等结尾，卡「生成中」 | `try/finally` 无条件 `yield "[DONE]"` |
| 启用 GZip / 设置 `Content-Length` | 服务端攒包，失去逐字；或响应头冲突报错 | 不压缩、不设长度，靠 chunked；加 `no-transform` 与 `X-Accel-Buffering: no` |
| 吞掉 `CancelledError` | 客户端断开后上游继续生成、计费不止 | 捕获后 `raise`，仅在 `finally` 做清理；同时标记对端已走，避免在已关闭的生成器里再 `yield [DONE]` 触发 `RuntimeError` |
| 上游异常抛出生成器 | 流已开始无法改状态码，前端收到半截或崩溃 | 流内收敛成 `error` 事件，再发 `[DONE]` |
| 流开始后才校验 Key | 配置错误也以 200 流返回，前端难判断 | 创建 `StreamingResponse` **之前**校验，错误走普通 `HTTPException` |
| `allow_origins="*"` + `allow_credentials=True` | 浏览器拒绝或预检行为异常 | 精确列 `localhost:5500` / `127.0.0.1:5500`，不混用凭证 |
| 前端只读一次 `response.text()` | 失去流式效果 | 必须 `response.body.getReader()` 逐块读取 |
| 前端按字节切 JSON | 多字节字符被截断出现乱码 | `TextDecoder(stream: true)` + 按 `\n\n` 事件块拼接 |

## 8. 异常收敛与不变量

- 流开始前的错误（缺 Key、请求体非法、上游首个请求即失败无法预判）→ 普通 JSON 响应。
- 流开始后的错误 → `data: {"error": {type, message}}`，随后 `[DONE]`。
- `error.type` 枚举：`upstream_error`（HTTP/网络/解析）、`internal`（其他未预期异常）。
- 错误消息截断到 300 字符，避免把上游完整报错或密钥信息回显。
- 客户端断开（`CancelledError` / `GeneratorExit`）不产出错误事件，直接结束。

## 9. 前端消费要点

- `fetch` 使用 `POST` + `Content-Type: application/json`，读取 `response.body.getReader()`。
- `TextDecoder("utf-8")` 以 `{stream: true}` 模式解码，避免多字节截断。
- 缓冲区按 `\n\n` 切分事件块，逐块解析 `data:` 行；`[DONE]` 结束，`error` 显示提示。
- 渲染：把 `delta.content` 追加到输出区；每块 `requestAnimationFrame` 合并，避免高频重排。
- 再次发送前 `AbortController.abort()` 取消上一条流，并清空输出区。
- 顶部展示状态：连接中 / 生成中 / 完成 / 出错。

## 10. 测试策略

pytest + pytest-asyncio + `httpx.ASGITransport`，用依赖注入替换 OpenAI 客户端，不触网：

| 用例 | 覆盖 |
| --- | --- |
| `test_stream_happy_path` | 多个 delta 顺序产出、`content-type` 为 `text/event-stream`、末尾 `data: [DONE]` |
| `test_stream_upstream_error` | 上游抛异常时先有 `error` 事件，仍有 `[DONE]` 收尾 |
| `test_stream_missing_api_key` | 未配置 Key 返回非流式 500 JSON，响应体不是 `text/event-stream` |
| `test_cors_preflight` | `OPTIONS` 携带 `Origin` / `Access-Control-Request-Method` 返回 200，回显 `Access-Control-Allow-Origin` |

手动联调：

- `curl -N -X POST ...` 观察逐行到达；
- 浏览器 `:5500` 页面观察打字机与状态切换；
- DevTools Network 中该请求 `Transfer-Encoding: chunked`、无 `Content-Length`。

## 11. 配置与依赖

`.env.example`：

```ini
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
ALLOWED_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
```

依赖：`fastapi`、`uvicorn[standard]`、`openai`、`python-dotenv`、`pytest`、`pytest-asyncio`、`httpx`。

## 12. 运行与验证

```powershell
# 后端
cd ai-stream-demo/backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# 复制 .env.example 为 .env 并填入 DEEPSEEK_API_KEY
python -m uvicorn main:app --reload --port 8000

# 前端（另开一个终端）
cd ai-stream-demo/frontend
python -m http.server 5500
# 打开 http://localhost:5500
```

成功标准：

1. 页面输入问题后逐字出现，状态为「生成中 → 完成」。
2. 网络面板该请求为 chunked、无 `Content-Length`。
3. 篡改 Key 后发送，页面显示错误提示而非白屏。
4. pytest 四项全绿。
