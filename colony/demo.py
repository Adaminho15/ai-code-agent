"""Scénario de démonstration complet : TOUT le design en une exécution.

Étapes :
1. Le boss crée un larbin `validator` avec un tool Python... qui a un bug. 💥
2. Le validator crashe au sandbox → self-healing : rollback impossible
   (v1 = code buggé initial) → le boss enclenche la réparation → le Larbin
   Réparateur (Fable 5.1 en live / mock en démo) recode AVEC la mémoire des
   bugs → candidat testé au sandbox → déployé → retry → ✅
3. Le validator délègue un résumé au rôle `summarizer` → le boss VALIDE la
   délégation → crée un larbin sur la 1ère IA de la chaîne `chat`.
4. Cette IA tombe en panne (503 simulé en démo) → le boss escalade :
   NOUVEAU summarizer sur une AUTRE IA → la demande reprend → ✅
5. Le validator fusionne tool + résumé et répond. Rapport final détaillé.

Par défaut : 100% mock (aucune clé API requise). Avec `--live` : vraies IAs
(Fable 5.1 via Anthropic, OpenRouter, Gemini... selon ton .env).
"""
from __future__ import annotations

import asyncio
import json

from . import bus as bus_mod
from .boss import Boss
from .bus import Bus, Message
from .config import Config, demo_config_path, default_config_path
from .knowledge import KnowledgeBase
from .log import dim, log
from .providers.registry import Registry

BUGGY_VALIDATOR = '''import json


def handle(payload):
    """Valide des emails (version initiale, contient des bugs)."""
    emails = payload.get("emails", [])
    domains = payload.get("allowed_domains", ["gmail.com", "outlook.com", "proton.me"])
    results = []
    for e in emails:
        local, _, domain = e.partition("@")
        sentinel = domains[5]  # BUG : IndexError si moins de 6 domaines
        ok = bool(local) and domain == sentinel  # BUG : ne compare qu'au 6e
        results.append({"email": e, "valid": ok})
    return {"results": results}
'''

EMAILS = [
    "adam@gmail.com",
    "projet@outlook.com",
    "fake@spam.io",
    "pas-un-email",
    "hey@proton.me",
]


async def run_demo(live: bool = False, config_path: str | None = None) -> int:
    print(dim("=" * 72))
    print(dim(f"  DÉMO COLONIE — mode {'LIVE (vraies IAs)' if live else 'MOCK (aucune clé requise)'}"))
    print(dim("=" * 72))

    cfg = Config(config_path or (default_config_path() if live
                                 else demo_config_path()))
    bus = Bus(max_history=cfg.max_history)
    registry = Registry.from_config(cfg)
    if not registry.providers:
        print("❌ Aucun provider disponible — remplis ton .env (voir .env.example)")
        return 1
    kb = KnowledgeBase()
    boss = Boss(registry, bus, cfg, kb)
    await boss.start()

    human = bus.register("human")

    # 1) Larbin validator avec un tool buggé
    validator = await boss.spawn(
        "validator", tool_code=BUGGY_VALIDATOR,
        reason="démo : validation d'emails avec tool Python")

    req = Message(
        bus_mod.REQUEST, frm="human", to=validator.addr, task_id="demo-1",
        body="Valide cette liste d'emails avec ton tool, puis fais faire un "
             "résumé du résultat par un larbin 'summarizer'.",
        payload={
            "use_tool": True,
            "payload": {
                "emails": EMAILS,
                "allowed_domains": ["gmail.com", "outlook.com", "proton.me"],
            },
            "expected_seconds": 12 if not live else 60,
            "delegate_after": {
                "role": "summarizer",
                "body": "Résume ce résultat de validation d'emails en 2 "
                        "phrases (valides vs invalides).",
            },
        })

    print()
    await bus.send(req)

    timeout = 120 if not live else 900
    resp = None
    try:
        while True:
            raw = await asyncio.wait_for(human.get(), timeout=timeout)
            if raw.type == bus_mod.RESPONSE and raw.reply_to == req.id:
                resp = raw
                break
    except asyncio.TimeoutError:
        print("❌ La démo n'a pas abouti dans le temps imparti.")

    # ------------------------------------------------------------ rapport --
    report = cfg.style.get("report", "normal")
    print()
    print(dim("=" * 72))
    print("  RAPPORT FINAL")
    print(dim("=" * 72))
    if resp is not None:
        status = resp.payload.get("status")
        print(f"Statut de la tâche  : {'✅ OK' if status == 'ok' else '❌ ÉCHEC'}")
        result = resp.payload.get("result")
        if isinstance(result, dict):
            tool = result.get("work") or result.get("tool") or {}
            n_ok = sum(1 for r in tool.get("results", []) if r.get("valid"))
            n_ko = len(tool.get("results", [])) - n_ok
            print(f"Emails validés      : {n_ok} valides / {n_ko} invalides")
            print(f"Délégation résumé   : {result.get('delegation', '?')}")
            summary = result.get("summary")
            if summary:
                print(f"Résumé du summarizer: {str(summary)[:220]}")
        else:
            print(f"Résultat : {str(result)[:400]}")
        if status != "ok":
            print(f"Raison : {resp.payload.get('reason', '?')}")

    if report == "court":
        await boss.stop()
        return 0 if resp is not None else 1

    print("\n— Événements du boss —")
    for e in boss.events:
        print(f"  {e}")
    print("\n— Larbins —")
    for lb in boss.larbins.values():
        print(f"  {lb.name:<16} rôle={lb.role:<12} IA={lb.provider.name:<14} "
              f"statut={lb.status:<10} versions_code={len(lb.versions)} "
              f"req={lb.stats['requests']} réparations={lb.stats['repairs']}")
    if report == "detaille":
        print("\n— Providers —")
        for h in registry.healths():
            print(f"  {h['name']:<14} {h['kind']:<14} calls={h['calls']:<3} "
                  f"errors={h['errors']:<3} breaker={h['breaker']}")
        print(f"\n— Bus : {bus.stats()} — "
              f"{len(kb.entries)} entrées en mémoire globale "
              f"(data/knowledge.json) —")

    await boss.stop()
    return 0 if resp is not None else 1
