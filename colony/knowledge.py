"""Base de connaissances globale (mémoire partagée des bugs).

C'est LA mémoire dont tu parlais : quand le Réparateur recode un larbin, il
reçoit l'historique des bugs déjà rencontrés (par TOUTE la colonie) pour ne
pas refaire les mêmes erreurs — et quand un candidat de réparation échoue,
l'échec est enregistré pour la prochaine tentative.

Persistance : data/knowledge.json
"""
from __future__ import annotations

import json
import os
import time

from .config import ROOT


class KnowledgeBase:
    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(ROOT, "data", "knowledge.json")
        self.entries: list[dict] = []
        self._load()

    # -------------------------------------------------------------- I/O ----
    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.entries = json.load(f).get("entries", [])
            except Exception:
                self.entries = []

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"entries": self.entries[-200:]}, f,
                      ensure_ascii=False, indent=2)

    # ------------------------------------------------------------ usage ----
    def record_bug(self, role: str, error: str, detail: str = "",
                   code_snippet: str = "") -> None:
        self.entries.append({
            "type": "bug",
            "role": role,
            "error": error,
            "detail": detail[:500],
            "code_snippet": code_snippet[:800],
            "ts": time.time(),
        })
        self.save()

    def record_fix(self, role: str, outcome: str, explanation: str = "",
                   candidate_excerpt: str = "") -> None:
        """outcome: 'success' | 'failed_candidate'."""
        self.entries.append({
            "type": "fix",
            "role": role,
            "outcome": outcome,
            "explanation": explanation[:500],
            "candidate_excerpt": candidate_excerpt[:800],
            "ts": time.time(),
        })
        self.save()

    def for_role(self, role: str, limit: int = 8) -> list[dict]:
        return [e for e in self.entries if e.get("role") == role][-limit:]

    def prompt_context(self, role: str, limit: int = 8) -> str:
        """Historique formaté pour injection dans le prompt du Réparateur."""
        entries = self.for_role(role, limit)
        if not entries:
            return "(aucun bug connu pour ce rôle — premier incident)"
        lines = []
        for e in entries:
            if e["type"] == "bug":
                lines.append(f"- BUG: {e['error']} :: {e['detail'][:150]}")
            else:
                verdict = "RÉUSSI" if e["outcome"] == "success" else "CANDIDAT REJETÉ"
                lines.append(f"- FIX {verdict}: {e['explanation'][:150]}")
        return "\n".join(lines)
