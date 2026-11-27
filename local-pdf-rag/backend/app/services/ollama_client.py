import httpx


class OllamaError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class OllamaClient:
    """通过 httpx 调用 Ollama 的 /api/embed 与 /api/chat。"""

    def __init__(
        self,
        base_url: str,
        embed_model: str,
        chat_model: str,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.embed_model = embed_model
        self.chat_model = chat_model
        self.timeout = timeout
        self._transport = transport

    async def _post(self, path: str, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self._transport
            ) as client:
                response = await client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise OllamaError("ollama_unreachable", f"无法连接 Ollama: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(
                "ollama_bad_response",
                f"Ollama 返回 HTTP {response.status_code}: {response.text[:300]}",
            )
        try:
            return response.json()
        except ValueError as exc:
            raise OllamaError("ollama_bad_response", "Ollama 返回非 JSON") from exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = await self._post("/api/embed", {"model": self.embed_model, "input": texts})
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise OllamaError("ollama_bad_response", "embeddings 数量与输入不一致")
        vectors: list[list[float]] = []
        dimension = None
        for vector in embeddings:
            if not isinstance(vector, list) or not vector:
                raise OllamaError("ollama_bad_response", "embedding 为空或格式错误")
            if dimension is None:
                dimension = len(vector)
            elif len(vector) != dimension:
                raise OllamaError("ollama_bad_response", "embedding 维度不一致")
            vectors.append([float(value) for value in vector])
        return vectors

    async def chat(self, messages: list[dict]) -> str:
        data = await self._post(
            "/api/chat", {"model": self.chat_model, "messages": messages, "stream": False}
        )
        message = data.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise OllamaError("ollama_bad_response", "chat 响应缺少 message.content")
        return message["content"]

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=3.0, transport=self._transport
            ) as client:
                response = await client.get("/api/tags")
            return response.status_code == 200
        except httpx.HTTPError:
            return False
