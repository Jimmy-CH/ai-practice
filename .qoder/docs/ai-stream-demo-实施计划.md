# ai-stream-demo 实施计划

> **执行方式**：本计划按 TDD 拆分为 7 个任务，逐任务推进。仓库约定：未经用户明确要求不自动 `git commit`，文中的「提交检查点」仅在用户同意时执行。

**目标**：新建子项目 `ai-stream-demo`，用 FastAPI `StreamingResponse` + OpenAI SDK 把 DeepSeek 流式能力封装成标准 SSE「水龙头」，`finally` 必发 `[DONE]`，并配最小原生前端与四项 pytest。

**架构**：后端单文件 `backend/main.py`（配置 + CORS + `/api/health` + `/api/stream` + 异步生成器）；前端 `frontend/index.html` 独立跑在 `:5500`，用 `fetch` + `ReadableStream` 逐块消费 `:8000` 的流。上游客户端通过 `get_client()` 注入点隔离，测试用假客户端，不触网。

**技术栈**：Python 3.11+、FastAPI、uvicorn、openai SDK、python-dotenv、pytest、pytest-asyncio、httpx。

**执行状态（2026-11-27）**：Task 1-7 已实现并完成真实联调。后端 `pytest -q` → `5 passed`；`GET /api/health` → `{"status":"ok","key_configured":true}`；缺 Key 时 `POST /api/stream` → `500 application/json`（非流）；真实流请求 → `200`、`text/event-stream`、`Transfer-Encoding: chunked`、无 `Content-Length`，分片按 0.90s→1.28s 递增到达，末尾 `[DONE]`；浏览器页面状态 `空闲 → 生成中… → 完成`，输出完整无报错。按仓库约定未执行任何 `git commit`。

---

## 文件结构

| 文件 | 职责 |
| --- | --- |
| `ai-stream-demo/backend/main.py` | 单文件应用：读配置、装 CORS、SSE 编码、流式路由、异常收敛 |
| `ai-stream-demo/backend/requirements.txt` | 运行与测试依赖 |
| `ai-stream-demo/backend/pytest.ini` | pytest 配置（asyncio auto、testpaths） |
| `ai-stream-demo/backend/.env.example` | 环境变量模板 |
| `ai-stream-demo/backend/tests/test_stream.py` | 四项契约测试 |
| `ai-stream-demo/backend/README.md` | 启动、curl 验证、坑位清单 |
| `ai-stream-demo/frontend/index.html` | 原生流式消费与打字机渲染 |

---

## Task 1：后端骨架与健康检查

**Files:**
- Create: `ai-stream-demo/backend/requirements.txt`
- Create: `ai-stream-demo/backend/pytest.ini`
- Create: `ai-stream-demo/backend/.env.example`
- Create: `ai-stream-demo/backend/main.py`
- Create: `ai-stream-demo/backend/tests/test_stream.py`

- [ ] **Step 1: 写依赖与配置骨架**

`requirements.txt`：

```text
fastapi>=0.110
uvicorn[standard]>=0.27
openai>=1.30
python-dotenv>=1.0
pytest>=8.0
pytest-asyncio>=0.23
httpx>=0.27
```

`pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

`.env.example`：

```ini
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
ALLOWED_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
```

- [ ] **Step 2: 写失败的测试**

`tests/test_stream.py`：

```python
import httpx
import pytest

import main


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd ai-stream-demo/backend && python -m pytest tests/test_stream.py::test_health -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'main'`）

- [ ] **Step 4: 写最小实现**

`main.py`：

```python
import os

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5500,http://127.0.0.1:5500",
    ).split(",")
    if origin.strip()
]

