"""Sandbox : exécution du code des larbins dans un sous-processus isolé.

Contrat du code d'un larbin (« tool ») :

    def handle(payload: dict) -> dict

- le payload arrive en JSON sur stdin,
- le résultat doit être du JSON sur stdout,
- tout crash / timeout / sortie invalide est détecté et classé.

Le timeout attrape notamment les boucles infinies (le pire ennemi de ton
analyse 😉). C'est aussi ici qu'on TESTE le code recodé par le Réparateur
avant de le déployer — jamais de code non testé en production.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile

# Runner ajouté sous le code du larbin : il branche stdin/stdout sur handle().
_RUNNER = '''
import json as _json
import sys as _sys

try:
    _payload = _json.loads(_sys.stdin.read() or "{}")
except Exception:
    _payload = {}

_result = handle(_payload)
_sys.stdout.write(_json.dumps(_result))
'''

class SandboxError(Exception):
    """Erreur d'exécution d'un tool dans le sandbox."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"[sandbox:{kind}] {detail[:400]}")
        self.kind = kind      # crash | timeout | bad_output | no_handle
        self.detail = detail


def has_handle(code: str) -> bool:
    return "def handle" in code


async def run_tool(code: str, payload: dict, timeout: float = 15.0) -> dict:
    """Exécute `code` avec `payload` et retourne le dict résultat."""
    if not has_handle(code):
        raise SandboxError("no_handle", "le code ne définit pas handle(payload)")
    payload = payload if isinstance(payload, dict) else {}
    with tempfile.TemporaryDirectory(prefix="colony-sbx-") as td:
        path = os.path.join(td, "tool.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code + "\n\n" + _RUNNER)
        stdin = json.dumps(payload)

        def _run() -> subprocess.CompletedProcess:
            return subprocess.run(
                [sys.executable, path], input=stdin, capture_output=True,
                text=True, timeout=timeout, cwd=td)

        try:
            proc = await asyncio.to_thread(_run)
        except subprocess.TimeoutExpired:
            raise SandboxError(
                "timeout",
                f"le code a dépassé {timeout}s (boucle infinie ?)")
        if proc.returncode != 0:
            raise SandboxError("crash", proc.stderr or "exit != 0")
        try:
            out = json.loads(proc.stdout)
        except (json.JSONDecodeError, TypeError):
            raise SandboxError("bad_output", proc.stdout[-300:])
        if not isinstance(out, dict):
            raise SandboxError("bad_output", "le résultat n'est pas un objet JSON")
        return out


async def test_candidate(code: str, payloads: list[dict],
                         timeout: float = 10.0) -> tuple[bool, str]:
    """Teste un code candidat (post-recodage) sur plusieurs payloads.

    Payloads = payload original + cas limites (vide, minimal).
    Retourne (ok, raison).
    """
    if not has_handle(code):
        return False, "le candidat ne définit pas handle(payload)"
    for p in payloads:
        try:
            await run_tool(code, p, timeout=timeout)
        except SandboxError as e:
            return False, f"échec sur payload={str(p)[:80]} → {e}"
    return True, "ok"
