"""Registry : construit les providers depuis la config + chaînes de fallback.

`pick(capability, exclude)` renvoie le premier provider SAIN de la chaîne —
c'est lui qui matérialise ta règle : « si l'IA est en maintenance, on recrée
le larbin sur une AUTRE IA » (jamais la même).
"""
from __future__ import annotations

import os
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


class Registry:
    def __init__(self, providers: dict[str, Provider],
                 chains: dict[str, list[str]]):
        self.providers = providers
        self.chains = chains

    # ------------------------------------------------------------- build ---
    @classmethod
    def from_config(cls, cfg) -> "Registry":
        providers: dict[str, Provider] = {}
        for name, spec in cfg.providers.items():
            spec = dict(spec)
            kind = spec.pop("kind", "openai_compat")
            try:
                p = cls._build_one(name, kind, spec)
            except Exception as e:  # noqa: BLE001
                log("registry", f"⚠️ provider '{name}' désactivé : {e}", "🔌")
                continue
            if p is not None:
                providers[name] = p
                log("registry", f"provider '{name}' prêt "
                                f"({p.kind}, model={p.model})", "🔌")
        return cls(providers, dict(cfg.chains))

    @classmethod
    def _build_one(cls, name: str, kind: str, spec: dict) -> Provider | None:
        if kind == "mock":
            return MockProvider(name, **spec)

        if kind == "anthropic":
            key_env = spec.pop("api_key_env", "ANTHROPIC_API_KEY")
            key = os.environ.get(key_env, "")
            if not key:
                raise RuntimeError(f"clé {key_env} absente du .env")
            return AnthropicProvider(name, api_key=key, **spec)

        if kind == "jules":
            key_env = spec.pop("api_key_env", "JULES_API_KEY")
            key = os.environ.get(key_env, "")
            if not key:
                raise RuntimeError(f"clé {key_env} absente du .env")
            return JulesProvider(name, api_key=key, **spec)

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
        api_key = os.environ.get(key_env, "") if key_env else ""
        if not api_key:
            raise RuntimeError(f"clé {key_env} absente du .env")
        model = spec.get("model") or preset.get("model", "")
        spec.pop("api_key_env", None)
        spec.pop("model", None)
        spec.pop("base_url", None)
        spec.pop("extra_headers", None)
        return OpenAICompatProvider(
            name, base_url=base_url, api_key=api_key, model=model, **spec)

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
