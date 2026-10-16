"""星语大模型网关同步封装（requests），异步侧用 asyncio.to_thread 包装。

网关契约（已验证）：payload 仅 robotCode + chatMessages + requestId，无鉴权头；
多传字段（如 agent）会被网关拒绝。单次调用约 6~15 秒，超时用 settings.llm_timeout。
"""

import asyncio
import json
import uuid

import requests

from app.config import settings


def xingyu_chat(system_prompt: str, user_prompt: str) -> str:
    payload = {
        "robotCode": settings.robot_code,
        "chatMessages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "requestId": str(uuid.uuid4()),
    }
    resp = requests.post(
        settings.xingyu_url,
        json=payload,
        timeout=settings.llm_timeout,
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"星语网关请求失败：HTTP {resp.status_code}")
    data = resp.json()
    if str(data.get("status")) != "0":
        raise RuntimeError(f"星语网关返回错误：{json.dumps(data, ensure_ascii=False)[:300]}")
    contents = (data.get("data") or {}).get("contents") or []
    if not contents:
        raise RuntimeError("星语网关未返回内容")
    return contents[0].get("content", "")


async def generate_by_xingyu(system_prompt: str, user_prompt: str) -> str:
    return await asyncio.to_thread(xingyu_chat, system_prompt, user_prompt)
