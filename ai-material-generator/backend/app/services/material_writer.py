import httpx
from app.config import settings


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


async def _chat(messages: list[dict]) -> str:
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


def _format_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "无"


def _extract_title(content: str, default: str) -> str:
    for line in content.splitlines():
        line = line.strip().lstrip("# ").lstrip("#")
        if line:
            return line
    return default


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
    content = await _chat([{"role": "user", "content": prompt}])
    return {
        "title": _extract_title(content, title),
        "content": content,
        "audience": audience,
        "material_type": material_type,
        "meta": {
            "audience": audience,
            "material_type": MATERIAL_TYPES[material_type],
            "generator": "DeepSeek",
        },
    }


async def generate_all_materials(
    title: str, analysis: dict, audience: str, skip_types: set[str] | None = None
) -> list[dict]:
    skip_types = skip_types or set()
    materials = []
    for material_type in MATERIAL_TYPES:
        if material_type in skip_types:
            continue
        materials.append(await generate_material(title, analysis, audience, material_type))
    return materials
