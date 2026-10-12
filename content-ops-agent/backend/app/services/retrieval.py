import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Evidence:
    text: str
    score: int


def split_and_rank(text: str, keywords: list[str]) -> list[Evidence]:
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n|(?<=[。！？.!?])\s*", text) if chunk.strip()]
    lowered_keywords = [keyword.lower() for keyword in keywords if keyword.strip()]
    ranked = [Evidence(chunk, sum(chunk.lower().count(keyword) for keyword in lowered_keywords)) for chunk in chunks]
    return sorted(ranked, key=lambda evidence: evidence.score, reverse=True)
