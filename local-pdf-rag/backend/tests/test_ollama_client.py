import httpx
import pytest

from app.services.ollama_client import OllamaClient, OllamaError


def make_client(handler):
    transport = httpx.MockTransport(handler)
    return OllamaClient(
        base_url="http://fake-ollama",
        embed_model="bge-m3",
        chat_model="qwen2.5:3b",
        timeout=5,
        transport=transport,
    )


@pytest.mark.asyncio
async def test_embed_success():
    def handler(request):
        assert request.url.path == "/api/embed"
        return httpx.Response(200, json={"embeddings": [[1.0, 0.0], [0.0, 1.0]]})

    client = make_client(handler)
    assert await client.embed(["cat", "dog"]) == [[1.0, 0.0], [0.0, 1.0]]


@pytest.mark.asyncio
async def test_embed_count_mismatch_raises():
    def handler(request):
        return httpx.Response(200, json={"embeddings": [[1.0, 0.0]]})

    client = make_client(handler)
    with pytest.raises(OllamaError) as exc:
        await client.embed(["cat", "dog"])
    assert exc.value.code == "ollama_bad_response"


@pytest.mark.asyncio
async def test_chat_success():
    def handler(request):
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200, json={"message": {"role": "assistant", "content": "答案"}}
        )

    client = make_client(handler)
    assert await client.chat([{"role": "user", "content": "hi"}]) == "答案"


@pytest.mark.asyncio
async def test_unreachable_maps_to_error():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    client = make_client(handler)
    with pytest.raises(OllamaError) as exc:
        await client.embed(["cat"])
    assert exc.value.code == "ollama_unreachable"
