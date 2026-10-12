import json

import httpx


class DeepSeekGenerator:
    def __init__(self, api_key: str, base_url: str, model: str, client: httpx.AsyncClient | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = client or httpx.AsyncClient(timeout=30)

    async def generate(self, theme: str, evidence: list[dict]) -> list[dict]:
        if not self.api_key:
            raise ValueError("未配置 DeepSeek API Key")
        system = "你是内容运营助手。不得使用证据外事实。仅输出 JSON。"
        payload = {"model": self.model, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": system}, {"role": "user", "content": json.dumps({"theme": theme, "evidence": evidence}, ensure_ascii=False)}]}
        response = await self.client.post(f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, json=payload)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)["assets"]