app = FastAPI(title="AI Stream Demo")


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "model": DEEPSEEK_MODEL,
        "key_configured": bool(DEEPSEEK_API_KEY),
    }
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd ai-stream-demo/backend && python -m pytest tests/test_stream.py::test_health -v`
Expected: PASS

- [ ] **Step 6: 提交检查点（需用户同意）**

```bash
git add ai-stream-demo/backend
git commit -m "feat(ai-stream-demo): scaffold backend and health check"
```

---

## Task 2：CORS 预检

**Files:**
- Modify: `ai-stream-demo/backend/main.py`
- Test: `ai-stream-demo/backend/tests/test_stream.py`

- [ ] **Step 1: 写失败的测试**

在 `tests/test_stream.py` 追加：

```python
async def test_cors_preflight(client):
    resp = await client.options(
        "/api/stream",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5500"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd ai-stream-demo/backend && python -m pytest tests/test_stream.py::test_cors_preflight -v`
Expected: FAIL（404 或缺少 `access-control-allow-origin`）

- [ ] **Step 3: 实现 CORS**

在 `main.py` 的 `app = FastAPI(...)` 之后追加：

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    # 坑位：不要用 allow_origins=["*"] 与 allow_credentials=True 混搭
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

同时把 `from fastapi.middleware.cors import CORSMiddleware` 移到文件顶部导入区。

- [ ] **Step 4: 运行确认通过**

Run: `cd ai-stream-demo/backend && python -m pytest tests/test_stream.py::test_cors_preflight -v`
Expected: PASS

- [ ] **Step 5: 提交检查点（需用户同意）**

```bash
git add ai-stream-demo/backend
git commit -m "feat(ai-stream-demo): enable CORS for frontend origin"
```

---

## Task 3：流式接口正常路径

**Files:**
- Modify: `ai-stream-demo/backend/main.py`
- Test: `ai-stream-demo/backend/tests/test_stream.py`

- [ ] **Step 1: 写假客户端与失败测试**

在 `tests/test_stream.py` 追加：

```python
from types import SimpleNamespace


class FakeStream:
    def __init__(self, contents):
        self._iterator = iter(contents)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            content = next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration
        return SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=content))]
        )


class FakeCompletions:
    def __init__(self, contents=None, error=None):
        self._contents = contents or []
        self._error = error

    async def create(self, **kwargs):
        if self._error is not None:
            raise self._error
        return FakeStream(self._contents)


class FakeClient:
    def __init__(self, contents=None, error=None):
        self.chat = SimpleNamespace(
            completions=FakeCompletions(contents=contents, error=error)
        )


async def test_stream_happy_path(client, monkeypatch):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(main, "get_client", lambda: FakeClient(["你", "好"]))

    resp = await client.post(
        "/api/stream",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert '"你"' in body
    assert '"好"' in body
    assert body.index('"你"') < body.index('"好"')
    assert body.rstrip().endswith("data: [DONE]")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd ai-stream-demo/backend && python -m pytest tests/test_stream.py::test_stream_happy_path -v`
Expected: FAIL（404，`/api/stream` 不存在）

- [ ] **Step 3: 实现 SSE 编码、客户端注入点与流式路由**

在 `main.py` 顶部导入区补充：

```python
import asyncio
import json
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel
```

在 `app` 定义之后追加：

```python
SSE_HEADERS = {
    # 坑位：不设 Content-Length，交给 ASGI 按 chunked 输出；
    # no-transform 与 X-Accel-Buffering 防止代理攒包。
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None


def sse_pack(data: str) -> str:
    return f"data: {data}\n\n"


def sse_delta(content: str) -> str:
    payload = {"choices": [{"delta": {"content": content}}]}
    return sse_pack(json.dumps(payload, ensure_ascii=False))


def get_client() -> AsyncOpenAI:
    # 依赖注入点：测试通过 monkeypatch 替换，避免真实网络调用
    return AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


@app.post("/api/stream")
async def stream_chat(request: ChatRequest) -> StreamingResponse:
    client = get_client()
    messages = [message.model_dump() for message in request.messages]

    async def event_generator() -> AsyncIterator[str]:
        try:
            stream = await client.chat.completions.create(
                model=request.model or DEEPSEEK_MODEL,
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if content:
                    yield sse_delta(content)
        except asyncio.CancelledError:
            # 坑位：客户端断开时取消必须向上抛，不能吞掉
            raise
        finally:
            # 终止哨兵必达：正常结束与上游异常都要补 [DONE]
            yield sse_pack("[DONE]")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
```

- [ ] **Step 4: 运行确认通过**

Run: `cd ai-stream-demo/backend && python -m pytest tests/test_stream.py::test_stream_happy_path -v`
Expected: PASS

- [ ] **Step 5: 提交检查点（需用户同意）**

```bash
git add ai-stream-demo/backend
git commit -m "feat(ai-stream-demo): add OpenAI streaming endpoint"
```

---

## Task 4：上游异常收敛

**Files:**
- Modify: `ai-stream-demo/backend/main.py`
- Test: `ai-stream-demo/backend/tests/test_stream.py`

- [ ] **Step 1: 写失败的测试**

在 `tests/test_stream.py` 追加：

```python
async def test_stream_upstream_error_still_done(client, monkeypatch):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        main,
        "get_client",
        lambda: FakeClient(error=RuntimeError("upstream boom")),
    )

    resp = await client.post(
        "/api/stream",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert resp.status_code == 200
    body = resp.text
    assert '"error"' in body
    assert "upstream boom" in body
    assert body.rstrip().endswith("data: [DONE]")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd ai-stream-demo/backend && python -m pytest tests/test_stream.py::test_stream_upstream_error_still_done -v`
Expected: FAIL（异常直接抛出，响应中断，无 `error` 事件）

- [ ] **Step 3: 实现错误事件**

在 `main.py` 的 `sse_delta` 之后追加：

```python
def sse_error(exc: Exception) -> str:
    # 截断 300 字符，避免上游完整报错或敏感信息回显
    message = f"{type(exc).__name__}: {exc}"[:300]
    payload = {"error": {"type": "upstream_error", "message": message}}
    return sse_pack(json.dumps(payload, ensure_ascii=False))
```

在 `event_generator` 的 `except asyncio.CancelledError` 分支之后补充：

```python
        except Exception as exc:
            # 流已开始无法改状态码：把异常收敛成 error 事件，前端仍能善终
            yield sse_error(exc)
        finally:
            yield sse_pack("[DONE]")
```

（与既有 `finally` 合并，确保只有一个 `finally` 块。）

- [ ] **Step 4: 运行确认通过**

Run: `cd ai-stream-demo/backend && python -m pytest tests/test_stream.py::test_stream_upstream_error_still_done -v`
Expected: PASS

- [ ] **Step 5: 提交检查点（需用户同意）**

```bash
git add ai-stream-demo/backend
git commit -m "feat(ai-stream-demo): converge upstream errors into SSE events"
```

---

## Task 5：流开始前的配置校验

**Files:**
- Modify: `ai-stream-demo/backend/main.py`
- Test: `ai-stream-demo/backend/tests/test_stream.py`

- [ ] **Step 1: 写失败的测试**

在 `tests/test_stream.py` 追加：

```python
async def test_stream_missing_api_key_returns_json(client, monkeypatch):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "")

    resp = await client.post(
        "/api/stream",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert resp.status_code == 500
    assert resp.headers["content-type"].startswith("application/json")
    assert "DEEPSEEK_API_KEY" in resp.json()["detail"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd ai-stream-demo/backend && python -m pytest tests/test_stream.py::test_stream_missing_api_key_returns_json -v`
Expected: FAIL（当前直接进入流，返回 200）

- [ ] **Step 3: 实现流前校验**

在 `stream_chat` 函数体最前面、创建 `client` 之前追加：

```python
    # 坑位：校验必须发生在 StreamingResponse 之前，
    # 否则响应已以 200 开始，无法再返回 500/400
    if not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=500, detail="未配置 DEEPSEEK_API_KEY")
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")
```

- [ ] **Step 4: 运行确认通过**

Run: `cd ai-stream-demo/backend && python -m pytest tests/test_stream.py::test_stream_missing_api_key_returns_json -v`
Expected: PASS

- [ ] **Step 5: 全量测试**

Run: `cd ai-stream-demo/backend && python -m pytest -v`
Expected: 5 passed（health / preflight / happy / upstream error / missing key）

- [ ] **Step 6: 提交检查点（需用户同意）**

```bash
git add ai-stream-demo/backend
git commit -m "feat(ai-stream-demo): validate config before starting stream"
```

---

## Task 6：原生前端流式消费

**Files:**
- Create: `ai-stream-demo/frontend/index.html`

- [ ] **Step 1: 写页面**

`index.html`：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Stream Demo · 流式水龙头</title>
  <style>
    body { margin: 0; font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; }
    main { max-width: 760px; margin: 48px auto; padding: 0 16px; }
    h1 { font-size: 20px; }
    .status { font-size: 13px; color: #94a3b8; margin-bottom: 12px; }
    #output { min-height: 180px; white-space: pre-wrap; line-height: 1.7;
      background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }
    textarea { width: 100%; box-sizing: border-box; margin-top: 12px; height: 88px;
      background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 8px; padding: 12px; }
    button { margin-top: 12px; padding: 10px 20px; border: 0; border-radius: 8px;
      background: #2563eb; color: #fff; cursor: pointer; }
    button:disabled { background: #475569; cursor: not-allowed; }
  </style>
</head>
<body>
<main>
  <h1>流式 AI 接口 · 水龙头演示</h1>
  <div class="status">状态：<span id="status">空闲</span></div>
  <div id="output"></div>
  <textarea id="input">用三句话解释什么是 HTTP 分块传输编码。</textarea>
  <button id="send">开始生成</button>
</main>
<script>
const API = "http://127.0.0.1:8000/api/stream";
const output = document.getElementById("output");
const statusEl = document.getElementById("status");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");

let controller = null;

sendBtn.addEventListener("click", async () => {
  if (controller) controller.abort();
  controller = new AbortController();
  output.textContent = "";
  statusEl.textContent = "连接中…";
  sendBtn.disabled = true;

  try {
    const resp = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: [{ role: "user", content: inputEl.value }] }),
      signal: controller.signal,
    });

    if (!resp.ok) {
      const detail = await resp.json().catch(() => ({}));
      throw new Error(detail.detail || `HTTP ${resp.status}`);
    }

    statusEl.textContent = "生成中…";
    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop();
      for (const block of blocks) {
        const line = block.split("\n").find((l) => l.startsWith("data:"));
        if (!line) continue;
        const data = line.slice(5).trim();
        if (data === "[DONE]") {
          statusEl.textContent = "完成";
          continue;
        }
        const payload = JSON.parse(data);
        if (payload.error) throw new Error(payload.error.message);
        const delta = payload.choices?.[0]?.delta?.content;
        if (delta) output.textContent += delta;
      }
    }
  } catch (err) {
    if (err.name === "AbortError") {
      statusEl.textContent = "已取消";
    } else {
      statusEl.textContent = "出错";
      output.textContent += `\n[错误] ${err.message}`;
    }
  } finally {
    sendBtn.disabled = false;
    controller = null;
  }
});
</script>
</body>
</html>
```

- [ ] **Step 2: 启动验证**

后端：`cd ai-stream-demo/backend && python -m uvicorn main:app --reload --port 8000`
前端：`cd ai-stream-demo/frontend && python -m http.server 5500`
浏览器打开 `http://localhost:5500`，点击「开始生成」。

