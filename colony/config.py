"""Chargement de la configuration : .env + config.json.

- Le fichier .env (à la racine) contient les clés API. Il n'est JAMAIS commis.
- config.json décrit les providers et les chaînes de fallback par capacité.
- Les timeouts/règles ont des valeurs par défaut raisonnables, tout est
  surchargeable dans config.json (clé "settings").
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- .env ------

def load_env(path: str | None = None) -> None:
    """Charge un fichier .env minimaliste (KEY=value), sans écraser l'existant."""
    path = path or os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


# ------------------------------------------------------------ defaults ------

DEFAULT_SETTINGS = {
    # Timeout de base d'une demande entre larbins (secondes).
    "request_timeout": 30,
    # Délai "attendu" d'une tâche : au-delà de expected * factor, le watchdog
    # du boss considère que le larbin est bloqué et escalade.
    "watchdog_factor": 6.0,
    # Délai global dur que attend un larbin avant d'abandonner
    # (= request_timeout * grace_factor). Pendant ce temps il peut y avoir
    # plusieurs escalades.
    "grace_factor": 4.0,
    # Nb max d'escalades (recréation du larbin sur une AUTRE IA) par demande.
    "max_escalations": 2,
    # Nb max de tentatives de réparation (self-healing) par larbin et par tâche.
    "max_repairs": 3,
    # Temps max accordé au Larbin Réparateur (Fable 5.1) pour recoder.
    "repair_timeout": 180,
    # Timeout d'exécution du code d'un larbin dans le sandbox.
    "sandbox_timeout": 15,
    # Timeout HTTP par défaut des providers.
    "http_timeout": 90,
    # Cooldown du circuit breaker d'un provider (secondes).
    "provider_cooldown": 60,
    # Validation des délégations par le boss : "rules" (rapide) ou "llm".
    "delegation_validation": "rules",
    # Version max de code gardée par larbin (pour rollback).
    "max_versions": 3,
}


class Config:
    """Accès unifié à la configuration."""

    def __init__(self, path: str):
        load_env()
        with open(path, encoding="utf-8") as f:
            self.data = json.load(f)
        settings = dict(DEFAULT_SETTINGS)
        settings.update(self.data.get("settings", {}))
        self.settings = settings

    # -- providers ----------------------------------------------------------
    @property
    def providers(self) -> dict:
        return self.data.get("providers", {})

    @property
    def chains(self) -> dict[str, list[str]]:
        """capability -> liste ordonnée de providers (fallback)."""
        return self.data.get("chains", {})

    # -- réglages -----------------------------------------------------------
    def __getattr__(self, name: str):
        try:
            return self.settings[name]
        except KeyError:
            raise AttributeError(name)


def default_config_path() -> str:
    return os.path.join(ROOT, "config.json")


def demo_config_path() -> str:
    return os.path.join(ROOT, "config.demo.json")
