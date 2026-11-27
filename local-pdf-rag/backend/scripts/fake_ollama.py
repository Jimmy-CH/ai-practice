import hashlib
import math

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="Fake Ollama")


def _vector(text: str, dimension: int = 16) -> list[float]:
    """用 SHA-256 生成确定性向量，保证同一文本每次得到相同结果。"""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = [digest[index] / 255.0 for index in range(dimension)]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


@app.post("/api/embed")
async def embed(payload: dict) -> dict:
    texts = payload.get("input", [])
    return {"embeddings": [_vector(str(text)) for text in texts]}


@app.post("/api/chat")
async def chat(payload: dict) -> dict:
    messages = payload.get("messages", [])
    question = next(
        (item.get("content", "") for item in reversed(messages) if item.get("role") == "user"),
        "",
    )
    answer = (
        "（假 Ollama 响应）已根据检索到的上下文生成答案。"
        "真实环境请安装 Ollama 并拉取 bge-m3、qwen2.5:3b。\n\n"
        f"收到的问题：{question[:200]}"
    )
    return {"message": {"role": "assistant", "content": answer}}


@app.get("/api/tags")
async def tags() -> dict:
    return {"models": [{"name": "bge-m3"}, {"name": "qwen2.5:3b"}]}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=11434)
