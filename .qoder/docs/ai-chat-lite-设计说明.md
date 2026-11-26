# ai-chat-lite 设计说明

## 1. 功能定位

`ai-chat-lite` 是 AI Practice 项目集中的「项目一」：基于 FastAPI + httpx + SSE 的多轮对话流式聊天系统。前端不引入任何重型框架与构建链，纯原生 HTML + CSS + JS；后端用 httpx 直连 OpenAI 兼容接口（默认 DeepSeek），逐行消费上游 SSE 并二次转发给浏览器，实现打字机效果、断点续传、停止生成与多会话持久化。

与已有 `ai-chat` 的区别：`ai-chat` 用 OpenAI SDK + Vue 3；本子项目用 httpx 原生流 + 原生前端，聚焦 SSE 传输层与流任务生命周期本身。

## 2. 范围与非目标

完成项：

- 注册 / 登录 / JWT 鉴权（bcrypt 哈希，24h 有效期）
- 多会话侧边栏：新建、切换、删除、自动标题
- 多轮对话，服务端裁剪上下文（最近 N 条）
- 流式输出、停止生成、断点续传（resume_from）、多标签页同流订阅
- SSE 心跳、上游异常补发 error 事件、终止事件统一
- 原生前端：登录视图、会话列表、消息区、Markdown 渲染、断线重连

非目标：

- 会话重命名、消息编辑 / 重新生成
- 多实例部署、Redis 共享缓冲（本设计显式假定单进程）
- 文件上传、RAG、工具调用
- 前端自动化测试（Playwright 等），仅保留手动联调清单

## 3. 目录结构

```
ai-chat-lite/
├── backend/
│   ├── app/
│   │   ├── api/          # auth / users / conversations / messages / router
│   │   ├── core/         # security(JWT+bcrypt) / sse(事件编码)
│   │   ├── models/       # user / conversation / message
│   │   ├── schemas/      # Pydantic 请求响应
│   │   ├── services/     # llm_client / stream_manager / chat_service / user / conversation
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py       # 装配 + 静态托管 + 启动恢复
│   ├── tests/            # pytest: auth / conversations / llm_client / stream
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── .env.example
│   └── README.md
└── frontend/             # 原生三件套，无构建链
    ├── index.html
    ├── styles.css
    ├── app.js
    └── markdown.js
```

`main.py` 用 `StaticFiles(directory=<repo>/ai-chat-lite/frontend, html=True)` 挂在 `/`，API 路由先注册、静态挂载最后，单端口 8000，同源无 CORS。

## 4. 数据模型

SQLAlchemy 2.0 async + SQLite，连接时启用 `PRAGMA foreign_keys=ON`。

```
users
  id INTEGER PK
  username VARCHAR(32) UNIQUE NOT NULL
  password_hash VARCHAR(128) NOT NULL
  created_at DATETIME NOT NULL

conversations
  id INTEGER PK
  user_id FK users.id ON DELETE CASCADE, INDEX
  title VARCHAR(60) NOT NULL DEFAULT '新对话'
  created_at / updated_at DATETIME NOT NULL

messages
  id INTEGER PK
  conversation_id FK conversations.id ON DELETE CASCADE, INDEX
  role VARCHAR(16)        -- user | assistant
  content TEXT NOT NULL DEFAULT ''
  status VARCHAR(16)      -- streaming | done | stopped | failed
  error TEXT NULL
  created_at / updated_at DATETIME NOT NULL
```

- 时间统一 UTC 存储；API 输出 ISO 字符串，前端转本地时区。
- user 消息创建即 `done`；assistant 消息创建即 `streaming`，由流任务推进终态。
- 标题规则：首条用户消息写入时，若标题仍为 `新对话`，取内容去换行后前 20 字。
- 裁剪不落库，仅在组装上游 prompt 时计算。

## 5. API 契约

