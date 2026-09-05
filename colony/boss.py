"""Le Boss : orchestrateur de la colonie.

Voir tout, tout décider :
- reçoit une COPIE de chaque message du bus (mesh supervisé),
- crée les larbins dynamiquement (sur l'IA de la bonne chaîne),
- WATCHDOG : si une demande traîne au-delà du délai attendu, il recrée le
  larbin fautif sur une AUTRE IA (jamais la même — règle d'Adam),
- valide les délégations horizontales (règles + option LLM),
- gère la file de réparation (priorités) avec le Larbin Réparateur,
- répond en échec propre quand tout a échoué (jamais de blocage infini).
"""
from __future__ import annotations

import asyncio
import itertools
import time

from . import bus as bus_mod
from .bus import BOSS, Bus, Message
from .config import Config
from .knowledge import KnowledgeBase
from .larbin import Larbin
from .log import log
from .repairer import Repairer

ROLE_TEMPLATES: dict[str, dict] = {
    "validator": {
        "capability": "validator",
        "mission": ("Tu es un larbin valideur. Tu vérifies des données et "
                    "commentes la qualité d'un résultat de façon claire et "
                    "concise, en français."),
    },
    "summarizer": {
        "capability": "chat",
        "mission": ("Tu es un larbin rédacteur. Tu résumes des résultats de "
                    "façon concise et utile, en français."),
    },
    "coder": {
        "capability": "coder",
        "mission": ("Tu es un larbin codeur Python senior. Tu écris du code "
                    "propre avec des noms explicites et des docstrings. Tu "
                    "réponds avec des blocs de code."),
    },
    "reviewer": {
        "capability": "chat",
        "mission": ("Tu es un larbin reviewer. Tu relis du code ou des "
                    "résultats et tu signales les problèmes importants."),
    },
    "generic": {
        "capability": "chat",
        "mission": ("Tu es un larbin polyvalent de la colonie. Tu fais ce "
                    "qu'on te demande, clairement, en français."),
    },
}

# Styles de nommage (QCM Q5)
NAME_POOLS: dict[str, list[str]] = {
    "prenoms": ["alfred", "jeeves", "edmund", "sebastian", "remy", "igor",
                "basile", "octave", "prosper", "gaspard"],
    "callsigns": ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot",
                  "golf", "hotel", "india", "juliett"],
}

# Tons des larbins et du boss (QCM Q1/Q7)
TONES: dict[str, str] = {
    "direct": "Réponds de façon directe et concise (1 à 3 phrases), sans blabla.",
    "chatty": "Tu es bavard et sympathique : explique brièvement ton raisonnement "
              "et ajoute une remarque utile.",
    "formel": "Tu t'exprimes de façon polie et formelle, comme dans un rapport.",
    "militaire": "Tu réponds sur un ton militaire : phrases très courtes, "
                 "précises, efficaces.",
}
LANGS: dict[str, str] = {
    "fr": "Tu réponds toujours en français.",
    "en": "Always answer in English.",
    "auto": "Réponds dans la langue de la demande.",
}
OUTPUT_FORMATS: dict[str, str] = {
    "text": "Réponds en texte libre lisible (pas de JSON sauf demande explicite).",
    "json": "Quand c'est possible, structure ta réponse en JSON valide.",
    "auto": "Pour un humain : texte libre. Pour un autre larbin : JSON valide "
            "si tu peux.",
}


def style_mission(base_mission: str, style: dict, larbin_name: str) -> str:
    """Ajoute la personnalité (QCM) à la mission de base d'un larbin."""
    parts = [base_mission]
    tone = style.get("tone", "")
    if tone in TONES:
        parts.append(TONES[tone])
    lang = style.get("language", "")
    if lang in LANGS:
        parts.append(LANGS[lang])
    fmt = style.get("output_format", "")
    if fmt in OUTPUT_FORMATS:
        parts.append(OUTPUT_FORMATS[fmt])
    sig = style.get("signature", "none")
    if sig == "name":
        parts.append(f"Signe chacune de tes réponses par « — {larbin_name} ».")
    elif sig == "emoji":
        parts.append("Termine chaque réponse par un emoji qui reflète ton humeur.")
    return " ".join(parts)


