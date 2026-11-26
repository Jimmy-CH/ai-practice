import json

import httpx
import pytest

from app.services import llm_client


def _sse_line(content: str = "", done: bool = False) -> bytes:
    if done:
        return b"data: [DONE]\n\n"
    payload = {"choices": [{"delta": {"content": content}}]}
    return f"data: {json.dumps(payload)}\n\n".encode()


def _install_transport(handler):
    llm_client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://upstream"
    )


async def test_collects_deltas_across_chunk_boundaries():
    body = _sse_line("你") + b": keepalive\n\n" + _sse_line("好") + _sse_line(done=True)

    async def handler(request: httpx.Request) -> httpx.Response:
        async def gen():
            for i in range(0, len(body), 7):  # 故意在 JSON 中间切块
                yield body[i : i + 7]

        return httpx.Response(200, content=gen())

    _install_transport(handler)
    chunks = [c async for c in llm_client.stream_chat([{"role": "user", "content": "hi"}])]
    assert chunks == ["你", "好"]


async def test_http_error_raises_upstream_http():
    async def handler(request):
        return httpx.Response(500, text="boom")

    _install_transport(handler)
    with pytest.raises(llm_client.UpstreamError) as exc:
        [c async for c in llm_client.stream_chat([{"role": "user", "content": "hi"}])]
    assert exc.value.code == "upstream_http"
    assert "500" in exc.value.message


async def test_bad_json_raises_upstream_parse():
    async def handler(request):
        return httpx.Response(200, content=b"data: {not-json}\n\n")

    _install_transport(handler)
    with pytest.raises(llm_client.UpstreamError) as exc:
        [c async for c in llm_client.stream_chat([{"role": "user", "content": "hi"}])]
    assert exc.value.code == "upstream_parse"


async def test_network_error_mapped():
    async def handler(request):
        raise httpx.ConnectError("boom", request=request)

    _install_transport(handler)
    with pytest.raises(llm_client.UpstreamError) as exc:
        [c async for c in llm_client.stream_chat([{"role": "user", "content": "hi"}])]
    assert exc.value.code == "upstream_network"
