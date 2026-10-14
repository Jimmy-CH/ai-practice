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
    request_id = "248fef55-a329-477f-8b76-23354bd16c7f"
    flow_code = "Flow_00000156"
else:
    xingyu_url = "http://nlup-llm-inter.yto56.com.cn:8060/api/chat/chat"
    # robot_code = "ROBOT_00000065"
    robot_code = "ROBOT_00000090"
    flow_code = ""


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
