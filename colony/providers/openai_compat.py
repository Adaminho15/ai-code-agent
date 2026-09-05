"""Adaptateur universel OpenAI-compatible.

Couvre NATIVEMENT (via presets) : OpenRouter, Cloudflare Workers AI, Groq,
Mistral, DeepSeek, Together, Cerebras, Fireworks, Google Gemini (endpoint
OpenAI-compat), OpenAI... et n'importe quelle passerelle custom via base_url.

Le format d'appel est toujours POST {base_url}/chat/completions.
"""
from __future__ import annotations

from .base import Provider, ProviderError, ResponseFormatError, post_json

PRESETS: dict[str, dict] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "model": "openrouter/auto",
    },
    "cloudflare": {
        # L'URL dépend du compte : {CLOUDFLARE_ACCOUNT_ID} est substitué.
        "base_url": "https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1",
        "api_key_env": "CLOUDFLARE_API_KEY",
        "model": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "api_key_env": "MISTRAL_API_KEY",
        "model": "mistral-large-latest",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-chat",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "api_key_env": "TOGETHER_API_KEY",
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "api_key_env": "CEREBRAS_API_KEY",
        "model": "llama-3.3-70b",
    },
    "fireworks": {
        "base_url": "https://api.fireworks.ai/inference/v1",
        "api_key_env": "FIREWORKS_API_KEY",
        "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key_env": "GEMINI_API_KEY",
        "model": "gemini-2.0-flash",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-4o-mini",
    },
    "anthropic-compat": {
        # Endpoint OpenAI-compat d'Anthropic (alternative à l'adaptateur natif).
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
        "model": "claude-fable-5-1",
    },
}


class OpenAICompatProvider(Provider):
    kind = "openai_compat"

    def __init__(self, name: str, base_url: str, api_key: str, model: str,
                 extra_headers: dict | None = None, **kw):
        super().__init__(name, model=model, **kw)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.extra_headers = extra_headers or {}

    async def _chat(self, system: str, prompt: str,
                    max_tokens: int, temperature: float) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        data = await post_json(
            f"{self.base_url}/chat/completions",
            {"Authorization": f"Bearer {self.api_key}",
             "Content-Type": "application/json", **self.extra_headers},
            body, self.http_timeout, self.name,
        )
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ResponseFormatError(
                f"{self.name}: structure de réponse inattendue: {str(data)[:200]}")
        if not isinstance(content, str) or not content.strip():
            raise ResponseFormatError(f"{self.name}: réponse vide")
        return content
