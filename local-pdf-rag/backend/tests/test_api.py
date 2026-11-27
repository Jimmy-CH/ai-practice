from pathlib import Path

import httpx
import pytest

from app.ingestion.pdf_parser import PageText
from app.main import app
from app.services.rag_service import RagService, get_service
from app.storage.json_store import JsonVectorStore

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


class FakeOllama:
    async def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]

    async def chat(self, messages):
        return "根据文档，答案如下 [sample.pdf p1]"

    async def ping(self):
        return True


class FakeParser:
    def parse_bytes(self, data):
        return [PageText(page=1, text="Retrieval augmented generation " * 200)]


def build_service(tmp_path):
    return RagService(
        store=JsonVectorStore(tmp_path / "index.json"),
        ollama=FakeOllama(),
        parser=FakeParser(),
    )


@pytest.mark.asyncio
async def test_full_flow(tmp_path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_service] = lambda: service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["ollama_reachable"] is True

        upload = await client.post(
            "/api/documents",
            files={"file": ("sample.pdf", FIXTURE.read_bytes(), "application/pdf")},
        )
        assert upload.status_code == 201
        document = upload.json()
        assert document["chunk_count"] > 0

        listed = await client.get("/api/documents")
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        asked = await client.post("/api/ask", json={"question": "what is RAG?"})
        assert asked.status_code == 200
        payload = asked.json()
        assert payload["answer"]
        assert payload["sources"][0]["filename"] == "sample.pdf"
        assert payload["sources"][0]["index"] == 1

        deleted = await client.delete(f"/api/documents/{document['id']}")
        assert deleted.status_code == 204
        assert (await client.get("/api/documents")).json() == []
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ask_empty_index_and_blank_question(tmp_path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_service] = lambda: service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/ask", json={"question": "hi"})
        assert response.status_code == 400
        assert response.json()["detail"].startswith("empty_index")

        empty = await client.post("/api/ask", json={"question": "   "})
        assert empty.status_code == 400
        assert empty.json()["detail"].startswith("empty_question")
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_non_pdf_rejected(tmp_path):
    service = build_service(tmp_path)
    app.dependency_overrides[get_service] = lambda: service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/documents", files={"file": ("a.txt", b"hello", "text/plain")}
        )
        assert response.status_code == 400
        assert response.json()["detail"].startswith("unsupported_file")
    app.dependency_overrides.clear()