Expected：文字逐字出现，状态 `连接中 → 生成中 → 完成`；DevTools Network 中请求为 `Transfer-Encoding: chunked` 且无 `Content-Length`。

- [ ] **Step 3: 提交检查点（需用户同意）**

```bash
git add ai-stream-demo/frontend
git commit -m "feat(ai-stream-demo): add minimal native streaming frontend"
```

---

## Task 7：README、文档索引与收尾验证

**Files:**
- Create: `ai-stream-demo/backend/README.md`
- Create: `ai-stream-demo/README.md`
- Modify: `.qoder/docs/README.md`
- Modify: `.qoder/docs/ai-stream-demo-实施计划.md`（勾选完成项）

- [ ] **Step 1: 写子项目 README**

`ai-stream-demo/README.md`：

```markdown
# ai-stream-demo

把 DeepSeek（OpenAI 兼容）流式能力封装成「水龙头」：FastAPI `StreamingResponse` + 异步生成器逐 token 推送 SSE，`finally` 必发 `data: [DONE]`。

## 目录

- `backend/`：单文件 FastAPI 应用与 pytest
- `frontend/`：原生 HTML，`fetch` + `ReadableStream` 逐块消费

## 启动

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # 填入 DEEPSEEK_API_KEY
python -m uvicorn main:app --reload --port 8000
```

