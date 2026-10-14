import json
import logging
import time
import httpx
from app.config import settings
from app.services.xingyu_api import generate_by_xingyu


logger = logging.getLogger("app.services.analyzer")


PARSE_PROMPT = """你是一名资深运营文档分析师。请从下面的版本迭代文档中提取四类信息，并以 JSON 格式返回。
提取要求：
1. 新增功能：列出本次新增的功能点
2. 变更与优化：列出功能改进、流程优化、体验优化等
3. 注意事项：列出用户需要关注或提前准备的事项
4. 风险提示：列出可能出现的问题或风险

每类信息返回字符串数组，每条控制在 30 字以内。如果某类没有内容，返回空数组。

文档标题：{title}
文档正文：
{content}

请只返回 JSON，不要返回任何解释性文字。格式示例：
{{
  "新增功能": ["..."],
  "变更与优化": ["..."],
  "注意事项": ["..."],
  "风险提示": ["..."]
}}"""


async def _chat_deepseek(messages: list[dict]) -> str:
    if not settings.deepseek_api_key:
        raise RuntimeError("未配置 DeepSeek API Key")
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{settings.deepseek_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": settings.deepseek_model,
                "messages": messages,
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def _chat(messages: list[dict]) -> str:
    if settings.llm_provider == "xingyu":
        system_prompt = "你是一名资深运营文档分析师。"
        user_prompt = messages[-1]["content"] if messages else ""
        return await generate_by_xingyu(system_prompt, user_prompt)
    return await _chat_deepseek(messages)


async def analyze_document(title: str, content: str) -> dict:
    prompt = PARSE_PROMPT.format(title=title, content=content)
    start = time.perf_counter()
    raw = await _chat([{"role": "user", "content": prompt}])
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(f"[{settings.llm_provider}] analyze_document '{title}' duration={duration_ms:.2f}ms, response_length={len(raw)}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(raw[start:end + 1])
        else:
            raise ValueError(f"解析结果不是合法 JSON: {raw}") from exc
    for key in ["新增功能", "变更与优化", "注意事项", "风险提示"]:
        if key not in data:
            data[key] = []
    return data
