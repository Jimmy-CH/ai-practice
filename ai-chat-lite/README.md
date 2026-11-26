# ai-chat-lite

> 不依赖任何前端框架的多轮流式对话系统：后端用 `httpx` 逐行消费上游 SSE，前端用原生 HTML/JS 手写 SSE 解析与打字机渲染，单端口同源部署。

- 对齐的实战要点：`async with client.stream(...)` + `aiter_lines()` 逐行读取（不整包 `json.loads`，避免 JSON 截断）；`media_type="text/event-stream"` + `Cache-Control: no-cache, no-transform` + `X-Accel-Buffering: no` 保证不被缓冲；异常统一收敛在异步生成器内部，主动补发 `error` 事件，前端不会白屏。
- 相比直接「请求即转发」的写法，这里把上游消费放进后台 `asyncio.Task`，`/stream` 只负责订阅，于是天然支持**断线不断生成**、**断点续传**、**停止生成**。

## 目录结构

```
ai-chat-lite/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 装配 + 生命周期 + 静态托管
│   │   ├── config.py            # 环境变量
│   │   ├── database.py          # SQLAlchemy 2.0 async + NullPool + 外键开关
│   │   ├── core/
│   │   │   ├── security.py      # bcrypt（72 字节截断）+ JWT + get_current_user
│   │   │   └── sse.py           # SSE 响应头与事件编码
│   │   ├── models/              # users / conversations / messages
│   │   ├── schemas/             # 请求响应模型
│   │   ├── services/
│   │   │   ├── llm_client.py    # httpx 流式调用 OpenAI 兼容上游
│   │   │   ├── stream_manager.py# 后台流任务、缓冲、订阅、停止、续传
│   │   │   ├── chat_service.py  # 提示词拼装、上下文裁剪、落库
│   │   │   ├── conversation_service.py
│   │   │   └── user_service.py
│   │   └── api/                 # auth / users / conversations / messages
│   └── tests/                   # pytest（认证、会话、httpx 解析、流任务、SSE 接口）
└── frontend/
    ├── index.html               # 登录 + 侧边栏 + 消息区 + 输入区
    ├── styles.css
    ├── markdown.js              # 先转义再排版的轻量 Markdown
    └── app.js                   # fetch + ReadableStream 解析 SSE、打字机、重连、停止
```

## 快速开始

```powershell
cd ai-chat-lite/backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env
# 编辑 .env，至少填写 DEEPSEEK_API_KEY 和 SECRET_KEY
uvicorn app.main:app --port 8000
```

浏览器打开 http://127.0.0.1:8000 ，先注册账号，再新建对话。前端由 FastAPI `StaticFiles` 同源托管，不需要 npm，也没有构建步骤。

## 配置项（`backend/.env`）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | 空 | 上游 API Key；为空时调用会返回 `upstream_http` 错误事件 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容上游地址，可指向自建网关 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名 |
| `SECRET_KEY` | `change-me` | JWT 签名密钥，部署必须修改 |
| `DATABASE_URL` | `sqlite+aiosqlite:///<backend>/lite.db` | 默认固定到 backend 目录，不受启动目录影响 |
| `MAX_CONTEXT_MESSAGES` | `20` | 上下文裁剪条数（只取最近 N 条 `done` / `stopped` 消息） |
| `STREAM_TIMEOUT_SECONDS` | `120` | 单次生成的总超时 |
| `HEARTBEAT_SECONDS` | `15` | SSE 心跳 `: ping` 间隔 |
| `FLUSH_INTERVAL_SECONDS` | `0.5` | 增量落库节流间隔 |
| `SYSTEM_PROMPT` | 中文助手提示词 | 系统提示词 |

## API

