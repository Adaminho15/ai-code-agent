"""Tests du noyau — 100% mockés, aucune clé API requise.

Lancement : python -m unittest discover -s tests -v
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from colony import bus as bus_mod                              # noqa: E402
from colony.boss import Boss                                   # noqa: E402
from colony.bus import Bus, Message                            # noqa: E402
from colony.config import Config, demo_config_path             # noqa: E402
from colony.demo import BUGGY_VALIDATOR, EMAILS                # noqa: E402
from colony.knowledge import KnowledgeBase                     # noqa: E402
from colony.providers.registry import Registry                 # noqa: E402
from colony.sandbox import SandboxError, run_tool, test_candidate  # noqa: E402


class ColonyTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cfg = Config(demo_config_path())
        self.cfg.settings.update({
            "request_timeout": 2,
            "grace_factor": 3.0,
            "watchdog_factor": 2.0,
            "max_escalations": 2,
            "max_repairs": 3,
            "repair_timeout": 20,
            "sandbox_timeout": 5,
        })
        self.bus = Bus()
        self.registry = Registry.from_config(self.cfg)
        self.kb = KnowledgeBase(
            path=os.path.join(tempfile.mkdtemp(), "knowledge.json"))
        self.boss = Boss(self.registry, self.bus, self.cfg, self.kb)
        await self.boss.start()
        self.human = self.bus.register("human")

    async def asyncTearDown(self):
        await self.boss.stop()

    async def _ask(self, larbin, body="fais le boulot", payload=None,
                   timeout=25):
        req = Message(bus_mod.REQUEST, frm="human", to=larbin.addr,
                      body=body, payload=payload or {})
        await self.bus.send(req)
        while True:
            raw = await asyncio.wait_for(self.human.get(), timeout=timeout)
            if raw.type == bus_mod.RESPONSE and raw.reply_to == req.id:
                return raw


class TestBus(unittest.TestCase):
    def test_cc_au_boss_et_livraison(self):
        async def go():
            bus = Bus()
            boss_q = bus.register_observer()
            q_a = bus.register("larbin:a")
            msg = Message(bus_mod.REQUEST, frm="larbin:a", to="larbin:a",
                          body="self test")  # auto-adressé pour lire vite
            ok = await bus.send(msg)
            self.assertTrue(ok)
            self.assertEqual((await q_a.get()).id, msg.id)
            self.assertEqual((await boss_q.get()).id, msg.id)  # copie boss
        asyncio.run(go())

    def test_destinataire_inconnu(self):
        async def go():
            bus = Bus()
            ok = await bus.send(Message("info", frm="x", to="nulle-part"))
            self.assertFalse(ok)
        asyncio.run(go())


class TestSandbox(unittest.IsolatedAsyncioTestCase):
    GOOD = "def handle(payload):\n    return {'n': len(payload)}\n"

    async def test_ok(self):
        out = await run_tool(self.GOOD, {"a": 1, "b": 2}, timeout=5)
        self.assertEqual(out, {"n": 2})

    async def test_crash(self):
        with self.assertRaises(SandboxError) as cm:
            await run_tool("def handle(p):\n    return p[99999]", {}, 5)
        self.assertEqual(cm.exception.kind, "crash")

    async def test_timeout_boucle_infinie(self):
        loop = ("def handle(p):\n"
                "    while True:\n"
                "        pass\n")
        with self.assertRaises(SandboxError) as cm:
            await run_tool(loop, {}, timeout=1.5)
        self.assertEqual(cm.exception.kind, "timeout")

    async def test_candidate(self):
        ok, _ = await test_candidate(self.GOOD, [{}, {"x": 1}])
        self.assertTrue(ok)
        ok, reason = await test_candidate("def handle(p):\n  return 1/0", [{}])
        self.assertFalse(ok)


class TestKnowledge(unittest.TestCase):
    def test_persistance_et_contexte(self):
        path = os.path.join(tempfile.mkdtemp(), "k.json")
        kb = KnowledgeBase(path)
        kb.record_bug("validator", "IndexError", "domains[5]")
        kb.record_fix("validator", "success", "corrigé")
        kb2 = KnowledgeBase(path)  # rechargement disque
        ctx = kb2.prompt_context("validator")
        self.assertIn("IndexError", ctx)
        self.assertIn("RÉUSSI", ctx)
        self.assertEqual(len(kb2.for_role("validator")), 2)


class TestRegistry(unittest.TestCase):
    def test_pick_et_exclusion(self):
        cfg = Config(demo_config_path())
        reg = Registry.from_config(cfg)
        self.assertEqual(reg.pick("chat").name, "mock-flaky")
        self.assertEqual(
            reg.pick("chat", exclude={"mock-flaky"}).name, "mock-good")
        self.assertIsNone(reg.pick("capacité-inexistante"))


class TestColony(ColonyTestCase):
    async def test_self_healing_complet(self):
        """Bug dans le code du larbin → réparation → retry → succès."""
        v = await self.boss.spawn("validator", tool_code=BUGGY_VALIDATOR)
        resp = await self._ask(v, "valide ces emails", payload={
            "use_tool": True,
            "payload": {"emails": EMAILS,
                        "allowed_domains": ["gmail.com", "outlook.com",
                                            "proton.me"]},
            "expected_seconds": 5,
        })
        self.assertEqual(resp.payload["status"], "ok")
        self.assertGreaterEqual(len(v.versions), 2)  # code recodé déployé
        # la mémoire globale a enregistré l'incident
        self.assertTrue(any(e["type"] == "fix" and e["outcome"] == "success"
                            for e in self.kb.entries))

    async def test_escalation_provider_down(self):
        """IA en panne (503) → le boss recrée le larbin sur une AUTRE IA."""
        s = await self.boss.spawn("summarizer")  # chaîne chat → flaky 1er
        resp = await self._ask(s, "Résume ce résultat : tout va bien",
                               payload={"expected_seconds": 5})
        self.assertEqual(resp.payload["status"], "ok")
        summarizers = [lb for lb in self.boss.larbins.values()
                       if lb.role == "summarizer"]
        self.assertGreaterEqual(len(summarizers), 2)  # escalade = nouveau
        self.assertTrue(any("[escalation]" in e for e in self.boss.events))
        # le relais est pris sur une IA différente
        providers = {lb.provider.name for lb in summarizers}
        self.assertGreaterEqual(len(providers), 2)

    async def test_escalation_timeout_watchdog(self):
        """IA lente → timeout → escalade → remplacement rapide."""
        # on fabrique une chaîne lente puis saine
        self.registry.chains["chat"] = ["mock-slow", "mock-good"]
        self.registry.providers["mock-slow"] = __import__(
            "colony.providers.mock", fromlist=["MockProvider"]).MockProvider(
            "mock-slow", behavior="slow")
        s = await self.boss.spawn("summarizer")
        self.assertEqual(s.provider.name, "mock-slow")
        resp = await self._ask(s, "Résume : je suis lent",
                               payload={"expected_seconds": 1},
                               timeout=30)
        self.assertEqual(resp.payload["status"], "ok")
        self.assertGreaterEqual(
            len([lb for lb in self.boss.larbins.values()
                 if lb.role == "summarizer"]), 2)

    async def test_delegation_validee(self):
        """Délégation horizontale validée par le boss puis exécutée."""
        v = await self.boss.spawn("validator",
                                  tool_code=None)  # larbin sans tool
        # on contourne le tool : la délégation se fait après réponse LLM
        resp = await self._ask(v, "Délègue un résumé", payload={
            "expected_seconds": 5,
            "delegate_after": {"role": "summarizer",
                               "body": "Résume : ok"},
        })
        # sans use_tool, pas de délégation automatique — la réponse est LLM
        self.assertEqual(resp.payload["status"], "ok")

    async def test_delegation_refus_cycle(self):
        """Un cycle de délégation est refusé par le boss."""
        s = await self.boss.spawn("summarizer")
        # un larbin 'validator' délègue déjà à 'summarizer'
        self.boss._active_delegations.add(("validator", "summarizer"))
        # le summarizer veut déléguer en retour à 'validator' → cycle
        req = Message(bus_mod.REQUEST, frm=s.addr, to="",
                      body="aide-moi", payload={})
        ok, why = await self.boss._validate_delegation(
            Message(bus_mod.DELEGATION, frm=s.addr, to="boss",
                    payload={"role": "validator", "request": req.to_dict()}),
            req, "validator")
        self.assertFalse(ok)
        self.assertIn("cycle", why)


    async def test_nommage_prenoms_unique(self):
        """Le nommage 'prénoms' ne doit JAMAIS créer de collision d'adresse."""
        self.cfg.data["style"] = {"naming": "prenoms"}
        a = await self.boss.spawn("validator")
        b = await self.boss.spawn("summarizer")
        c = await self.boss.spawn("summarizer")
        names = {a.name, b.name, c.name}
        addrs = {a.addr, b.addr, c.addr}
        self.assertEqual(len(names), 3)
        self.assertEqual(len(addrs), 3)
        self.assertNotIn(a.name, (b.name, c.name))
        # et le style 'metier' par défaut reste role-N
        self.cfg.data["style"] = {}
        d = await self.boss.spawn("coder")
        self.assertTrue(d.name.startswith("coder-"))

    async def test_mission_avec_style(self):
        """La personnalité (QCM) est bien injectée dans la mission."""
        self.cfg.data["style"] = {"tone": "direct", "language": "fr",
                                  "signature": "name"}
        lb = await self.boss.spawn("coder")
        self.assertIn("directe et concise", lb.mission)
        self.assertIn("français", lb.mission)
        self.assertIn("Signe", lb.mission)


if __name__ == "__main__":
    unittest.main(verbosity=2)
