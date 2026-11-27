import json

import pytest

from app.storage.base import ChunkRecord, DocumentRecord
from app.storage.json_store import JsonVectorStore


def make_doc(doc_id="d1"):
    return DocumentRecord(
        id=doc_id,
        filename="a.pdf",
        page_count=1,
        chunk_count=2,
        created_at="2026-01-01T00:00:00Z",
    )


def make_chunk(chunk_id, doc_id, text, embedding):
    return ChunkRecord(
        id=chunk_id,
        doc_id=doc_id,
        filename="a.pdf",
        page=1,
        index=0,
        start=0,
        end=len(text),
        text=text,
        embedding=embedding,
    )


@pytest.mark.asyncio
async def test_add_search_delete_roundtrip(tmp_path):
    path = tmp_path / "index.json"
    store = JsonVectorStore(path)
    await store.add_document(
        make_doc(),
        [
            make_chunk("c1", "d1", "cat", [1.0, 0.0]),
            make_chunk("c2", "d1", "dog", [0.0, 1.0]),
        ],
    )
    hits = await store.search([1.0, 0.0], top_k=1)
    assert hits[0].chunk.id == "c1"
    assert await store.counts() == (1, 2)

    reloaded = JsonVectorStore(path)
    assert await reloaded.counts() == (1, 2)
    assert await reloaded.delete_document("d1") is True
    assert await reloaded.counts() == (0, 0)
    assert json.loads(path.read_text(encoding="utf-8"))["documents"] == []


@pytest.mark.asyncio
async def test_delete_missing_returns_false(tmp_path):
    store = JsonVectorStore(tmp_path / "index.json")
    assert await store.delete_document("nope") is False
