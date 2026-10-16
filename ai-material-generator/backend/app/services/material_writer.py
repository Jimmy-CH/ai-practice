import asyncio
import logging
import time
import httpx
from app.config import settings
from app.services.xingyu_api import generate_by_xingyu


logger = logging.getLogger("app.services.material_writer")

# 在飞生成任务注册表：key -> Task，用于后台预热与用户请求撞车时复用同一任务
_inflight_tasks: dict[tuple, asyncio.Task] = {}


MATERIAL_TYPES = {
    "version_announcement": "版本宣发稿",
    "operation_guide": "网点操作指引",
    "faq": "FAQ 问答库",
    "push_script": "行者推送话术",
    "poster_script": "海报脚本",
    "training_outline": "培训课件大纲",
}

GENERATE_PROMPT = """你是一名资深运营文案。请根据以下版本迭代要点，为「{audience}」受众撰写一篇「{type_name}」。

文档标题：{title}
新增功能：
{新增功能}
变更与优化：
{变更与优化}
注意事项：
{注意事项}
风险提示：
{风险提示}

写作要求：
- 语气专业、清晰、易读
- 突出对受众的实际价值
- 风险提示放在文末
- 返回 Markdown 格式正文，不需要代码块包裹

请直接输出正文。"""


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
                "temperature": 0.5,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def _chat(messages: list[dict]) -> str:
    if settings.llm_provider == "xingyu":
        # 优先取调用方传入的 system 人设；无 system 消息时保留历史默认
        system_prompt = next(
            (m["content"] for m in messages if m.get("role") == "system"),
            "你是一名资深运营文案。",
        )
        user_prompt = messages[-1]["content"] if messages else ""
        return await generate_by_xingyu(system_prompt, user_prompt)
    return await _chat_deepseek(messages)


def _format_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "无"


def _extract_title(content: str, default: str) -> str:
    for line in content.splitlines():
        line = line.strip().lstrip("# ").lstrip("#")
        if line:
            return line
    return default


def generator_label() -> str:
    """meta.generator 展示名：随 provider 路由，生成与缓存命中两条路径共用。"""
    return "Xingyu" if settings.llm_provider == "xingyu" else "DeepSeek"


async def generate_material(title: str, analysis: dict, audience: str, material_type: str) -> dict:
    if material_type not in MATERIAL_TYPES:
        raise ValueError(f"不支持的物料类型: {material_type}")
    prompt = GENERATE_PROMPT.format(
        title=title,
        audience=audience,
        type_name=MATERIAL_TYPES[material_type],
        新增功能=_format_list(analysis.get("新增功能", [])),
        变更与优化=_format_list(analysis.get("变更与优化", [])),
        注意事项=_format_list(analysis.get("注意事项", [])),
        风险提示=_format_list(analysis.get("风险提示", [])),
    )
    start = time.perf_counter()
    content = await _chat([{"role": "user", "content": prompt}])
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"[{settings.llm_provider}] generate_material title='{title}' audience='{audience}' "
        f"type='{material_type}' duration={duration_ms:.2f}ms response_length={len(content)}"
    )
    return {
        "title": _extract_title(content, title),
        "content": content,
        "audience": audience,
        "material_type": material_type,
        "meta": {
            "audience": audience,
            "material_type": MATERIAL_TYPES[material_type],
            "generator": generator_label(),
        },
    }


async def generate_material_deduped(key: tuple, factory) -> dict:
    """同 key 的在飞生成任务直接复用，避免同一物料并发调用两次 LLM。

    factory 为无参 callable，返回协程；仅在首次注册时才会被调用。
    任务完成后（无论成败）清除注册，允许后续重试。
    """
    existing = _inflight_tasks.get(key)
    if existing is not None:
        return await existing
    task = asyncio.create_task(factory())
    _inflight_tasks[key] = task
    try:
        return await task
    finally:
        if _inflight_tasks.get(key) is task:
            _inflight_tasks.pop(key, None)


async def generate_all_materials(
    title: str,
    analysis: dict,
    audience: str,
    only_types: set[str] | None = None,
    dedup_keys: dict[str, tuple] | None = None,
) -> list[dict]:
    """并发生成物料。only_types 为待生成的类型白名单：None 表示全部，空集表示不生成。

    dedup_keys 提供类型 -> 去重键映射；提供时同 key 的在飞任务会被复用。
    """
    types = only_types if only_types is not None else MATERIAL_TYPES.keys()
    keys = dedup_keys or {}

    async def run(material_type: str) -> dict:
        key = keys.get(material_type)
        if key is None:
            return await generate_material(title, analysis, audience, material_type)
        return await generate_material_deduped(
            key, lambda: generate_material(title, analysis, audience, material_type)
        )

    tasks = [run(material_type) for material_type in MATERIAL_TYPES if material_type in types]
    return await asyncio.gather(*tasks) if tasks else []
