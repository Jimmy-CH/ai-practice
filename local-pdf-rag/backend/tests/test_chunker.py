import pytest

from app.ingestion.chunker import TextChunker


def test_chunk_size_and_overlap():
    text = "a" * 2000
    chunks = TextChunker(800, 100).split(text)
    assert [len(chunk.text) for chunk in chunks] == [800, 800, 600]
    assert chunks[0].text[-100:] == chunks[1].text[:100]
    assert chunks[1].text[-100:] == chunks[2].text[:100]


def test_short_text_single_chunk():
    chunks = TextChunker(800, 100).split("hello")
    assert len(chunks) == 1
    assert chunks[0].text == "hello"


def test_blank_text_returns_empty():
    assert TextChunker().split("   \n\t ") == []


def test_overlap_must_be_less_than_size():
    with pytest.raises(ValueError):
        TextChunker(100, 100)
