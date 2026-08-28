import os
import json
from typing import List, Dict
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import AsyncOpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = FastAPI(title="DeepSeek 聊天机器人后端")

# 初始化 DeepSeek 客户端
client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),  # 在 .env 中配置 DEEPSEEK_API_KEY=sk-xxx
    base_url="https://api.deepseek.com"  # DeepSeek 官方 API 地址
)


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: str = "deepseek-v4-flash"  # 推荐使用最新的 V4 Flash 模型
    stream: bool = True


async def generate_stream_response(messages: List[Dict[str, str]], model: str):
    try:
        # 调用 DeepSeek 流式接口
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,  # 开启流式输出
            temperature=0.7  # V4 模型默认温度为 0.7，表现更稳定
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                data = {"content": content, "finished": False}
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'finished': True})}\n\n"

    except Exception as e:
        error_data = {"error": str(e), "finished": True}
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"


@app.post("/chat")
async def chat(request: ChatRequest):
    if request.stream:
        return StreamingResponse(
            generate_stream_response(request.messages, request.model),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    else:
        response = await client.chat.completions.create(
            model=request.model,
            messages=request.messages
        )
        return {"message": response.choices[0].message.content}

