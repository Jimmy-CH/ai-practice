import pytest

from app.config import settings
from app.ingestion.pdf_parser import PageText
from app.services.rag_service import EmptyIndexError, RagService
from app.storage.json_store import JsonVectorStore


class FakeOllama:
    def __init__(self):
        self.chat_messages = None

    async def embed(self, texts):
        return [[1.0, 0.0] if "cat" in text else [0.0, 1.0] for text in texts]

    async def chat(self, messages):
        self.chat_messages = messages
        return "答案 [a.pdf p1]"


class FakeParser:
    def parse_bytes(self, data):
        return [PageText(page=1, text="cat " * 500)]


@pytest.mark.asyncio
async def test_ingest_and_ask(tmp_path):
    store = JsonVectorStore(tmp_path / "index.json")
    ollama = FakeOllama()
    service = RagService(store=store, ollama=ollama, parser=FakeParser())

    document = await service.ingest("a.pdf", b"ignored")
    assert document.page_count == 1
    assert document.chunk_count == 3

    response = await service.ask("cat?")
    assert response.answer == "答案 [a.pdf p1]"
    assert len(response.sources) == min(settings.TOP_K, 3)
    assert response.sources[0].index == 1
    assert "a.pdf p1" in ollama.chat_messages[1]["content"]


@pytest.mark.asyncio
async def test_ask_empty_index_raises(tmp_path):
    service = RagService(
        store=JsonVectorStore(tmp_path / "index.json"),
        ollama=FakeOllama(),
        parser=FakeParser(),
    )
    with pytest.raises(EmptyIndexError):
        await service.ask("hi")
