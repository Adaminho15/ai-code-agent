"""Exemple : construire TON propre scénario de colonie.

Lancement :
    python examples/custom_scenario.py          # mocks, aucune clé
    LIVE=1 python examples/custom_scenario.py   # vraies IAs du .env

Ce script crée une mini chaîne de production :
    coder (écrit une fonction) → reviewer (la relit) → optimiseur final.
Le reviewer parle directement au coder (request/response), le boss voit tout.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from colony import bus as bus_mod                     # noqa: E402
from colony.boss import Boss                          # noqa: E402
from colony.bus import Bus, Message                   # noqa: E402
from colony.config import Config, demo_config_path, default_config_path  # noqa: E402
from colony.knowledge import KnowledgeBase            # noqa: E402
from colony.providers.registry import Registry        # noqa: E402


async def main() -> None:
    live = bool(os.environ.get("LIVE"))
    cfg = Config(default_config_path() if live else demo_config_path())
    bus = Bus()
    registry = Registry.from_config(cfg)
    boss = Boss(registry, bus, cfg, KnowledgeBase())
    await boss.start()
    human = bus.register("human")

    # 1) le boss crée les larbins
    coder = await boss.spawn("coder", reason="écrire une fonction")
    reviewer = await boss.spawn("reviewer", reason="relire le code du coder")

    # 2) le coder écrit, puis demande DIRECTEMENT au reviewer de relire
    #    (délégation horizontale validée par le boss)
    req = Message(
        bus_mod.REQUEST, frm="human", to=coder.addr, task_id="perso-1",
        body=("Écris une fonction Python `slugify(texte)` qui transforme un "
              "titre en slug URL, puis fais relire ton code par le reviewer."),
        payload={
            "expected_seconds": 60 if live else 5,
            "delegate_after": {
                "role": "reviewer",
                "body": "Relis ce code de slugify et signale les problèmes.",
            },
        })
    await bus.send(req)

    deadline = time.monotonic() + (900 if live else 60)
    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(human.get(), timeout=deadline
                                         - time.monotonic())
        except asyncio.TimeoutError:
            print("⏱️ timeout")
            break
        if raw.type == bus_mod.RESPONSE and raw.reply_to == req.id:
            print("\n===== RÉSULTAT FINAL =====")
            print(raw.payload.get("result"))
            break

    for e in boss.events:
        print(f"  {e}")
    await boss.stop()


if __name__ == "__main__":
    asyncio.run(main())
