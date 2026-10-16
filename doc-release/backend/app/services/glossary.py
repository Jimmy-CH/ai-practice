"""术语表加载与命中匹配。加载一次后缓存，文件变更需重启服务。"""

import json
from functools import lru_cache
from pathlib import Path

GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "glossary.json"


@lru_cache(maxsize=1)
def load_glossary() -> dict:
    return json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))


def match_terms(text: str) -> list[str]:
    """返回文本中命中的术语名（按术语表顺序、去重）。"""
    lowered = text.lower()
    hits: list[str] = []
    for item in load_glossary()["terms"]:
        names = [item["term"], *item.get("aliases", [])]
        if any(n and n.lower() in lowered for n in names):
            hits.append(item["term"])
    return hits


def build_glossary_prompt_section() -> str:
    lines = []
    for item in load_glossary()["terms"]:
        aliases = "、".join(item.get("aliases", []))
        lines.append(f"- {item['term']}：{item['note']}（别名：{aliases}）")
    return "\n".join(lines)
