import os
import json
import asyncio
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI
from dotenv import load_dotenv
from datetime import datetime

# 加载环境变量
load_dotenv()

app = FastAPI(title="DeepSeek 聊天机器人后端 (企业级增强版)")

# ✅ 1. 增加 CORS 跨域中间件（生产环境建议将 "*" 替换为具体的前端域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化 DeepSeek 客户端
client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


# ✅ 2. 定义请求体模型（增加可选的 resume_from 字段，用于断线续传）
class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: str = "deepseek-chat"
    stream: bool = True
    resume_from: Optional[int] = -1  # 前端重试时，传回最后收到的 seq


# ✅ 3. 健康检查接口（供前端检测服务状态）
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "model": "deepseek-chat",
        "timestamp": datetime.now().isoformat()
    }


# ✅ 4. 核心流式生成器（增加 seq 序号，防止重试时内容重复）
async def generate_stream_response(messages: List[Dict[str, str]], model: str, resume_from: int):
    seq = 0
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=0.7
        )

        async for chunk in stream:
            # 核心逻辑：如果前端传了 resume_from，跳过已经发送过的 token
            if seq <= resume_from:
                seq += 1
                continue

            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                # 封装 SSE 数据，必须包含 seq
                data = {"seq": seq, "content": content, "finished": False}
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                seq += 1

        # 流结束信号
        yield f"data: {json.dumps({'seq': seq, 'finished': True})}\n\n"

    except Exception as e:
        error_data = {"seq": seq, "error": str(e), "finished": True}
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if request.stream:
        return StreamingResponse(
            generate_stream_response(
                request.messages,
                request.model,
                request.resume_from
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    else:
        response = await client.chat.completions.create(
            model=request.model,
            messages=request.messages
        )
        return {"message": response.choices[0].message.content}
