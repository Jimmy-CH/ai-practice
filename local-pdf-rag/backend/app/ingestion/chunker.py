import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkPiece:
    text: str
    start: int
    end: int


class TextChunker:
    """字符级滑窗切分：默认 800 字符，相邻片段重叠 100 字符。"""

    def __init__(self, size: int = 800, overlap: int = 100) -> None:
        if size <= 0:
            raise ValueError("size 必须大于 0")
        if overlap < 0:
            raise ValueError("overlap 不能为负数")
        if overlap >= size:
            raise ValueError("overlap 必须小于 size")
        self.size = size
        self.overlap = overlap

    def split(self, text: str) -> list[ChunkPiece]:
        if not text or not text.strip():
            return []
        step = self.size - self.overlap
        pieces: list[ChunkPiece] = []
        start = 0
        length = len(text)
        while start < length:
            end = min(start + self.size, length)
            piece = text[start:end].strip()
            if piece:
                pieces.append(ChunkPiece(text=piece, start=start, end=end))
            if end >= length:
                break
            start += step
        return pieces


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """余弦相似度；任一零向量返回 0.0，维度不一致抛 ValueError。"""
    if len(a) != len(b):
        raise ValueError("向量维度不一致")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