统一前缀 `/api`，除注册/登录外均需 `Authorization: Bearer <jwt>`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/register` | `{username,password}` → 201；重名 400 |
| POST | `/auth/login` | → `{access_token, token_type:"bearer"}` |
| GET | `/users/me` | 当前用户 |
| GET | `/conversations` | 按 `updated_at` 倒序，含 `running: bool` |
| POST | `/conversations` | 新建空会话 |
| DELETE | `/conversations/{id}` | 先 cancel 运行中任务，再级联删除；204 |
| GET | `/conversations/{id}/messages` | 历史消息 |
| POST | `/conversations/{id}/messages` | `{content}` → 201 `{user_message, assistant_message}`；同会话运行中返回 409 |
| GET | `/messages/{mid}/stream?resume_from=-1` | SSE 订阅 / 续传 |
| POST | `/messages/{mid}/stop` | 取消生成，幂等 |

安全与边界：

- 所有会话/消息操作按 `user_id` 过滤，越权一律 404。
- `resume_from` 合法区间 `[-1, len(parts)-1]`，越界 400。
- 订阅时无 session 且消息为终态：合成一条 `done` 事件，携带 DB 完整 content。

## 6. 流任务管理（方案 A）

`StreamManager` 为进程内单例，按 assistant message id 索引 `StreamSession`：

```python
class StreamSession:
    message_id: int
    conversation_id: int
    owner_id: int
    status: Literal["streaming", "done", "stopped", "failed"]  # 与 messages.status 同一套词表
    parts: list[str]               # index 即 seq，连续
    error_code / error_message
    waiters: set[asyncio.Event]    # 每个订阅者独立，避免丢唤醒
    task: asyncio.Task | None
    finished_at: float | None
```

生命周期：

1. `start()` 注册 session，`asyncio.create_task(_run)`，强引用保存在 dict。
2. `_run()` 在 `asyncio.timeout(STREAM_TIMEOUT_SECONDS)` 内消费 `llm_client.stream_chat()`，每片 `parts.append` + notify + 节流落库（0.5s 或 20 片）。
3. 终态：正常 `done`；`CancelledError` → `stopped`；`UpstreamError` → `failed` + code；超时 → `failed(timeout)`；其他异常 → `failed(internal)`。
4. `finally` 用独立 `AsyncSession` 强制 flush（含 status/error/updated_at），notify 全部订阅者，10 分钟后清理 session。
5. 订阅者离开只退订，不取消任务；只有显式 `stop()` 才取消。
6. 进程重启：lifespan 启动时把遗留 `streaming` 消息标为 `failed`，`error='服务重启中断'`。
7. 同会话只允许一个运行中任务，API 层返回 409。

> 词表约束：`StreamSession.status` 与 `messages.status` 必须完全同构（运行中就是 `streaming`），因为 `_flush` 会把它直接写库；前端靠 `streaming` 判断刷新后是否重订阅，启动恢复靠它收殓遗留消息。历史上两者用过两套词（`running` vs `streaming`），导致落库 0.5s 后前端认不出「生成中」，刷新后续传失效。

订阅循环：先回放 `parts[cursor+1:]`，终态则发终止事件后退出；否则 `asyncio.wait_for(waiter.wait(), HEARTBEAT_SECONDS)`，超时发送 `: ping` 注释行。

## 7. SSE 线格式

```
event: delta
id: 3
data: {"seq":3,"content":"你"}

event: done
data: {"message_id":7,"status":"done","content":"完整文本"}

event: error
data: {"message_id":7,"status":"failed","code":"upstream_timeout","message":"生成超时"}
```

- 终止事件只有 `done`（status=done|stopped）与 `error`；停止生成走 `done(status=stopped)`。
- `error.code` 枚举：`upstream_http` / `upstream_parse` / `upstream_network` / `timeout` / `internal`。
- 响应头：`text/event-stream`、`Cache-Control: no-cache, no-transform`、`X-Accel-Buffering: no`；不启用 GZipMiddleware。

## 8. 上游调用（httpx）

```python
async with client.stream("POST", f"{base}/chat/completions", json=payload) as resp:
    if resp.status_code != 200:
        raise UpstreamError("upstream_http", (await resp.aread()).decode()[:300])
    async for line in resp.aiter_lines():      # 逐行读取，避免 JSON 截断
        if not line.startswith("data:"): continue
        data = line[5:].strip()
        if data == "[DONE]": return
        yield json.loads(data)["choices"][0]["delta"]["content"]