所有业务接口都在 `/api` 下，除注册/登录外都需要 `Authorization: Bearer <token>`。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/auth/register` | 注册，返回用户信息 |
| POST | `/api/auth/login` | 登录，返回 `access_token` |
| GET | `/api/users/me` | 当前用户 |
| GET | `/api/conversations` | 会话列表（`running` 标记是否有生成中的消息） |
| POST | `/api/conversations` | 新建会话 |
| DELETE | `/api/conversations/{id}` | 删除会话（级联删除消息，并取消运行中的任务） |
| GET | `/api/conversations/{id}/messages` | 消息列表 |
| POST | `/api/conversations/{id}/messages` | 发送消息，返回 `user_message` + `assistant_message`（`status=streaming`）；同会话已有生成中消息时返回 409 |
| GET | `/api/messages/{id}/stream?resume_from=-1` | 订阅 SSE 流；`resume_from` 为「已收到的最后 seq」，只回放更新的片段 |
| POST | `/api/messages/{id}/stop` | 停止生成，部分内容立即落库 |

越权访问一律 404；`resume_from` 超过当前缓冲上界返回 400。

## SSE 协议

```
event: delta
id: 0
data: {"seq":0,"content":"这是"}

event: delta
id: 1
data: {"seq":1,"content":"一个"}

event: done
data: {"message_id":12,"status":"done","content":"这是一个...完整内容"}
```

- `delta` 带 `seq`（从 0 递增）与增量 `content`；前端把 `seq` 存起来，断线重连时作为 `resume_from`。
- 终止事件只有两种：`done`（`status` 为 `done` 或 `stopped`，附完整内容）与 `error`（`code` + `message`）。
- `error.code` 取值：`upstream_http`、`upstream_parse`、`upstream_network`、`timeout`、`internal`。
- 长时间无增量会收到注释行 `: ping`，前端据此刷新看门狗。

## 设计不变量

- **运行中以内存缓冲为权威，终态以数据库为权威**：`done` / `error` 事件一定在最终落库之后才发出。
- **断线只退订，不取消任务**：关页面或网络中断后后台继续生成，重新打开会话会从 `resume_from=-1` 重放全部缓冲内容。
- **只有 `stop` 才取消任务**：取消后状态为 `stopped`，已生成的部分内容保留。
- **会话级串行**：同一会话同一时刻只允许一个生成中的消息（409）。
- 进程重启时，遗留的 `streaming` 消息在启动时被标记为 `failed`（「服务重启中断」），前端不会一直转圈。

## 测试

```powershell
cd ai-chat-lite/backend
.\venv\Scripts\python.exe -m pytest -q
```

覆盖范围：密码哈希与 JWT、会话 CRUD 与越权、`httpx.MockTransport` 驱动的流式解析、流任务状态机（完成 / 停止 / 超时 / 上游异常 / 心跳 / 续传）、SSE 接口行为。

> 说明：`httpx.ASGITransport` 会先缓冲完整响应体，因此「边读流边并发 stop」这类时序断言放在 `tests/test_stream_manager.py` 直接驱动 `subscribe()` 验证；需要真实逐块时序时请用真实 Uvicorn + 假上游。

## 无 Key 联调（假上游）

`backend/scripts/` 内置了假上游与端到端冒烟脚本，不需要真实 API Key 也能验证完整流式链路：

```powershell
cd ai-chat-lite/backend
# 终端 A：假上游
.\venv\Scripts\python.exe -m uvicorn scripts.fake_upstream:app --port 8011

# 终端 B：主服务指向假上游
$env:DEEPSEEK_API_KEY="fake"; $env:DEEPSEEK_BASE_URL="http://127.0.0.1:8011"
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8010

