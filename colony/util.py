"""Petits utilitaires partagés."""
from __future__ import annotations

import json
import re


def extract_code_block(text: str) -> str | None:
    """Extrait le premier bloc ```python ... ``` (ou ``` ... ```)."""
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text,
                  re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    stripped = text.strip()
    if stripped.startswith(("def ", "import ", "from ", "class ")):
        return stripped
    return None


def extract_json_block(text: str):
    """Extrait un bloc JSON (fencé ou brut). None si absent/invalide."""
    m = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except (json.JSONDecodeError, TypeError):
            pass
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
