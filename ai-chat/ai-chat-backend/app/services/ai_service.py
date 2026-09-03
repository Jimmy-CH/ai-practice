
import json
from typing import List, Dict
from openai import AsyncOpenAI
from app.config import settings

client = AsyncOpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL
)


async def generate_stream_response(messages: List[Dict[str, str]], model: str, resume_from: int):
    seq = 0
    try:
        stream = await client.chat.completions.create(
            model=model, messages=messages, stream=True, temperature=0.7
        )
        async for chunk in stream:
            if seq <= resume_from:
                seq += 1
                continue
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                data = {"seq": seq, "content": content, "finished": False}
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                seq += 1
        yield f"data: {json.dumps({'seq': seq, 'finished': True})}\n\n"
    except Exception as e:
        error_data = {"seq": seq, "error": str(e), "finished": True}
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

