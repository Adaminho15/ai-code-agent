"""Adaptateur natif Anthropic (Messages API).

Utilisé notamment pour **Fable 5.1** (`claude-fable-5-1`), le cerveau du
Larbin Réparateur.
"""
from __future__ import annotations

from .base import Provider, ResponseFormatError, post_json


class AnthropicProvider(Provider):
    kind = "anthropic"

    def __init__(self, name: str, api_key: str,
                 model: str = "claude-fable-5-1",
                 base_url: str = "https://api.anthropic.com", **kw):
        super().__init__(name, model=model, **kw)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def _chat(self, system: str, prompt: str,
                    max_tokens: int, temperature: float) -> str:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        data = await post_json(f"{self.base_url}/v1/messages", headers, body,
                               self.http_timeout, self.name)
        texts = [b.get("text", "")
                 for b in data.get("content", [])
                 if isinstance(b, dict) and b.get("type") == "text"]
        if not any(t.strip() for t in texts):
            raise ResponseFormatError(
                f"{self.name}: pas de texte dans la réponse: {str(data)[:200]}")
        return "\n".join(t for t in texts if t.strip())
