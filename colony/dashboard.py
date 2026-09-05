"""Dashboard web live de la colonie — zéro dépendance.

- Serveur HTTP asyncio intégré (stdlib uniquement), bind 0.0.0.0
- GET  /               → l'interface (colony/static/dashboard.html)
- GET  /api/state      → instantané complet (larbins, providers, événements…)
- GET  /api/messages   → derniers messages du bus
- GET  /api/events     → flux SSE temps réel (messages + état)
- POST /api/task       → donne une tâche à un larbin DEPUIS le navigateur
- POST /api/scenario   → lance le scénario complet (self-healing + délégation
                         + escalade multi-IA) en direct

Lancement :
    python3 -m colony.cli dashboard            # tes IAs du .env (fallback mocks)
    python3 -m colony.cli dashboard --mock     # mode démo sans clé
    python3 -m colony.cli dashboard --port 8420 --config config.perso.json
"""
from __future__ import annotations

import asyncio
import json
import os
import time

from . import bus as bus_mod
from .bus import BOSS, Bus, Message
from .config import Config, demo_config_path
from .knowledge import KnowledgeBase
from .log import log
from .providers.registry import Registry

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class Dashboard:
    def __init__(self, boss, bus: Bus, registry: Registry, cfg: Config,
                 kb: KnowledgeBase, mode: str, config_path: str):
        self.boss = boss
        self.bus = bus
        self.registry = registry
        self.cfg = cfg
        self.kb = kb
        self.mode = mode
        self.config_path = config_path
        self.started = time.time()
        self.observer = bus.register_observer()
        self.human = bus.register("human")
        self.tasks: dict[str, dict] = {}
        self.sse_clients: list[asyncio.Queue] = []
        self.scenario_running = False
        self._bg: list[asyncio.Task] = []
        self._server: asyncio.base_events.Server | None = None
        self.port: int | None = None

    # ------------------------------------------------------------- cycle --
    async def start(self, port: int) -> None:
        self._bg.append(asyncio.create_task(self._consume(), name="dash-msgs"))
        self._bg.append(asyncio.create_task(self._drain_human(),
                                            name="dash-human"))
        self._bg.append(asyncio.create_task(self._broadcast(),
                                            name="dash-bcast"))
        self._server = await asyncio.start_server(self._client, "0.0.0.0", port)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        for t in self._bg:
            t.cancel()
        if self._server:
            self._server.close()

    # ---------------------------------------------------- flux temps réel --
    async def _consume(self) -> None:
        """Consomme l'observateur : suit les tâches + pousse aux clients SSE."""
        while True:
            msg = await self.observer.get()
            if (msg.type == bus_mod.RESPONSE
                    and msg.reply_to in self.tasks):
                t = self.tasks[msg.reply_to]
                t["status"] = ("ok" if msg.payload.get("status") == "ok"
                               else "échec")
                t["result"] = str(
                    msg.payload.get("result")
                    or msg.payload.get("reason") or "")[:300]
                self._push({"kind": "state", "state": self.state()})
            self._push({"kind": "msg", "msg": msg.to_dict()})

    async def _drain_human(self) -> None:
        while True:
            await self.human.get()   # réponses vers "human" : déjà suivies

    async def _broadcast(self) -> None:
        while True:
            await asyncio.sleep(2.0)
            self._push({"kind": "state", "state": self.state()})

    def _push(self, item: dict) -> None:
        for q in list(self.sse_clients):
            q.put_nowait(item)

    # ------------------------------------------------------------ état ----
    def state(self) -> dict:
        b = self.boss
        larbins = [{
            "name": lb.name, "role": lb.role, "provider": lb.provider.name,
            "model": lb.provider.model, "status": lb.status,
            "requests": lb.stats["requests"], "errors": lb.stats["errors"],
            "repairs": lb.stats["repairs"], "versions": len(lb.versions),
        } for lb in sorted(b.larbins.values(), key=lambda l: l.name)]
        tasks = sorted(self.tasks.values(),
                       key=lambda t: t["ts"], reverse=True)[:15]
        recent_kb = [{
            "type": e.get("type"), "role": e.get("role"),
            "info": (e.get("error") or e.get("outcome") or "")[:90],
        } for e in self.kb.entries[-8:]][::-1]
        return {
            "mode": self.mode,
            "config": os.path.basename(self.config_path),
            "uptime": int(time.time() - self.started),
            "larbins": larbins,
            "providers": self.registry.healths(),
            "chains": self.cfg.chains,
            "events": list(b.events)[-60:][::-1],
            "bus": self.bus.stats(),
            "pending": len(b.pending),
            "knowledge": {"total": len(self.kb.entries), "recent": recent_kb},
            "tasks": tasks,
            "scenario_running": self.scenario_running,
            "settings": {k: self.cfg.settings.get(k) for k in (
                "request_timeout", "watchdog_factor", "max_escalations",
                "max_repairs", "knowledge_scope", "delegation_validation",
                "sandbox_timeout")},
        }

    # ------------------------------------------------------------- HTTP ---
    async def _client(self, reader: asyncio.StreamReader,
                      writer: asyncio.StreamWriter) -> None:
        try:
            line = await asyncio.wait_for(reader.readline(), 15)
            parts = line.decode("utf-8", "replace").split()
            if len(parts) < 2:
                return
            method, path = parts[0].upper(), parts[1].split("?", 1)[0]
            headers: dict[str, str] = {}
            while True:
                h = await asyncio.wait_for(reader.readline(), 15)
                if h in (b"\r\n", b"\n", b""):
                    break
                k, _, v = h.decode("utf-8", "replace").partition(":")
                if v:
                    headers[k.strip().lower()] = v.strip()
            body = b""
            if method == "POST":
                n = int(headers.get("content-length", "0") or 0)
                body = await reader.readexactly(n) if n else b""

            if method == "GET" and path == "/":
                await self._send_file(writer, "dashboard.html")
            elif method == "GET" and path == "/api/state":
                await self._send_json(writer, self.state())
            elif method == "GET" and path == "/api/messages":
                limit = 120
                msgs = [m.to_dict() for m in self.bus.history[-limit:]]
                await self._send_json(writer, {"messages": msgs})
            elif method == "GET" and path == "/api/events":
                await self._sse(writer)
                return  # connexion longue : déjà fermée par _sse
            elif method == "POST" and path == "/api/task":
                await self._send_json(writer, await self._api_task(body))
            elif method == "POST" and path == "/api/scenario":
                await self._send_json(writer, await self._api_scenario())
            else:
                await self._send_json(writer, {"error": "introuvable"}, 404)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError,
                ConnectionResetError, BrokenPipeError, ValueError):
            pass
        except Exception as e:  # noqa: BLE001
            log("dashboard", f"⚠️ requête échouée : {e!r}", "⚠️")
        finally:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass

    # ---------------------------------------------------------- réponses --
    async def _send_json(self, writer, obj: dict, code: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        writer.write(
            f"HTTP/1.1 {code} OK\r\nContent-Type: application/json; "
            f"charset=utf-8\r\nContent-Length: {len(data)}\r\n"
            f"Connection: close\r\n\r\n".encode() + data)
        await writer.drain()

    async def _send_file(self, writer, name: str) -> None:
        path = os.path.join(STATIC_DIR, name)
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            await self._send_json(writer, {"error": "fichier manquant"}, 500)
            return
        head = ("HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(data)}\r\nConnection: close\r\n\r\n"
                ).encode("utf-8")
        writer.write(head + data)
        await writer.drain()

    async def _sse(self, writer) -> None:
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream; "
            b"charset=utf-8\r\nCache-Control: no-cache\r\n"
            b"Connection: keep-alive\r\n\r\n")
        await writer.drain()
        q: asyncio.Queue = asyncio.Queue()
        self.sse_clients.append(q)
        log("dashboard", f"🟢 client connecté ({len(self.sse_clients)} "
                         f"au total)", "🖥️")
        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), 15)
                except asyncio.TimeoutError:
                    item = {"kind": "ping"}
                data = json.dumps(item, ensure_ascii=False)
                writer.write(f"data: {data}\n\n".encode("utf-8"))
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError, RuntimeError, OSError):
            pass
        finally:
            if q in self.sse_clients:
                self.sse_clients.remove(q)
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------- APIs ---
    async def _api_task(self, body: bytes) -> dict:
        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return {"ok": False, "error": "JSON invalide"}
        task = str(data.get("task") or "").strip()
        role = str(data.get("role") or "coder").strip()
        if not task:
            return {"ok": False, "error": "tâche vide"}
        if role not in ("coder", "summarizer", "reviewer", "validator",
                        "generic"):
            return {"ok": False, "error": f"rôle inconnu : {role}"}
        mock = self.mode.startswith("MOCK")
        larbin = await self.boss.spawn(role,
                                       reason=f"tâche dashboard : {task[:60]}")
        req = Message(bus_mod.REQUEST, frm="human", to=larbin.addr,
                      task_id=f"dash-{len(self.tasks) + 1}", body=task,
                      payload={"expected_seconds": 5 if mock else 60})
        self.tasks[req.id] = {"id": req.id, "task": task[:140], "role": role,
                              "larbin": larbin.name, "status": "en cours",
                              "ts": time.time(), "result": ""}
        log("dashboard", f"⌨️ tâche reçue → {larbin.name} ({role})",
            "⌨️")
        await self.bus.send(req)
        return {"ok": True, "larbin": larbin.name}

    async def _api_scenario(self) -> dict:
        if self.scenario_running:
            return {"ok": False, "error": "scénario déjà en cours"}
        self.scenario_running = True

        async def _run() -> None:
            try:
                from .demo import run_scenario
                await run_scenario(self.boss, self.bus)
                log("dashboard", "🎬 scénario terminé", "🎬")
            except Exception as e:  # noqa: BLE001
                log("dashboard", f"💥 scénario échoué : {e!r}", "💥")
            finally:
                self.scenario_running = False
        asyncio.create_task(_run())
        log("dashboard", "🎬 scénario complet lancé (bug → réparation → "
                        "délégation → escalade)", "🎬")
        return {"ok": True}


# ------------------------------------------------------------ point d'entrée

async def serve(config_path: str, port: int, mock: bool = False) -> int:
    """Construit la colonie + le dashboard et tourne pour toujours."""
    cfg = Config(config_path)
    registry = Registry.from_config(cfg)
    mode = "LIVE"
    if mock or not registry.providers:
        if not mock:
            log("dashboard", "⚠️ aucune IA dans le .env → mode MOCK (démo)",
                "⚠️")
        cfg = Config(demo_config_path())
        registry = Registry.from_config(cfg)
        mode = "MOCK (démo)"
    from .boss import Boss  # import tardif (évite boucle)
    bus = Bus(max_history=cfg.max_history)
    kb = KnowledgeBase()
    boss = Boss(registry, bus, cfg, kb)
    await boss.start()
    dash = Dashboard(boss, bus, registry, cfg, kb, mode, config_path)
    await dash.start(port)
    log("dashboard", f"🖥️ interface prête sur le port {dash.port} "
                    f"(mode {mode}) — Ctrl+C pour arrêter", "🖥️")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await dash.stop()
        await boss.stop()
    return 0