另开终端：

```powershell
cd frontend
python -m http.server 5500
# 打开 http://localhost:5500
```

## 验证

```powershell
cd backend
python -m pytest -v
```

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/api/stream `
  -H "Content-Type: application/json" `
  -d '{"messages":[{"role":"user","content":"你好"}]}'
```

预期：逐条 `data:` 到达，最后一条为 `data: [DONE]`。

## 坑位清单

1. `finally` 不发 `[DONE]` → 前端永远等不到结束。
2. 启用 GZip 或设置 `Content-Length` → 服务端攒包，失去逐字。
3. 吞掉 `CancelledError` → 客户端断开后上游继续计费。
4. 上游异常直接抛出 → 流已开始，状态码无法回退。
5. 流开始后才校验 Key → 配置错误也返回 200 流。
6. `allow_origins=["*"]` 混搭 `allow_credentials=True` → 预检异常。
7. 前端 `response.text()` → 失去流式效果。
8. 前端按字节切 JSON → 多字节字符乱码，需 `TextDecoder(stream: true)`。
```

- [ ] **Step 2: 更新 `.qoder/docs/README.md` 索引**

在表格末尾追加：

```markdown
| ai-stream-demo | [设计说明](./ai-stream-demo-设计说明.md) | 流式接口封装：SSE 线格式、CORS 预检、finally 哨兵、坑位清单与测试策略 |
| ai-stream-demo | [实施计划](./ai-stream-demo-实施计划.md) | 7 个 TDD 任务：骨架 → CORS → 正常流 → 异常收敛 → 流前校验 → 前端 → 收尾 |
```

- [ ] **Step 3: 全量验证**

Run: `cd ai-stream-demo/backend && python -m pytest -v`
Expected: 5 passed

Run（真实联调，需已配置 Key）：
`curl.exe -N -X POST http://127.0.0.1:8000/api/stream -H "Content-Type: application/json" -d "{\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}]}"`
Expected: 逐行 `data:`，结尾 `data: [DONE]`

- [ ] **Step 4: 勾选本计划完成项并提交检查点（需用户同意）**

```bash
git add ai-stream-demo .qoder/docs/README.md
git commit -m "docs(ai-stream-demo): add README and doc index"
```
