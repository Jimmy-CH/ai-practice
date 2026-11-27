# ai-stream-demo

把 DeepSeek（OpenAI 兼容）的流式能力封装成一根「水龙头」：FastAPI `StreamingResponse` + 异步生成器逐 token 推送 SSE，末尾在 `finally` 必发 `data: [DONE]`，前端用原生 `fetch` + `ReadableStream` 逐块消费。

## 目录

```
ai-stream-demo/
├── backend/       # 单文件 FastAPI 应用 + pytest
└── frontend/      # 原生 HTML，零依赖零构建
```

- `backend/main.py`：配置读取、CORS、SSE 编码、`/api/health`、`/api/stream`
- `backend/tests/test_stream.py`：健康检查、CORS 预检、正常流、上游异常收敛、缺 Key 校验
- `frontend/index.html`：打字机渲染与错误提示

## 启动

后端：

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # 填入 DEEPSEEK_API_KEY
python -m uvicorn main:app --reload --port 8000
```

前端（另开一个终端，独立端口以真实触发 CORS）：

```powershell
cd frontend
python -m http.server 5500
# 打开 http://localhost:5500
```

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查，返回模型名与 Key 是否配置 |
| POST | `/api/stream` | `{"messages":[{"role":"user","content":"..."}]}`，返回 SSE 流 |

正常事件：

```
data: {"choices":[{"delta":{"content":"你"}}]}

data: [DONE]
```

流开始后的错误：

```
data: {"error":{"type":"upstream_error","message":"..."}}

data: [DONE]
```

## 验证

自动化：

```powershell
cd backend
python -m pytest -v
```

手动（需已配置真实 Key）：

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/api/stream `
  -H "Content-Type: application/json" `
  -d "{\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}]}"
```

预期：逐条 `data:` 到达，最后一条为 `data: [DONE]`；DevTools Network 中该请求为 `Transfer-Encoding: chunked` 且无 `Content-Length`。

## 坑位清单

1. `finally` 不发 `[DONE]` → 前端 reader 永远等不到结束。
2. 启用 GZip 或设置 `Content-Length` → 服务端攒包，失去逐字效果。
3. 吞掉 `CancelledError` → 客户端断开后上游继续生成、继续计费。
4. 上游异常直接抛出 → 流已开始，HTTP 状态码无法回退，前端收到半截。
5. 流开始后才校验 Key → 配置错误也以 200 流返回，前端难判断。
6. `allow_origins=["*"]` 混搭 `allow_credentials=True` → 预检行为异常。
7. 前端用 `response.text()` → 失去流式效果。
8. 前端按字节切 JSON → 多字节字符被截断乱码，需 `TextDecoder(stream: true)`。

## 设计文档

设计、实施计划与实现说明归档在仓库 `.qoder/docs/`：`ai-stream-demo-设计说明.md`、`ai-stream-demo-实施计划.md`、`ai-stream-demo-实现说明.md`。