```

- `aiter_lines()` 保证整行拼接；解析失败抛 `upstream_parse`。
- 网络异常（ConnectError / ReadTimeout / RemoteProtocolError）统一映射 `upstream_network`。
- 客户端在 lifespan 中创建与关闭，测试用 `httpx.MockTransport` 注入。

## 9. 上下文裁剪

```
system 固定提示（.env 可覆盖）
+ 本会话 status in (done, stopped) 的最近 MAX_CONTEXT_MESSAGES=20 条，时间正序
+ 强制包含本次用户消息且位于末尾
```

`failed` 消息剔除；`stopped` 保留。

## 10. 原生前端

- 视图：登录/注册 → 主界面（侧边栏会话列表 + 消息区 + 输入框），单页切换。
- Token 存 `localStorage`；401 清除并回登录视图。
- SSE 解析：`fetch` + `getReader()` + `TextDecoder(stream:true)`，按 `\n\n` 切块，解析 `event:` / `id:` / `data:`，忽略 `:` 注释。
- 打字机：delta 累积到 pending，`requestAnimationFrame` 每帧整体追加；距底 < 80px 才自动滚动。
- Markdown：流式期间纯文本，`done` 后一次性渲染；`markdown.js` 先 `escapeHtml`，支持标题/加粗/行内码/代码块/列表/换行，零外部依赖。
- 断线重连：reader 异常或 60s 无数据 → 1s/2s/4s 退避，最多 3 次，带 `resume_from=lastSeq`。
- 停止：先 `POST /stop` 再 abort reader。
- 切回运行中会话：status=streaming 的气泡清空后从 `resume_from=-1` 重订阅，以服务端 buffer 为权威；终态消息以 DB 为准。

## 11. 错误处理与不变量

- 所有上游异常在任务内捕获并转成 error 事件，绝不让异常泄漏导致白屏。
- 终止事件必达：任务 finally 会 notify，订阅者必收到 done/error。
- 消息内容来源唯一：运行中来自 buffer，终态来自 DB。
- 同一会话最多一个运行中 assistant 消息。
- 越权一律 404；JWT 失效 401。

## 12. 测试策略

pytest + pytest-asyncio + `httpx.ASGITransport` + `httpx.MockTransport`：

| 文件 | 覆盖 |
| --- | --- |
| `test_auth.py` | 注册/重名/登录/错密码/无 Token/bcrypt 截断 |
| `test_conversations.py` | 新建、倒序、自动标题、级联删除、越权 404、删除运行中会话 |
| `test_llm_client.py` | 跨块 JSON 行拼接、[DONE]、非 200、解析失败、网络异常映射 |
| `test_stream.py` | 正常流落库、error 事件、中途断流、断点续传、停止、越界 400、终态合成 done、启动恢复、并发 409、裁剪 payload |

前端不写自动化用例，README 提供手动联调清单。

## 13. 配置与依赖

```ini
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
SECRET_KEY=change-me
DATABASE_URL=sqlite+aiosqlite:///<backend 绝对路径>/lite.db
MAX_CONTEXT_MESSAGES=20
STREAM_TIMEOUT_SECONDS=120
HEARTBEAT_SECONDS=15
FLUSH_INTERVAL_SECONDS=0.5
SYSTEM_PROMPT=你是一个乐于助人的中文助手。
```

依赖：fastapi、uvicorn[standard]、httpx、sqlalchemy[asyncio]、aiosqlite、python-jose[cryptography]、passlib[bcrypt]、bcrypt==4.0.1（必须钉 4.x，passlib 1.7.4 与 bcrypt 5.x 不兼容）、python-dotenv、pytest、pytest-asyncio。
