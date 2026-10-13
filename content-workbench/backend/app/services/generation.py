import json
import logging
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

SCHEMAS: dict[str, dict[str, type]] = {
    "announcement": {"title": str, "summary": str, "body": str, "actions": list},
    "faq": {"items": list},
    "poster": {"headline": str, "subhead": str, "selling_points": list, "cta": str},
}
KINDS = frozenset(SCHEMAS)

PROMPT = """你是产品内容生成助手。仅依据给定证据资料生成公告、FAQ、海报文案，禁止使用证据之外的产品事实。
只输出 JSON 对象 {"assets": [...]}，数组元素形如：
{"kind": "announcement", "content": {"title": "...", "summary": "...", "body": "...", "actions": ["..."]}, "source_ids": ["s1"]}
{"kind": "faq", "content": {"items": [{"question": "...", "answer": "...", "source_ids": ["s1"]}]}, "source_ids": ["s1"]}
{"kind": "poster", "content": {"headline": "...", "subhead": "...", "selling_points": ["..."], "cta": "..."}, "source_ids": ["s1"]}
source_ids 只能取自证据给出的 source_id。"""


class ContentGenerator(Protocol):
    async def generate(self, theme: str, audience: str, evidence: list[dict]) -> list[dict]: ...


class DeepSeekGenerator:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(self, theme: str, audience: str, evidence: list[dict]) -> list[dict]:
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": json.dumps({"theme": theme, "audience": audience, "evidence": evidence}, ensure_ascii=False)},
            ],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        return data["assets"] if isinstance(data, dict) else data


class FakeGenerator:
    async def generate(self, theme: str, audience: str, evidence: list[dict]) -> list[dict]:
        ids = [item["source_id"] for item in evidence]
        text = evidence[0]["text"] if evidence else "智能报表支持拖拽分析与导出。"
        return self.build(ids, theme=theme, audience=audience, text=text)

    @staticmethod
    def build(source_ids: list[str], theme: str, audience: str, text: str = "智能报表支持拖拽分析与导出。") -> list[dict]:
        ids = list(source_ids)
        return [
            {"kind": "announcement", "content": {"title": f"{theme}正式发布", "summary": text[:50], "body": text, "actions": ["查看详情"]}, "source_ids": ids},
            {"kind": "faq", "content": {"items": [{"question": f"什么是{theme}？", "answer": text[:50], "source_ids": ids}]}, "source_ids": ids},
            {"kind": "poster", "content": {"headline": theme, "subhead": audience, "selling_points": [text[:20]], "cta": "立即了解"}, "source_ids": ids},
        ]


class GenerationValidationError(ValueError):
    pass


def _citations(node: dict, allowed: dict[str, str]) -> list[dict]:
    ids = node.get("source_ids")
    if not isinstance(ids, list) or not ids:
        raise GenerationValidationError("缺少来源引用")
    citations = []
    for source_id in ids:
        if source_id not in allowed:
            raise GenerationValidationError("引用了未知来源")
        citations.append({"source_id": source_id, "text": allowed[source_id]})
    return citations


def validate_kind_content(kind: str, content: dict) -> None:
    schema = SCHEMAS.get(kind)
    if schema is None or not isinstance(content, dict):
        raise GenerationValidationError("内容类型或结构非法")
    for field, field_type in schema.items():
        if not isinstance(content.get(field), field_type):
            raise GenerationValidationError(f"字段 {field} 缺失或类型错误")
    if kind == "faq":
        for entry in content["items"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("question"), str) or not isinstance(entry.get("answer"), str):
                raise GenerationValidationError("FAQ 问答项结构非法")


def validate_generation(items: list[dict], allowed: dict[str, str]) -> list[tuple[str, dict, list[dict]]]:
    results = []
    for item in items:
        kind, content = item.get("kind"), item.get("content")
        validate_kind_content(kind, content)
        if kind == "faq":
            citations = []
            for entry in content["items"]:
                citations.extend(_citations(entry, allowed))
        else:
            citations = _citations(item, allowed)
        unique = list({(c["source_id"], c["text"]): c for c in citations}.values())
        results.append((kind, content, unique))
    if {kind for kind, _, _ in results} != KINDS:
        raise GenerationValidationError("未生成完整的三类内容")
    return results


def parse_model_output(raw: Any) -> list[dict]:
    data = raw["assets"] if isinstance(raw, dict) else raw
    if not isinstance(data, list):
        raise GenerationValidationError("模型输出结构非法")
    return data