# 终端 C：跑冒烟（默认打 8000，可用 SMOKE_BASE_URL 覆盖）
$env:SMOKE_BASE_URL="http://127.0.0.1:8010"; .\venv\Scripts\python.exe scripts/e2e_stream_smoke.py
```

冒烟覆盖：静态资源、注册登录、完整流式（含逐块时序断言）、断线续传、运行中停止、上游 502 错误链路、会话并发 409、越权 404 与级联删除。

## 已知限制

- 流任务与管理器状态都在进程内存中，只适用于**单进程**部署；多 worker 需要换成 Redis 之类的共享缓冲与广播。
- SQLite 适合本地与演示；并发写入场景请换 PostgreSQL / MySQL（改 `DATABASE_URL` 即可，ORM 层无需改动）。

## 浏览器验证报告（截图路径）

验证环境：`uvicorn app.main:app --port 8000` + `scripts/fake_upstream.py`（`FAKE_DELAY_SECONDS=0.5`、`FAKE_REPEAT=4`，约 24s/条，便于观察停止与断线），真实浏览器手工回归。

截图位于 `docs/screenshots/`，随仓库提交。

| 场景 | 结果 | 截图 |
| --- | --- | --- |
| 登录卡片 / 注册后进入主界面 | 通过 | [01-login.png](docs/screenshots/01-login.png)、[02-app.png](docs/screenshots/02-app.png) |
| 发送消息、打字机逐段输出、「停止」按钮出现 | 通过 | [03-streaming.png](docs/screenshots/03-streaming.png) |
| 自然结束、Markdown（加粗/列表/代码块）渲染 | 通过 | [04-done.png](docs/screenshots/04-done.png) |
| 停止生成：保留部分内容 + 「已停止」+ 按钮复位 | 通过（首轮与修复后各一次） | [05-stopped.png](docs/screenshots/05-stopped.png)、[14-stop-after-fix.png](docs/screenshots/14-stop-after-fix.png) |
| 刷新断点续传 | **首轮失败 → 修复后通过** | 刷新前：[11-before-refresh.png](docs/screenshots/11-before-refresh.png)；失败现象：[06-resume.png](docs/screenshots/06-resume.png)、[07-resume-done.png](docs/screenshots/07-resume-done.png)（命名沿用需求，实为卡住）；再手动刷新才补齐：[09-manual-refresh.png](docs/screenshots/09-manual-refresh.png)；修复后：[12-resume-before-refresh.png](docs/screenshots/12-resume-before-refresh.png)、[13-resume-after-refresh.png](docs/screenshots/13-resume-after-refresh.png)、[13-resume-growth.png](docs/screenshots/13-resume-growth.png)、[13-resume-done.png](docs/screenshots/13-resume-done.png) |
| 控制台 | 无红色报错 | [08-console.png](docs/screenshots/08-console.png)、[13-console-after-fix.png](docs/screenshots/13-console-after-fix.png) |
| 网络请求 | 未见失败请求 | [10-network.png](docs/screenshots/10-network.png) |

### 首轮失败原因与修复

首轮刷新后气泡停在刷新那一刻、也不再出现「生成中…」「停止」，即续传静默失效。根因是 `StreamSession.status` 用了 `"running"` 而消息状态词表是 `"streaming"`，`_flush()` 把前者直接写库，消息创建 0.5s 后 DB 状态变为 `running`，前端“是否重订阅”的判断永不成立（同时 `recover_stale_streaming()` 也收殓不到这类行）。

修复后会话状态与消息状态统一为 `streaming / done / stopped / failed`，并补充：

- 单测 `test_running_message_flushes_streaming_status`：运行中落库必须是 `streaming`（共 37 项单测通过）
- `scripts/e2e_stream_smoke.py` 新增“停止前 DB 状态必须是 streaming”断言
- 接口实测：发送后 1s / 2s / 3s 读取消息均为 `status=streaming`、会话 `running=true`，新订阅从 `seq=0` 完整回放

复现脚本（无真实 Key）：

```powershell
cd ai-chat-lite/backend
$env:FAKE_DELAY_SECONDS="0.5"; $env:FAKE_REPEAT="4"
.\venv\Scripts\python.exe -m uvicorn scripts.fake_upstream:app --port 8011
# 另一个终端
$env:DEEPSEEK_API_KEY="fake"; $env:DEEPSEEK_BASE_URL="http://127.0.0.1:8011"
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```
