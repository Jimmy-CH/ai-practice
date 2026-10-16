"""海报配图生成链路：脚本文本 → 画面描述提炼 → 星语文生图 → 本地落盘。

提炼走 material_writer._chat（provider 路由）；生图走 xingyu_api 文生图封装。
图片落盘目录按 __file__ 推导，不受进程 WorkingDirectory 影响。
"""
import logging
import time

from app.services import material_writer

logger = logging.getLogger("app.services.poster_writer")

REFINE_PROMPT = """你是一名资深视觉设计师。下面是一份海报脚本文案，请把它改写成一段可直接用于 AI 文生图工具的中文视觉描述。

要求：
- 画面描述需覆盖：主体形象、场景环境、氛围情绪、配色方案、画面风格
- 不要输出广告语、标语、文字排版要求（文生图模型无法可靠渲染文字）
- 只输出一段连贯的视觉描述，不超过 200 字，不要任何前缀和解释

海报脚本：
{script}"""


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
