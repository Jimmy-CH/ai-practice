import json
from collections.abc import AsyncIterator

import httpx

from app.config import settings


class UpstreamError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


_client: httpx.AsyncClient | None = None


def init_client() -> None:
    global _client
    _client = httpx.AsyncClient(
        base_url=settings.DEEPSEEK_BASE_URL,
        timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
    )


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def stream_chat(messages: list[dict], model: str | None = None) -> AsyncIterator[str]:
    client = _client
    if client is None:
        init_client()
        client = _client
    payload = {
        "model": model or settings.DEEPSEEK_MODEL,
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Accept": "text/event-stream",
    }
    try:
        async with client.stream("POST", "/chat/completions", json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                body = (await resp.aread()).decode("utf-8", "replace")[:300]
                raise UpstreamError("upstream_http", f"HTTP {resp.status_code}: {body}")
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content")
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    raise UpstreamError("upstream_parse", data[:300])
                if delta:
                    yield delta
    except UpstreamError:
        raise
    except (httpx.HTTPError, OSError) as exc:
        raise UpstreamError("upstream_network", f"{type(exc).__name__}: {exc}") from exc
