"""Le Larbin : un sous-agent de la colonie.

Un larbin a :
- un rôle (validator, summarizer, coder...) et une mission (prompt système),
- une IA (provider) qui lui sert de cerveau,
- OPTIONNELLEMENT du code Python (`handle(payload) -> dict`) exécuté en
  sandbox — c'est ce code qui peut être auto-réparé (self-healing),
- une boîte aux lettres sur le bus ; il parle directement aux autres larbins
  (le boss reçoit une copie de tout).

Mécanismes clés (design validé avec Adam) :
- request/response avec timeout → si pas de réponse, escalade au boss qui
  recrée le larbin sur une AUTRE IA,
- self-healing : rollback vers le code précédent d'abord, puis réparation
  par le Larbin Réparateur (avec mémoire des bugs),
- délégation horizontale validée par le boss.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid

from . import bus as bus_mod
from .bus import BOSS, Bus, Message
from .config import Config
from .log import log
from .providers.base import Provider, ProviderError, ResponseFormatError
from .sandbox import SandboxError, run_tool
from .util import extract_json_block


class RequestFailed(Exception):
    """La demande a échoué, même après escalades / réparations."""


class Larbin:
    def __init__(self, name: str, role: str, capability: str, mission: str,
                 provider: Provider, bus: Bus, config: Config,
                 tool_code: str | None = None, expected_seconds: float = 15.0):
        self.lid = uuid.uuid4().hex[:6]
        self.name = name
        self.addr = f"larbin:{name}"
        self.role = role
        self.capability = capability
        self.mission = mission
        self.provider = provider
        self.bus = bus
        self.cfg = config
        self.mailbox = bus.register(self.addr)
        self._waits: dict[str, asyncio.Future] = {}
        self._task: asyncio.Task | None = None
        self.history: list[dict] = []          # mémoire de conversation (LLM)
        self.versions: list[str] = [tool_code] if tool_code else []
        self.expected_seconds = expected_seconds
        self.repair_attempts = 0
        self.status = "idle"
        self.stats = {"requests": 0, "errors": 0, "repairs": 0}

    # ------------------------------------------------------------ code ----
    @property
    def tool_code(self) -> str | None:
        return self.versions[-1] if self.versions else None

    def deploy(self, code: str) -> None:
        """Déploie une nouvelle version (après validation sandbox)."""
        self.versions.append(code)
        drop = len(self.versions) - self.cfg.max_versions
        if drop > 0:
            del self.versions[:drop]
        self.stats["repairs"] += 1
        self.repair_attempts = 0
        log(self.name, f"✅ nouvelle version déployée (v{len(self.versions)}), "
                       f"testée au sandbox", "🩹")

    def rollback(self) -> None:
        """Revient au code précédent (si le nouveau code est pire)."""
        if len(self.versions) > 1:
            self.versions.pop()
            log(self.name, f"🔄 rollback vers v{len(self.versions)} "
                           f"(code précédent restauré)", "🔄")

    # ---------------------------------------------------------- cycle de vie
    async def start(self) -> None:
        self._task = asyncio.create_task(self.run(), name=self.addr)
        await self.bus.send(Message(
            bus_mod.INFO, frm=self.addr, to=BOSS,
            body=f"larbin '{self.name}' en ligne (rôle={self.role}, "
                 f"IA={self.provider.name}/{self.provider.model})"))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        self.bus.unregister(self.addr)

    # ----------------------------------------------------------- run loop --
    async def run(self) -> None:
        try:
            while True:
                msg = await self.mailbox.get()
                if msg.type in (bus_mod.RESPONSE, bus_mod.REPAIR_DONE):
                    fut = self._waits.get(msg.reply_to or "")
                    if fut is not None and not fut.done():
                        fut.set_result(msg)
                    continue
                if msg.type == bus_mod.REQUEST:
                    asyncio.create_task(self._safe_handle(msg))
        except asyncio.CancelledError:
            pass

    async def _safe_handle(self, msg: Message) -> None:
        try:
            await self._handle_request(msg)
        except Exception as e:  # filet de sécurité : un larbin ne meurt jamais
            log(self.name, f"💥 handler crashé: {e!r}", "💥")

    # -------------------------------------------------------- requêtes -----
    def _register_wait(self, wait_id: str) -> asyncio.Future:
        fut = asyncio.get_running_loop().create_future()
        self._waits[wait_id] = fut
        return fut

    async def wait_reply(self, reply_to: str, timeout: float) -> Message:
        """Attend une réponse (une seule fois — pour les réparations)."""
        fut = self._register_wait(reply_to)
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self._waits.pop(reply_to, None)

    async def request(self, to: str, body: str, payload: dict | None = None,
                      timeout: float | None = None,
                      delegation_role: str | None = None) -> Message:
        """Envoie une demande et attend la réponse (avec escalades).

        Si `delegation_role` est fourni, la demande passe par le boss
        (validation), sinon elle part directement au destinataire.
        """
        timeout = timeout or self.cfg.request_timeout
        m = Message(bus_mod.REQUEST, frm=self.addr, to=to, body=body,
                    payload=payload or {}, priority=self.cfg.default_priority)
        if delegation_role:
            d = Message(bus_mod.DELEGATION, frm=self.addr, to=BOSS,
                        payload={"role": delegation_role, "request": m.to_dict()})
            await self.bus.send(d)
        else:
            await self.bus.send(m)

        hard = time.monotonic() + timeout * self.cfg.grace_factor
        fut = self._register_wait(m.id)
        escalated = 0
        try:
            while True:
                remaining = hard - time.monotonic()
                if remaining <= 0:
                    raise RequestFailed(f"aucune réponse pour {m.id} "
                                        f"(délai global dépassé)")
                done, _ = await asyncio.wait({fut},
                                             timeout=min(timeout, remaining))
                if done:
                    return fut.result()
                # timeout local → on prévient le boss (il gère l'escalade)
                if escalated < self.cfg.max_escalations:
                    escalated += 1
                    log(self.name, f"⏱️ pas de réponse de '{to or delegation_role}' "
                                   f"en {timeout}s → escalade n°{escalated} au boss",
                        "⏱️")
                    await self.bus.send(Message(
                        bus_mod.ESCALATION, frm=self.addr, to=BOSS,
                        payload={"reason": f"timeout {timeout}s",
                                 "request": m.to_dict()}))
                else:
                    await asyncio.sleep(min(2.0, max(0.2, remaining)))
        finally:
            self._waits.pop(m.id, None)

    # ------------------------------------------------------- traitement ----
    async def _handle_request(self, req: Message) -> None:
        self.stats["requests"] += 1
        self.status = "working"
        log(self.name, f"📥 demande reçue : {req.body[:100]}", "📥")
        try:
            if req.payload.get("use_tool") and self.tool_code:
                result = await self._run_tool_with_healing(req)
            else:
                result = await self._ask_llm(req)
            # délégation éventuelle après le travail principal
            deleg = req.payload.get("delegate_after")
            if isinstance(deleg, dict) and deleg:
                result = await self._delegate_then_merge(deleg, result)
            await self._respond(req, ok=True, result=result)
        except RequestFailed as e:
            await self._respond(req, ok=False, reason=str(e))
        except (ProviderError, ResponseFormatError) as e:
            self.stats["errors"] += 1
            classification = (e.classification() if isinstance(e, ProviderError)
                              else "PROVIDER_DOWN")
            log(self.name, f"🔴 mon IA ({self.provider.name}) est HS "
                           f"({classification}) → je préviens le boss", "🔴")
            await self.bus.send(Message(
                bus_mod.ERROR, frm=self.addr, to=BOSS, reply_to=req.id,
                payload={"classification": classification,
                         "provider": self.provider.name,
                         "detail": str(e)[:300],
                         "request": req.to_dict()}))
        except Exception as e:  # noqa: BLE001
            self.stats["errors"] += 1
            log(self.name, f"💥 imprévu : {e!r}", "💥")
            await self._respond(req, ok=False, reason=f"erreur imprévue: {e}")
        finally:
            self.status = "idle"

    async def _respond(self, req: Message, ok: bool, result=None,
                       reason: str = "") -> None:
        payload: dict = {"status": "ok" if ok else "failed"}
        if ok:
            payload["result"] = result
        else:
            payload["reason"] = reason
        body = (str(result)[:1200] if ok else f"échec : {reason}")[:1200]
        await self.bus.send(Message(
            bus_mod.RESPONSE, frm=self.addr, to=req.frm, reply_to=req.id,
            task_id=req.task_id, body=body, payload=payload))

    # ----------------------------------------------------------- LLM -------
    async def _ask_llm(self, req: Message):
        user = req.body
        if req.payload:
            user += ("\n\nDonnées (JSON) :\n"
                     + json.dumps(req.payload, ensure_ascii=False)[:3000])
        self.history.append({"role": "user", "content": user})
        hist = self.history[-self.cfg.conversation_memory:]
        if len(hist) > 1:
            prompt = "\n\n".join(f"[{h['role']}]\n{h['content']}" for h in hist)
        else:
            prompt = user
        out = await self.provider.chat(self.mission, prompt,
                                       max_tokens=2048, temperature=0.3)
        self.history.append({"role": "assistant", "content": out})
        parsed = extract_json_block(out)
        return parsed if parsed is not None else out

    # -------------------------------------------------- tool + self-heal ---
    async def _run_tool_with_healing(self, req: Message):
        payload = req.payload.get("payload", {})
        attempts = 0
        while True:
            try:
                result = await run_tool(self.tool_code, payload,
                                        timeout=self.cfg.sandbox_timeout)
                break
            except SandboxError as e:
                attempts += 1
                if attempts > self.cfg.max_repairs:
                    raise RequestFailed(
                        f"self-healing épuisé ({self.cfg.max_repairs} "
                        f"tentatives), dernière erreur: {e}")
                log(self.name, f"💥 bug dans mon code ({e.kind}) — "
                               f"tentative {attempts}/{self.cfg.max_repairs}",
                    "🩹")
                # 1) rollback d'abord : peut-être que la version précédente
                #    marchait (le nouveau code a introduit le bug)
                if (self.cfg.rollback_policy == "always"
                        and len(self.versions) > 1):
                    self.rollback()
                    try:
                        result = await run_tool(self.tool_code, payload,
                                                timeout=self.cfg.sandbox_timeout)
                        break
                    except SandboxError:
                        pass  # l'ancien code plante aussi → réparation
                # 2) réparation par le boss (Fable 5.1 + mémoire des bugs)
                fixed = await self._request_repair(req, e)
                if not fixed:
                    raise RequestFailed("réparation abandonnée")
        return result

    async def _request_repair(self, req: Message, err: SandboxError) -> bool:
        self.status = "repairing"
        rr = Message(
            bus_mod.REPAIR_REQUEST, frm=self.addr, to=BOSS, priority=0,
            payload={"larbin": self.addr, "role": self.role,
                     "code": self.tool_code, "error": err.kind,
                     "detail": err.detail, "request_id": req.id,
                     "payload": req.payload.get("payload", {})})
        await self.bus.send(rr)
        try:
            done = await self.wait_reply(rr.id, self.cfg.repair_timeout)
        except asyncio.TimeoutError:
            log(self.name, "⚠️ le réparateur n'a pas répondu à temps", "⚠️")
            return False
        return bool(done.payload.get("ok"))

    async def _delegate_then_merge(self, deleg: dict, tool_result):
        role = deleg.get("role", "generic")
        body = deleg.get("body", "Voici un résultat, traite-le.")
        log(self.name, f"📤 délégation vers un larbin '{role}' "
                       f"(validation par le boss)", "📤")
        try:
            resp = await self.request(to="", body=body,
                                      payload={"input": tool_result},
                                      timeout=self.cfg.request_timeout,
                                      delegation_role=role)
        except RequestFailed as e:
            return {"work": tool_result, "summary": None,
                    "delegation": f"échouée : {e}"}
        if resp.payload.get("status") != "ok":
            return {"work": tool_result, "summary": None,
                    "delegation": f"refusée : {resp.payload.get('reason', '?')}"}
        summary = resp.payload.get("result") or resp.body
        return {"work": tool_result, "summary": summary, "delegation": "ok"}
