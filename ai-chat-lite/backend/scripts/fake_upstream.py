"""本地假上游：模拟 OpenAI 兼容 /chat/completions 的慢速 SSE，便于无真实 Key 时联调。

用法（两个终端）：
    1) python -m uvicorn scripts.fake_upstream:app --port 8011
    2) 在 backend/ 下启动主服务，指向假上游：
       $env:DEEPSEEK_API_KEY="fake"; $env:DEEPSEEK_BASE_URL="http://127.0.0.1:8011"
       python -m uvicorn app.main:app --port 8000

用户消息里包含 SIMULATE_HTTP_ERROR 时会返回 502，用来验证错误链路。
"""
import asyncio
import json
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="fake-upstream")

TOKENS = [
    "这是", "一个", "**流式**", "输出", "的", "示例", "。\n\n",
    "- 第一点\n", "- 第二点\n",
    "\n```python\n", "print(1)\n", "```\n",
]
# 慢速模式：FAKE_DELAY_SECONDS 控制每个 token 间隔，FAKE_REPEAT 控制整段重复次数
DELAY_SECONDS = float(os.getenv("FAKE_DELAY_SECONDS", "0.12"))
REPEAT = int(os.getenv("FAKE_REPEAT", "1"))


@app.post("/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    text = "".join(m.get("content", "") for m in body.get("messages", []) if m.get("role") == "user")
    if "SIMULATE_HTTP_ERROR" in text:
        return JSONResponse({"error": {"message": "simulated upstream failure"}}, status_code=502)

    async def gen():
        for token in TOKENS * REPEAT:
            chunk = {"choices": [{"delta": {"content": token}}]}
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            await asyncio.sleep(DELAY_SECONDS)
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