class Boss:
    def __init__(self, registry, bus: Bus, cfg: Config,
                 knowledge: KnowledgeBase | None = None):
        self.registry = registry
        self.bus = bus
        self.cfg = cfg
        self.knowledge = knowledge or KnowledgeBase()
        self.observer = bus.register_observer()
        self.larbins: dict[str, Larbin] = {}
        # request_id -> suivi pour le watchdog
        self.pending: dict[str, dict] = {}
        self.repair_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._seq = itertools.count()
        self._pool_seq = itertools.count(1)   # noms uniques (quiz Q5)
        self._spawn_count: dict[str, int] = {}
        self._active_delegations: set[tuple[str, str]] = set()
        self.events: list[str] = []   # journal des événements clés
        self.repairer = Repairer(registry, self.knowledge, cfg)
        self._tasks: list[asyncio.Task] = []

    # ---------------------------------------------------------- cycle de vie
    async def start(self) -> None:
        self._tasks.append(asyncio.create_task(self._run(), name="boss-loop"))
        self._tasks.append(asyncio.create_task(self._watchdog(),
                                               name="boss-watchdog"))
        self._tasks.append(asyncio.create_task(self._repair_loop(),
                                               name="boss-repair"))
        log("boss", "👑 boss en ligne — je vois tout, watchdog actif, "
                    "réparateur prêt", "👑")

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for lb in self.larbins.values():
            await lb.stop()

    def _event(self, kind: str, text: str) -> None:
        self.events.append(f"{time.strftime('%H:%M:%S')} [{kind}] {text}")

    # --------------------------------------------------------------- spawn --
    async def spawn(self, role: str, capability: str | None = None,
                    mission: str | None = None, provider_name: str | None = None,
                    exclude: tuple | set = (), tool_code: str | None = None,
                    expected_seconds: float = 15.0,
                    reason: str = "") -> Larbin:
        tpl = ROLE_TEMPLATES.get(role, ROLE_TEMPLATES["generic"])
        cap = capability or tpl["capability"]
        provider = None
        if provider_name:
            provider = self.registry.get(provider_name)
        else:
            provider = self.registry.pick(cap, exclude)
            if provider is None:
                provider = self.registry.pick(cap)  # dernière chance
        if provider is None:
            raise RuntimeError(
                f"aucun provider disponible pour la capacité '{cap}' "
                f"(exclus : {sorted(exclude) or 'aucun'})")
        n = self._spawn_count.get(role, 0) + 1
        self._spawn_count[role] = n
        naming = self.cfg.style.get("naming", "metier")
        pool = NAME_POOLS.get(naming)
        if pool:
            # compteur GLOBAL : chaque larbin né prend le prénom suivant,
            # quel que soit son rôle (sinon 2 rôles → même nom → collision
            # d'adresse sur le bus !)
            g = next(self._pool_seq)
            name = f"{pool[(g - 1) % len(pool)]}-{g}"
        else:
            name = f"{role}-{n}"
        base, i = name, 2
        while f"larbin:{name}" in self.larbins:
            name = f"{base}-{i}"
            i += 1
        lb = Larbin(name=name, role=role, capability=cap,
                    mission=mission or style_mission(tpl["mission"],
                                                     self.cfg.style, name),
                    provider=provider,
                    bus=self.bus, config=self.cfg, tool_code=tool_code,
                    expected_seconds=expected_seconds)
        self.larbins[lb.addr] = lb
        await lb.start()
        why = f" ({reason})" if reason else ""
        self._event("spawn", f"{name} créé sur IA={provider.name}{why}")
        return lb

    # ------------------------------------------------------------ main loop -
    async def _run(self) -> None:
        while True:
            msg = await self.observer.get()
            try:
                await self._dispatch(msg)
            except Exception as e:  # noqa: BLE001
                log("boss", f"💥 erreur de dispatch : {e!r}", "💥")

    async def _dispatch(self, msg: Message) -> None:
        if msg.type == bus_mod.REQUEST:
            await self._track_request(msg)
        elif msg.type == bus_mod.RESPONSE:
            entry = self.pending.pop(msg.reply_to, None) if msg.reply_to else None
            if entry and entry.get("delegation_pair"):
                self._active_delegations.discard(entry["delegation_pair"])
        elif msg.type == bus_mod.ERROR and msg.to == BOSS:
            await self._handle_error(msg)
        elif msg.type == bus_mod.ESCALATION and msg.to == BOSS:
            await self._handle_escalation(
                msg.payload.get("reason", "?"),
                Message.from_dict(msg.payload.get("request", {})))
        elif msg.type == bus_mod.DELEGATION and msg.to == BOSS:
            await self._handle_delegation(msg)
        elif msg.type == bus_mod.REPAIR_REQUEST and msg.to == BOSS:
            await self.repair_queue.put((msg.priority, next(self._seq), msg))
        elif msg.type == bus_mod.INFO:
            if self.cfg.style.get("verbosity", "normal") != "minimal":
                log("boss", f"👁️ {msg.frm} : {msg.body[:110]}", "👁️")

    # ------------------------------------------------------------ tracking --
    def _deadline_for(self, req: Message) -> float:
        expected = req.payload.get("expected_seconds", 30)
        return time.monotonic() + float(expected) * self.cfg.watchdog_factor

    async def _track_request(self, msg: Message) -> None:
        entry = self.pending.get(msg.id)
        if entry:
            # réacheminement (escalade) : nouvelle cible, nouveau délai
            entry["target"] = msg.to
            entry["deadline"] = self._deadline_for(msg)
            return
        self.pending[msg.id] = {
            "requester": msg.frm, "target": msg.to,
            "deadline": self._deadline_for(msg),
            "original": msg, "escalations": 0,
            "delegation_pair": None,
        }

    # -------------------------------------------------------------- erreurs -
    async def _handle_error(self, msg: Message) -> None:
        req = Message.from_dict(msg.payload.get("request", {}))
        entry = self.pending.get(req.id) or self._rebuild_entry(req)
        classification = msg.payload.get("classification", "PROVIDER_DOWN")
        provider_name = msg.payload.get("provider", "?")
        log("boss", f"🚨 {msg.frm} signale {classification} sur "
                    f"{provider_name} (demande {req.id[:8]})", "🚨")
        if classification in ("PROVIDER_DOWN", "RATE_LIMIT", "AUTH",
                              "TIMEOUT"):
            await self._escalate(entry, exclude={provider_name},
                                 reason=f"{classification} sur {provider_name}")
        else:
            await self._fail(entry, msg.payload.get("detail", "erreur"))

    async def _handle_escalation(self, reason: str, req: Message) -> None:
        if not req.id:
            return
        entry = self.pending.get(req.id) or self._rebuild_entry(req)
        await self._escalate(entry, reason=reason)

    def _rebuild_entry(self, req: Message) -> dict:
        self.pending[req.id] = {
            "requester": req.frm, "target": req.to,
            "deadline": self._deadline_for(req),
            "original": req, "escalations": 0,
            "delegation_pair": None,
        }
        return self.pending[req.id]

    # ----------------------------------------------------------- escalade ---
    async def _escalate(self, entry: dict, exclude: set | frozenset = frozenset(),
                        reason: str = "") -> None:
        if entry["escalations"] >= self.cfg.max_escalations:
            await self._fail(entry, f"trop d'escalades — {reason}")
            return
        req = entry["original"]
        target = self.larbins.get(entry["target"])
        old_provider = target.provider.name if target else ""
        exclude = set(exclude) | ({old_provider} if old_provider else set())
        role = target.role if target else "generic"
        cap = target.capability if target else "chat"
        mission = target.mission if target else None
        tool = target.tool_code if target else None
        try:
            new = await self.spawn(role, capability=cap, mission=mission,
                                   exclude=exclude, tool_code=tool,
                                   reason=reason)
        except RuntimeError as e:
            await self._fail(entry, str(e))
            return
        entry["escalations"] += 1
        entry["deadline"] = self._deadline_for(req)
        forwarded = Message.from_dict(req.to_dict())
        forwarded.to = new.addr
        await self.bus.send(forwarded)
        self._event("escalation",
                    f"{reason} → {new.name} recréé sur {new.provider.name} "
                    f"(exclus : {sorted(exclude)})")
        log("boss", f"🔁 escalade : {new.name} prend le relais sur "
                    f"IA={new.provider.name} — {reason}", "🔁")

    async def _fail(self, entry: dict, reason: str) -> None:
        req = entry["original"]
        self.pending.pop(req.id, None)
        await self.bus.send(Message(
            bus_mod.RESPONSE, frm=BOSS, to=entry["requester"],
            reply_to=req.id, task_id=req.task_id,
            body=f"échec définitif : {reason}",
            payload={"status": "failed", "reason": reason}))
        self._event("fail", f"demande {req.id[:8]} échouée : {reason}")
        log("boss", f"❌ échec définitif de {req.id[:8]} : {reason}", "❌")

    # ------------------------------------------------------------ watchdog --
    async def _watchdog(self) -> None:
        """Le chien de garde : aucune demande ne peut traîner indéfiniment."""
        while True:
            await asyncio.sleep(1.0)
            now = time.monotonic()
            for rid, entry in list(self.pending.items()):
                if entry["deadline"] < now:
                    # dépassé → escalade (le compteur d'escalades protège
                    # contre les boucles infinies)
                    await self._handle_escalation(
                        "watchdog : larbin bloqué/absent", entry["original"])

    # ---------------------------------------------------------- délégation --
    def _role_of(self, addr: str) -> str:
        lb = self.larbins.get(addr)
        return lb.role if lb else addr

    async def _handle_delegation(self, msg: Message) -> None:
        req = Message.from_dict(msg.payload.get("request", {}))
        role = msg.payload.get("role", "generic")
        ok, why = await self._validate_delegation(msg, req, role)
        if not ok:
            self._event("delegation", f"refusée : {why}")
            log("boss", f"🚫 délégation refusée ({msg.frm} → {role}) : {why}",
                "🚫")
            await self.bus.send(Message(
                bus_mod.RESPONSE, frm=BOSS, to=msg.frm, reply_to=req.id,
                body=f"délégation refusée : {why}",
                payload={"status": "failed", "reason": why}))
            return
        # cible : un larbin existant du même rôle et disponible, sinon création
        target = None
        if self.cfg.delegation_reuse == "reuse":
            for lb in self.larbins.values():
                if lb.role == role and lb.status == "idle":
                    target = lb
                    break
        if target is None:
            target = await self.spawn(role, reason=f"délégation de {msg.frm}")
        pair = (self._role_of(msg.frm), role)
        self._active_delegations.add(pair)
        forwarded = Message.from_dict(req.to_dict())
        forwarded.to = target.addr
        await self.bus.send(forwarded)
        entry = self.pending.get(forwarded.id)
        if entry:
            entry["delegation_pair"] = pair
        self._event("delegation",
                    f"{msg.frm} → {target.name} validée ({why})")
        log("boss", f"✅ délégation validée : {msg.frm} → {target.name} "
                    f"({role})", "✅")

    async def _validate_delegation(self, msg: Message, req: Message,
                                   role: str) -> tuple[bool, str]:
        if not req.body or not req.body.strip():
            return False, "corps de la demande vide"
        if req.frm != msg.frm:
            return False, "usurpation d'identité (expéditeur ≠ demandeur)"
        cap = ROLE_TEMPLATES.get(role, ROLE_TEMPLATES["generic"])["capability"]
        if self.registry.pick(cap) is None:
            return False, f"aucune IA disponible pour la capacité '{cap}'"
        frm_role = self._role_of(msg.frm)
        if (frm_role, role) in self._active_delegations or \
           (role, frm_role) in self._active_delegations:
            return False, "cycle de délégation détecté (A→B et B→A)"
        if self.cfg.delegation_validation == "llm":
            provider = (self.registry.pick("boss")
                        or self.registry.pick("chat"))
            if provider is not None:
                try:
                    out = await provider.chat(
                        "Tu es le boss d'une colonie d'agents. Réponds "
                        "uniquement OUI ou NON.",
                        f"Le larbin '{msg.frm}' (rôle {frm_role}) veut "
                        f"déléguer au rôle '{role}' : « {req.body[:300]} ». "
                        f"Cette délégation est-elle justifiée ?",
                        max_tokens=4, temperature=0.0)
                    if "OUI" in out.upper():
                        return True, "validée par le boss (LLM)"
                    return False, f"refusée par le boss : {out.strip()[:60]}"
                except Exception:  # noqa: BLE001
                    pass  # IA indisponible → on retombe sur les règles
        return True, "règles ok"

    # -------------------------------------------------------- réparation ---
    async def _repair_loop(self) -> None:
        while True:
            prio, _, msg = await self.repair_queue.get()
            payload = msg.payload
            larbin = self.larbins.get(payload.get("larbin", ""))
            if larbin is None:
                continue
            log("boss", f"🩹 réparation de {larbin.name} "
                        f"(priorité {prio})", "🩹")
            try:
                outcome = await self.repairer.fix(
                    larbin_role=larbin.role,
                    code=payload.get("code", ""),
                    error=payload.get("error", ""),
                    detail=payload.get("detail", ""),
                    test_payload=payload.get("payload", {}))
            except Exception as e:  # noqa: BLE001
                outcome = {"ok": False, "reason": f"réparateur HS : {e}"}
            if outcome.get("ok"):
                larbin.deploy(outcome["code"])
                self._event("repair", f"{larbin.name} recodé avec succès → "
                                      f"v{len(larbin.versions)}")
                await self.bus.send(Message(
                    bus_mod.REPAIR_DONE, frm=BOSS, to=larbin.addr,
                    reply_to=msg.id, body="code réparé et testé ✅",
                    payload={"ok": True, "code": outcome["code"]}))
            else:
                larbin.repair_attempts += 1
                give_up = larbin.repair_attempts >= self.cfg.max_repairs
                self._event("repair",
                            f"{larbin.name} : candidat rejeté "
                            f"({str(outcome.get('reason'))[:80]})"
                            + (" → ABANDON" if give_up else " → nouvelle "
                                                          "tentative avec mémoire"))
                await self.bus.send(Message(
                    bus_mod.REPAIR_DONE, frm=BOSS, to=larbin.addr,
                    reply_to=msg.id,
                    body=("abandon de la réparation" if give_up
                          else "candidat rejeté — retente avec la mémoire"),
                    payload={"ok": False, "give_up": give_up,
                             "reason": outcome.get("reason", "")}))
