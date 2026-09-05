"""Classes de base pour les providers LLM.

Chaque provider porte :
- un rate limiter (intervalle min entre 2 appels → évite les bans),
- un circuit breaker (3 échecs → provider "ouvert" = ignoré pendant un cooldown),
- un compteur de santé (pour `doctor` et le dashboard).

Tous les providers implémentent `chat(system, prompt) -> str`.
"""
from __future__ import annotations

import asyncio
import json
import socket
import time
import urllib.error
import urllib.request


# ------------------------------------------------------------- erreurs -----

class ProviderError(Exception):
    """Erreur venue du provider (HTTP, réseau, quota...)."""

    def __init__(self, provider: str, status: int | None = None,
                 reason: str = "", kind: str = "unknown"):
        super().__init__(f"[{provider}] http={status or '-'} kind={kind}: {reason[:250]}")
        self.provider = provider
        self.status = status
        self.reason = reason
        self.kind = kind  # network | http | auth | rate_limit | server | unknown

    def classification(self) -> str:
        """Classification pour le boss : RATE_LIMIT vs PROVIDER_DOWN."""
        if self.kind == "rate_limit" or self.status == 429:
            return "RATE_LIMIT"
        return "PROVIDER_DOWN"


class ResponseFormatError(Exception):
    """Le provider a répondu mais dans un format inattendu."""


# ----------------------------------------------------- rate limiting --------

class RateLimiter:
    """Garantit un intervalle minimum entre deux appels au provider."""

    def __init__(self, min_interval: float):
        self.min_interval = max(0.0, min_interval)
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            delta = time.monotonic() - self._last
            wait = self.min_interval - delta
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


class CircuitBreaker:
    """N échecs consécutifs → circuit ouvert → provider ignoré (cooldown)."""

    def __init__(self, threshold: int = 3, cooldown: float = 60.0):
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures = 0
        self.opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.cooldown:
            # half-open : on retente
            self.opened_at = None
            self.failures = 0
            return True
        return False

    def record(self, ok: bool) -> None:
        if ok:
            self.failures = 0
            self.opened_at = None
        else:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = time.monotonic()


# ------------------------------------------------------------ provider ------

class Provider:
    kind = "base"

    def __init__(self, name: str, model: str = "", min_interval: float = 0.5,
                 http_timeout: float = 90, cooldown: float = 60,
                 breaker_threshold: int = 3, **_ignored):
        self.name = name
        self.model = model
        self.http_timeout = http_timeout
        self.limiter = RateLimiter(min_interval)
        self.breaker = CircuitBreaker(threshold=breaker_threshold,
                                      cooldown=cooldown)
        self.calls = 0
        self.errors = 0
        self.last_error = ""

    async def chat(self, system: str, prompt: str,
                   max_tokens: int = 2048, temperature: float = 0.2) -> str:
        """Point d'entrée protégé (rate limit + circuit breaker)."""
        if not self.breaker.allow():
            raise ProviderError(self.name, reason="circuit ouvert (cooldown)")
        await self.limiter.acquire()
        try:
            out = await self._chat(system, prompt, max_tokens, temperature)
        except (ProviderError, ResponseFormatError):
            self.breaker.record(False)
            self.errors += 1
            self.last_error = str(self)[:200]
            raise
        self.breaker.record(True)
        self.calls += 1
        return out

    async def _chat(self, system: str, prompt: str,
                    max_tokens: int, temperature: float) -> str:
        raise NotImplementedError

    def health(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "model": self.model,
            "calls": self.calls,
            "errors": self.errors,
            "breaker": "OUVERT (cooldown)" if self.breaker.opened_at else "fermé",
            "last_error": self.last_error[:120],
        }


# --------------------------------------------------------- helpers HTTP ----

def _classify_http(status: int) -> str:
    if status == 429:
        return "rate_limit"
    if status in (401, 403):
        return "auth"
    if status >= 500:
        return "server"
    return "http"


def _http_error_body(e: urllib.error.HTTPError) -> str:
    try:
        return e.read().decode("utf-8", "replace")[:400]
    except Exception:
        return ""


async def post_json(url: str, headers: dict, payload: dict, timeout: float,
                    provider: str) -> dict:
    def _do() -> dict:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            raise ProviderError(provider, status=e.code,
                                reason=_http_error_body(e),
                                kind=_classify_http(e.code))
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
            raise ProviderError(provider, reason=str(e), kind="network")

    return await asyncio.to_thread(_do)


async def get_json(url: str, headers: dict, timeout: float, provider: str) -> dict:
    def _do() -> dict:
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            raise ProviderError(provider, status=e.code,
                                reason=_http_error_body(e),
                                kind=_classify_http(e.code))
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
            raise ProviderError(provider, reason=str(e), kind="network")

    return await asyncio.to_thread(_do)
