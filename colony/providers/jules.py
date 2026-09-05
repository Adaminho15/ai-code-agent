"""Adaptateur Jules (Google) — agent de code asynchrone.

⚠️ Expérimental : Jules n'est pas un modèle de chat mais un agent qui bosse
sur un repo (ou en mode "repoless"). L'adaptateur :
1. crée une session avec le prompt (repoless par défaut),
2. approuve automatiquement le plan si Jules le demande (configurable),
3. poll le statut jusqu'à COMPLETED / FAILED / timeout,
4. renvoie la dernière activité texte de l'agent (+ URL de PR le cas échéant).

Auth : header `x-goog-api-key: $JULES_API_KEY`.
Docs : https://jules.google/docs/api/reference/
"""
from __future__ import annotations

import asyncio
import time

from .base import Provider, ProviderError, get_json, post_json

TERMINAL_OK = ("COMPLETED",)
TERMINAL_NOK = ("FAILED",)


class JulesProvider(Provider):
    kind = "jules"

    def __init__(self, name: str, api_key: str,
                 base_url: str = "https://jules.googleapis.com/v1alpha",
                 poll_interval: float = 3.0, max_wait: float = 600.0,
                 auto_approve: bool = True, **kw):
        super().__init__(name, model="jules", **kw)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval
        self.max_wait = max_wait
        self.auto_approve = auto_approve

    def _headers(self) -> dict:
        return {"x-goog-api-key": self.api_key,
                "Content-Type": "application/json"}

    async def _chat(self, system: str, prompt: str,
                    max_tokens: int, temperature: float) -> str:
        full_prompt = f"{system}\n\n---\n\n{prompt}" if system else prompt
        session = await post_json(
            f"{self.base_url}/sessions", self._headers(),
            {"prompt": full_prompt, "title": "colony"},
            self.http_timeout, self.name)
        sid = session.get("id") or session.get("name", "").split("/")[-1]
        if not sid:
            raise ProviderError(self.name, reason="session Jules sans id",
                                kind="server")

        deadline = time.monotonic() + self.max_wait
        state = "QUEUED"
        while time.monotonic() < deadline:
            await asyncio.sleep(self.poll_interval)
            info = await get_json(f"{self.base_url}/sessions/{sid}",
                                  self._headers(), self.http_timeout, self.name)
            state = info.get("state", info.get("status", ""))
            if state == "AWAITING_PLAN_APPROVAL" and self.auto_approve:
                await post_json(
                    f"{self.base_url}/sessions/{sid}:approvePlan",
                    self._headers(), {}, self.http_timeout, self.name)
            if state in TERMINAL_OK or state in TERMINAL_NOK:
                break
        else:
            raise ProviderError(self.name,
                                reason=f"session {sid} toujours en cours "
                                       f"(>{self.max_wait}s)", kind="server")

        if state in TERMINAL_NOK:
            raise ProviderError(self.name,
                                reason=f"session Jules FAILED ({sid})",
                                kind="server")

        # Récupère la dernière activité texte de l'agent (best effort).
        try:
            acts = await get_json(f"{self.base_url}/sessions/{sid}/activities",
                                  self._headers(), self.http_timeout, self.name)
        except ProviderError:
            acts = {}
        text = self._last_agent_text(acts)

        outputs = session.get("outputs") or info.get("outputs") or []
        pr_urls = []
        for out in outputs:
            pr = (out or {}).get("pullRequest") or {}
            if pr.get("url"):
                pr_urls.append(f"PR: {pr['url']} — {pr.get('title', '')}")

        parts = [f"(Jules session {sid} — {state})"]
        if text:
            parts.append(text)
        parts.extend(pr_urls)
        return "\n".join(parts)

    @staticmethod
    def _last_agent_text(activities: dict) -> str:
        items = activities.get("activities", activities) or []
        if isinstance(items, dict):
            items = list(items.values())
        texts = []
        for a in items:
            if not isinstance(a, dict):
                continue
            author = str(a.get("author", a.get("actor", ""))).lower()
            if "user" in author:
                continue
            for key in ("text", "content", "message", "description"):
                v = a.get(key)
                if isinstance(v, str) and v.strip():
                    texts.append(v.strip())
                    break
        return texts[-1] if texts else ""
