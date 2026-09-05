"""Le bus de messages : le système nerveux de la colonie.

Règles (validées avec Adam) :
- Topologie "mesh supervisé" : les larbins s'envoient des messages DIRECTEMENT,
  mais le boss reçoit une copie de CHAQUE message (il voit tout, peut détecter
  les blocages et escalader).
- Format hybride : enveloppe JSON (champs fixes) + corps en langage naturel.
- Request/response avec timeout, id de corrélation (reply_to).
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict, dataclass, field

from .log import log

BOSS = "boss"

# Types de messages reconnus
REQUEST = "request"          # demande d'un agent à un autre (attend une réponse)
RESPONSE = "response"        # réponse à un request (reply_to = id du request)
DELEGATION = "delegation"    # demande au boss de faire bosser un autre larbin
ESCALATION = "escalation"    # signalement au boss (timeout, larbin bloqué)
REPAIR_REQUEST = "repair_request"  # demande de réparation de code au boss
REPAIR_DONE = "repair_done"        # boss -> larbin : code réparé (ou abandon)
ERROR = "error"              # rapport d'erreur au boss
INFO = "info"                # annonce (changements d'état, etc.)


@dataclass
class Message:
    """Enveloppe JSON + corps en langage naturel."""

    type: str
    frm: str                       # adresse de l'expéditeur ("boss" ou "larbin:xx")
    to: str                        # adresse du destinataire ("boss", "larbin:xx", "*")
    body: str = ""                 # corps en langage naturel
    payload: dict = field(default_factory=dict)   # données structurées
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    reply_to: str | None = None    # id du message auquel on répond
    task_id: str | None = None     # id de tâche métier (optionnel)
    priority: int = 1              # 0=urgent, 1=normal, 2=arrière-plan
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        # clé JSON-friendly
        d["from"] = d.pop("frm")
        return d

    @staticmethod
    def from_dict(d: dict) -> "Message":
        d = dict(d)
        d["frm"] = d.pop("from", d.get("frm", "?"))
        allowed = {f for f in Message.__dataclass_fields__}
        return Message(**{k: v for k, v in d.items() if k in allowed})


class Bus:
    """Boîtes aux lettres + observateurs (le boss observe tout)."""

    def __init__(self, max_history: int = 2000):
        self._queues: dict[str, asyncio.Queue] = {}
        self._observers: list[asyncio.Queue] = []
        self.history: list[Message] = []          # pour le dashboard / rapport
        self.max_history = max_history

    # ------------------------------------------------------------------ API
    def register(self, address: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues[address] = q
        return q

    def register_observer(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._observers.append(q)
        return q

    def unregister(self, address: str) -> None:
        self._queues.pop(address, None)

    async def send(self, msg: Message) -> bool:
        """Delivre le message. Retourne False si le destinataire n'existe pas."""
        self._record(msg)
        # Copie au(x) observateur(s) — le boss voit TOUT.
        for q in self._observers:
            q.put_nowait(msg)
        if msg.to == "*":
            for addr, q in self._queues.items():
                if addr != msg.frm:
                    q.put_nowait(msg)
            return True
        q = self._queues.get(msg.to)
        if q is None:
            if msg.to == BOSS and self._observers:
                # le boss lit tout via son observateur (mesh supervisé)
                return True
            log("bus", f"⚠️ destinataire inconnu '{msg.to}' "
                       f"(message {msg.type} de {msg.frm} perdu)", "📭")
            return False
        q.put_nowait(msg)
        return True

    # ---------------------------------------------------------------- divers
    def _record(self, msg: Message) -> None:
        self.history.append(msg)
        if len(self.history) > self.max_history:
            del self.history[: len(self.history) - self.max_history]

    def stats(self) -> dict:
        by_type: dict[str, int] = {}
        for m in self.history:
            by_type[m.type] = by_type.get(m.type, 0) + 1
        return {"total": len(self.history), "by_type": by_type}
