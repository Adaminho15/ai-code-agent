"""Registry : construit les providers depuis la config + chaînes de fallback.

`pick(capability, exclude)` renvoie le premier provider SAIN de la chaîne —
c'est lui qui matérialise ta règle : « si l'IA est en maintenance, on recrée
le larbin sur une AUTRE IA » (jamais la même).
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Iterable

from ..log import log
from .anthropic import AnthropicProvider
from .base import Provider
from .jules import JulesProvider
from .mock import MockProvider
from .openai_compat import PRESETS, OpenAICompatProvider


def _substitute_env(value: str) -> str:
    """Remplace {VAR} par la variable d'environnement correspondante."""
    out = value
    for key in list(os.environ):
        out = out.replace("{" + key + "}", os.environ[key])
    return out


def _detect_local_model(base_url: str) -> str:
    """Ollama : détecte le premier modèle installé via /api/tags.

    Retourne "" si le serveur local est éteint ou ne répond pas.
    """
    root = base_url.rsplit("/v1", 1)[0]
    try:
        req = urllib.request.Request(root + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        models = data.get("models") or []
        if models:
            return str(models[0].get("name", ""))
    except Exception:  # noqa: BLE001
        pass
    return ""


class Registry:
    def __init__(self, providers: dict[str, Provider],
                 chains: dict[str, list[str]]):
        self.providers = providers
        self.chains = chains

    # ------------------------------------------------------------- build ---
    @classmethod
    def from_config(cls, cfg) -> "Registry":
        defaults = dict(
            min_interval=0.6,
            http_timeout=cfg.http_timeout,
            cooldown=cfg.provider_cooldown,
            breaker_threshold=cfg.breaker_threshold,
        )
        providers: dict[str, Provider] = {}
        for name, spec in cfg.providers.items():
            spec = dict(spec)
            kind = spec.pop("kind", "openai_compat")
            try:
                p = cls._build_one(name, kind, spec, defaults)
            except Exception as e:  # noqa: BLE001
                log("registry", f"⚠️ provider '{name}' désactivé : {e}", "🔌")
                continue
            if p is not None:
                providers[name] = p
                log("registry", f"provider '{name}' prêt "
                                f"({p.kind}, model={p.model})", "🔌")
        return cls(providers, dict(cfg.chains))

    @classmethod
    def _build_one(cls, name: str, kind: str, spec: dict,
                   defaults: dict) -> Provider | None:
        if kind == "mock":
            return MockProvider(name, **{**defaults, **spec})

        if kind == "anthropic":
            key_env = spec.pop("api_key_env", "ANTHROPIC_API_KEY")
            key = os.environ.get(key_env, "")
            if not key:
                raise RuntimeError(f"clé {key_env} absente du .env")
            kw = dict(defaults)
            kw.update({k: v for k, v in spec.items() if k in defaults})
            return AnthropicProvider(name, api_key=key, **kw)

        if kind == "jules":
            key_env = spec.pop("api_key_env", "JULES_API_KEY")
            key = os.environ.get(key_env, "")
            if not key:
                raise RuntimeError(f"clé {key_env} absente du .env")
            kw = dict(defaults)
            kw.update({k: v for k, v in spec.items() if k in defaults})
            return JulesProvider(name, api_key=key, **kw)

        # openai_compat (par défaut)
        preset = PRESETS.get(spec.pop("preset", ""), {})
        spec.pop("api_key", None)
        base_url = spec.get("base_url") or preset.get("base_url", "")
        if not base_url:
            raise RuntimeError("base_url manquante")
        base_url = _substitute_env(base_url)
        if "{" in base_url:
            raise RuntimeError(f"variable d'environnement manquante dans "
                               f"{base_url}")
        key_env = spec.get("api_key_env") or preset.get("api_key_env", "")
        keyless = bool(spec.pop("keyless", False)
                       or preset.get("keyless", False))
        if keyless:
            api_key = "local-sans-cle"   # header ignoré par les serveurs locaux
        else:
            api_key = os.environ.get(key_env, "") if key_env else ""
            if not api_key:
                raise RuntimeError(f"clé {key_env} absente du .env")
        model = spec.get("model") or preset.get("model", "")
        if keyless and not model:
            # IA locale : auto-détection du premier modèle installé (Ollama)
            model = _detect_local_model(base_url)
            if model:
                log("registry", f"🦙 modèle local détecté : {model}", "🔌")
            else:
                log("registry", "⚠️ aucun modèle local détecté (serveur "
                                "éteint ? `ollama pull ...`) — précise "
                                "'model' dans config.json sinon ce provider "
                                "échouera", "🔌")
        spec.pop("api_key_env", None)
        spec.pop("model", None)
        spec.pop("base_url", None)
        spec.pop("extra_headers", None)
        kw = dict(defaults)
        kw.update({k: v for k, v in spec.items() if k in defaults})
        return OpenAICompatProvider(
            name, base_url=base_url, api_key=api_key, model=model, **kw)

    # -------------------------------------------------------------- picks ---
    def pick(self, capability: str,
             exclude: Iterable[str] = ()) -> Provider | None:
        excluded = set(exclude)
        for name in self.chains.get(capability, []):
            if name in excluded or name not in self.providers:
                continue
            p = self.providers[name]
            if p.breaker.allow():
                return p
        log("registry", f"⚠️ aucun provider sain pour '{capability}' "
                        f"(exclus : {sorted(excluded) or 'aucun'})", "🔌")
        return None

    def get(self, name: str) -> Provider | None:
        return self.providers.get(name)

    def names(self) -> list[str]:
        return sorted(self.providers)

    def healths(self) -> list[dict]:
        return [p.health() for p in self.providers.values()]
