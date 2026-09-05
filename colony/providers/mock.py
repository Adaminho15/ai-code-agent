"""Provider mock : permet de tester TOUTE la colonie sans aucune clé API.

Comportements :
- "good"  : répond toujours (déterministe, adapté au rôle demandé),
- "flaky" : échoue en 503 sur les N premiers appels (simule une panne),
- "down"  : échoue toujours (simule une maintenance).

Le mock "réparateur" renvoie un code corrigé valide pour la démo self-healing.
"""
from __future__ import annotations

import asyncio

from .base import Provider, ProviderError

FIXED_EMAIL_VALIDATOR = '''import json


def handle(payload):
    """Valide des emails contre une liste de domaines autorisés."""
    emails = payload.get("emails", [])
    domains = payload.get("allowed_domains", ["gmail.com", "outlook.com", "proton.me"])
    results = []
    for e in emails:
        local, _, domain = e.partition("@")
        valid = bool(local) and domain in domains
        results.append({"email": e, "valid": valid})
    return {"results": results}
'''


class MockProvider(Provider):
    kind = "mock"

    def __init__(self, name: str, behavior: str = "good", model: str = "mock-1",
                 fail_first: int = 5, **kw):
        super().__init__(name, model=model, **kw)
        self.behavior = behavior
        self.fail_first = fail_first
        self._calls = 0

    async def _chat(self, system: str, prompt: str,
                    max_tokens: int, temperature: float) -> str:
        self._calls += 1
        if self.behavior == "down" or (
                self.behavior == "flaky" and self._calls <= self.fail_first):
            raise ProviderError(self.name, status=503,
                                reason="panne simulée (mock)", kind="server")
        if self.behavior == "slow":
            await asyncio.sleep(30)  # simule une IA qui traîne
        await asyncio.sleep(0.03)
        low = (system + "\n" + prompt).lower()
        if any(k in low for k in ("réparateur", "corrige", "répare", "repair")):
            return "```python\n" + FIXED_EMAIL_VALIDATOR + "\n```"
        if any(k in low for k in ("résume", "résumé", "synthèse", "summary")):
            return ("Synthèse (mock) : le lot analysé contient des adresses "
                    "valides et invalides ; les invalides utilisent un domaine "
                    "non autorisé ou un format cassé. Recommandation : nettoyer "
                    "la liste avant tout envoi.")
        return "OK (mock) — traité : " + prompt.strip()[:120].replace("\n", " ")
