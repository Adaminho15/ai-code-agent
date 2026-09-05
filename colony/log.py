"""Journalisation colorée de la colonie.

Chaque agent (boss ou larbin) a une couleur fixe, tous les messages vont
aussi dans data/logs/colony.log pour garder un historique complet.
"""
from __future__ import annotations

import os
from datetime import datetime

_COLORS = [
    "\033[96m",  # cyan
    "\033[93m",  # jaune
    "\033[92m",  # vert
    "\033[95m",  # magenta
    "\033[94m",  # bleu
    "\033[91m",  # rouge
    "\033[97m",  # blanc
]
_RESET = "\033[0m"
_DIM = "\033[2m"
_BOLD = "\033[1m"

_addr_color: dict[str, str] = {}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.environ.get("COLONY_LOG_DIR", os.path.join(ROOT, "data", "logs"))
_logfile = None  # None = pas encore ouvert, False = échec d'ouverture


def _ensure_logfile():
    global _logfile
    if _logfile is None:
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            _logfile = open(
                os.path.join(LOG_DIR, "colony.log"), "a", encoding="utf-8"
            )
        except Exception:
            _logfile = False
    return _logfile


def _color_for(addr: str) -> str:
    if addr not in _addr_color:
        _addr_color[addr] = _COLORS[len(_addr_color) % len(_COLORS)]
    return _addr_color[addr]


def log(agent: str, text: str, icon: str = "💬") -> None:
    """Affiche une ligne de log colorée + l'écrit dans colony.log."""
    line = (
        f"{_DIM}[{datetime.now().strftime('%H:%M:%S')}]{_RESET} "
        f"{icon} {_BOLD}{_color_for(agent)}{agent}{_RESET}: {text}"
    )
    print(line, flush=True)
    f = _ensure_logfile()
    if f:
        f.write(
            f"[{datetime.now().isoformat(timespec='seconds')}] {agent}: {text}\n"
        )
        f.flush()


def dim(text: str) -> str:
    return f"{_DIM}{text}{_RESET}"
