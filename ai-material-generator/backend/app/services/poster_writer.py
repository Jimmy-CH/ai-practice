"""海报配图生成链路：脚本文本 → 画面描述提炼 → 星语文生图 → 本地落盘。

提炼走 material_writer._chat（provider 路由）；生图走 xingyu_api 文生图封装。
图片落盘目录按 __file__ 推导，不受进程 WorkingDirectory 影响。
"""
import asyncio
import logging
import time
import uuid
from pathlib import Path

import requests

from app.services import material_writer
from app.services.xingyu_api import generate_poster_image_url

logger = logging.getLogger("app.services.poster_writer")

REFINE_PROMPT = """你是一名资深视觉设计师。下面是一份海报脚本文案，请把它改写成一段可直接用于 AI 文生图工具的中文视觉描述。

要求：
- 画面描述需覆盖：主体形象、场景环境、氛围情绪、配色方案、画面风格
- 不要输出广告语、标语、文字排版要求（文生图模型无法可靠渲染文字）
- 只输出一段连贯的视觉描述，不超过 200 字，不要任何前缀和解释

海报脚本：
{script}"""


# backend/app/services/poster_writer.py → parent×3 = backend/，图片目录 backend/poster_images/
POSTER_IMAGE_DIR = Path(__file__).resolve().parent.parent.parent / "poster_images"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


async def refine_poster_prompt(script_content: str) -> str:
    """把海报脚本文案提炼成文生图视觉描述。"""
    prompt = REFINE_PROMPT.format(script=script_content)
    messages = [
        {"role": "system", "content": "你是一名资深视觉设计师，擅长把文案创意转化为画面描述。"},
        {"role": "user", "content": prompt},
    ]
    start = time.perf_counter()
    description = await material_writer._chat(messages)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"refine_poster_prompt script_len={len(script_content)} "
        f"duration={duration_ms:.2f}ms response_length={len(description)}"
    )
    return description.strip()


async def generate_poster_image(prompt: str) -> tuple[str, bytes]:
    """调星语文生图并下载图片，返回 (图片URL, 图片字节)。任一环节失败抛 RuntimeError。"""
    start = time.perf_counter()
    url = await generate_poster_image_url(prompt)
    response = await asyncio.to_thread(requests.get, url, timeout=60)
    if response.status_code != 200 or not response.content:
        raise RuntimeError(f"海报图下载失败: HTTP {response.status_code}")
    if not response.content.startswith(PNG_MAGIC):
        raise RuntimeError("海报图下载内容不是有效 PNG")
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"generate_poster_image prompt_len={len(prompt)} duration={duration_ms:.2f}ms "
        f"image_size={len(response.content)}"
    )
    return url, response.content


def save_poster_image(owner_id: int, data: bytes) -> str:
    """图片字节写入 backend/poster_images/{owner_id}/，返回相对 backend 的路径。"""
    dir_path = POSTER_IMAGE_DIR / str(owner_id)
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{uuid.uuid4()}.png"
    file_path.write_bytes(data)
    return str(file_path.relative_to(POSTER_IMAGE_DIR.parent))


def remove_poster_image(file_path: str) -> None:
    """删除落盘文件（用户删图与入库失败回滚共用）；路径不存在时静默。"""
    absolute = POSTER_IMAGE_DIR.parent / file_path
    absolute.unlink(missing_ok=True)
