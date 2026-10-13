import re
from dataclasses import dataclass


@dataclass
class Evidence:
    source_id: str
    text: str
    score: int


def split_and_rank(text: str, source_id: str, keywords: list[str]) -> list[Evidence]:
    keywords = [keyword.strip() for keyword in keywords if keyword and keyword.strip()]
    pieces = []
    for block in re.split(r"\n\s*\n", text):
        for piece in re.split(r"(?<=[。！？])\s*", block):
            piece = piece.strip()
            if len(piece) < 5:
                continue
            score = sum(1 for keyword in keywords if keyword in piece)
            pieces.append(Evidence(source_id=source_id, text=piece, score=score))
    return pieces


def select_evidence(sources: list[tuple[str, str]], keywords: list[str], top_k: int) -> list[Evidence]:
    seen = set()
    candidates = []
    for source_id, content in sources:
        for evidence in split_and_rank(content, source_id, keywords):
            if evidence.text in seen:
                continue
            seen.add(evidence.text)
            if evidence.score > 0:
                candidates.append(evidence)
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:top_k]
