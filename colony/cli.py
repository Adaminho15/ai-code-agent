"""CLI de la colonie.

Commandes :
  python -m colony.cli demo [--live]   # démo complète (mock par défaut)
  python -m colony.cli doctor          # santé de toutes les IAs du .env
  python -m colony.cli run "tâche"     # donne une tâche à un larbin codeur
"""
from __future__ import annotations

import argparse
import asyncio
import time

from . import bus as bus_mod
from .boss import Boss
from .bus import Bus, Message
from .config import Config, default_config_path
from .demo import run_demo
from .knowledge import KnowledgeBase
from .log import dim
from .providers.registry import Registry


def _build():
    cfg = Config(default_config_path())
    bus = Bus()
    registry = Registry.from_config(cfg)
    boss = Boss(registry, bus, cfg, KnowledgeBase())
    return cfg, bus, registry, boss


async def cmd_demo(args) -> int:
    return await run_demo(live=args.live)


async def cmd_doctor(args) -> int:
    cfg, _bus, registry, _boss = _build()
    print(dim("Santé des providers (petit ping réel) —"))
    print()
    if not registry.providers:
        print("❌ Aucun provider configuré (clés absentes du .env ?)")
        return 1
    failures = 0
    for name in sorted(registry.providers):
        p = registry.providers[name]
        if p.kind == "mock":
            print(f"  ✅ {name:<14} mock — toujours OK")
            continue
        t0 = time.monotonic()
        try:
            out = await p.chat("Test de santé.", "Réponds juste : pong",
                               max_tokens=8, temperature=0.0)
            dt = (time.monotonic() - t0) * 1000
            print(f"  ✅ {name:<14} {p.model:<28} {dt:7.0f} ms — "
                  f"{str(out)[:40]!r}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"  ❌ {name:<14} {p.model:<28} {str(e)[:90]}")
    print()
    print(dim("Chaînes de fallback configurées :"))
    for cap, chain in cfg.chains.items():
        print(f"  {cap:<12} → {' → '.join(chain)}")
    return 0 if failures == 0 else 1


async def cmd_run(args) -> int:
    cfg, bus, registry, boss = _build()
    if not registry.providers:
        print("❌ Aucun provider — remplis .env")
        return 1
    await boss.start()
    human = bus.register("human")
    coder = await boss.spawn("coder", reason=f"tâche : {args.task[:60]}")
    req = Message(bus_mod.REQUEST, frm="human", to=coder.addr,
                  task_id="run-1", body=args.task,
                  payload={"expected_seconds": 90})
    await bus.send(req)
    deadline = time.monotonic() + (args.timeout or 900)
    try:
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                print("❌ timeout global")
                break
            raw = await asyncio.wait_for(human.get(), timeout=left)
            if raw.type == bus_mod.RESPONSE and raw.reply_to == req.id:
                if raw.payload.get("status") == "ok":
                    print("\n===== RÉSULTAT =====")
                    print(raw.payload.get("result"))
                else:
                    print(f"❌ échec : {raw.payload.get('reason')}")
                break
    except asyncio.TimeoutError:
        print("❌ timeout global")
    finally:
        await boss.stop()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="colony")
    sub = parser.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="démo complète (mock ou --live)")
    d.add_argument("--live", action="store_true",
                   help="utilise les vraies IAs du .env")
    d.set_defaults(fn=cmd_demo)

    doc = sub.add_parser("doctor", help="santé des providers")
    doc.set_defaults(fn=cmd_doctor)

    r = sub.add_parser("run", help="donne une tâche à un larbin codeur")
    r.add_argument("task")
    r.add_argument("--timeout", type=int, default=None)
    r.set_defaults(fn=cmd_run)

    args = parser.parse_args()
    try:
        return asyncio.run(args.fn(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
