import asyncio
import json
import os
from collections.abc import AsyncIterator
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

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

app.add_middleware(
    CORSMiddleware,
    # 坑位：不要用 allow_origins=["*"] 与 allow_credentials=True 混搭
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def sse_error(exc: Exception) -> str:
    # 截断 300 字符，避免上游完整报错或敏感信息回显
    message = f"{type(exc).__name__}: {exc}"[:300]
    payload = {"error": {"type": "upstream_error", "message": message}}
    return sse_pack(json.dumps(payload, ensure_ascii=False))


def get_client() -> AsyncOpenAI:
    # 依赖注入点：测试通过 monkeypatch 替换，避免真实网络调用
    return AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "model": DEEPSEEK_MODEL,
        "key_configured": bool(DEEPSEEK_API_KEY),
    }


@app.post("/api/stream")
async def stream_chat(request: ChatRequest) -> StreamingResponse:
    # 坑位：校验必须发生在 StreamingResponse 之前，
    # 否则响应已以 200 开始，无法再返回 500/400
    if not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=500, detail="未配置 DEEPSEEK_API_KEY")
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    client = get_client()
    messages = [message.model_dump() for message in request.messages]

    async def event_generator() -> AsyncIterator[str]:
        client_gone = False
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
        except (asyncio.CancelledError, GeneratorExit):
            # 坑位：客户端断开时取消/关闭必须向上抛，不能吞掉；
            # 此时对端已走，无法再送达 [DONE]，只做标记
            client_gone = True
            raise
        except Exception as exc:
            # 流已开始无法改状态码：把异常收敛成 error 事件，前端仍能善终
            yield sse_error(exc)
        finally:
            # 坑位：终止哨兵在 finally 补发，正常结束与上游异常都必达 [DONE]
            if not client_gone:
                yield sse_pack("[DONE]")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
