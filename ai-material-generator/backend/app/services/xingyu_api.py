import json
import logging
import uuid
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)
env = "dev"


if env == "dev":
    xingyu_url = "http://10.130.13.74:8060/api/chat/chat"
    robot_code = "ROBOT_00000149"
    # 文生图专用机器人（chat 机器人调 /api/chat/image 会 401，robotCode 按能力隔离）
    image_robot_code = "ROBOT_00000418"
    image_url = "http://10.130.13.74:8060/api/chat/image"
else:
    xingyu_url = "http://nlup-llm-inter.yto56.com.cn:8060/api/chat/chat"
    # robot_code = "ROBOT_00000065"
    robot_code = "ROBOT_00000090"
    # 占位：prod 文生图机器人编码待平台提供后替换
    image_robot_code = "ROBOT_00000418"
    image_url = "http://nlup-llm-inter.yto56.com.cn:8060/api/chat/image"


def xingyu_ai_request_api(role_content: str, data: str) -> Optional[List]:
    payload = {
        "robotCode": robot_code,
        "chatMessages": [
            {"role": "system", "content": role_content},
            {"role": "user", "content": data},
        ],
        "requestId": f"{uuid.uuid4()}",
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url=xingyu_url, headers=headers, data=json.dumps(payload))
    """
            {
            "status": 0,
            "message": "success",
            "data": {
                "msgId":"20240611f5ac5e3c0a1d4bad9e1afe6788dd3812"
                "sessionId": "f5ac5e3c-0a1d-4bad-9e1a-fe6788dd3812",
                "requestId": "f5ac5e3c-0a1d-4bad-9e1a-fe6788dd3812",
                "chatType": 3,
                "rasaResult": null,
                "contents": [
                    {
                        "index": 0,
                        "role": null,
                        "content": "我是来自阿里云的大规模语言模型，我叫通义千问。",
                        "reasoningContent": "用户问了 我是谁，表明。。。。"
                    }
                ]
            }
        }
    """
    if response.status_code == 200:
        result = response.json()
        if f"{result['status']}" == "0":
            return result["data"]["contents"]
        else:
            logger.error(
                f"xingyu_ai_request_api(role_content={role_content},data={data}) failed=>Result({response.text})"
            )
    else:
        logger.error(
            f"xingyu_ai_request_api(role_content={role_content},data={data}) failed=>StatusCode({response.status_code})"
        )
        return None


async def generate_by_xingyu(system_prompt: str, user_prompt: str) -> str:
    """异步包装 xingyu_ai_request_api，返回模型生成的文本内容。"""
    import asyncio

    contents = await asyncio.to_thread(xingyu_ai_request_api, system_prompt, user_prompt)
    if not contents or not isinstance(contents, list):
        raise RuntimeError("星语 API 未返回有效内容")
    first = contents[0]
    if isinstance(first, dict):
        return first.get("content", "")
    return str(first)


def xingyu_text_to_image_api(prompt: str) -> Optional[str]:
    """同步调用星语文生图接口，返回图片 OSS 临时 URL；失败返回 None。

    实测要点：仅 async=false 可用；URL 优先在 data.contents[0].content
    （chatType=5），文档所称 data.results 实测为 null，两者都兼容。
    """
    payload = {
        "robotCode": image_robot_code,
        "async": False,
        "prompt": prompt,
        "requestId": f"{uuid.uuid4()}",
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(
            url=image_url, headers=headers, data=json.dumps(payload), timeout=120
        )
    except requests.RequestException as exc:
        logger.error(f"xingyu_text_to_image_api(prompt={prompt[:50]}...) failed=>EXC({exc})")
        return None
    if response.status_code != 200:
        logger.error(
            f"xingyu_text_to_image_api failed=>StatusCode({response.status_code})"
        )
        return None
    result = response.json()
    if f"{result.get('status')}" != "0":
        logger.error(
            f"xingyu_text_to_image_api failed=>Result({response.text[:300]})"
        )
        return None
    data = result.get("data") or {}
    contents = data.get("contents") or []
    if contents and isinstance(contents[0], dict) and contents[0].get("content"):
        return contents[0]["content"]
    results = data.get("results") or []
    if results:
        return results[0]
    logger.error(f"xingyu_text_to_image_api failed=>NoImageUrl({response.text[:300]})")
    return None


async def generate_poster_image_url(prompt: str) -> str:
    """异步包装 xingyu_text_to_image_api，返回图片 OSS 临时 URL；失败抛 RuntimeError。"""
    import asyncio

    url = await asyncio.to_thread(xingyu_text_to_image_api, prompt)
    if not url:
        raise RuntimeError("星语文生图未返回图片 URL")
    return url
