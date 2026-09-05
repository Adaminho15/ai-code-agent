"""Le Larbin Réparateur — le cœur du self-healing.

Utilise la chaîne de providers "repairer" (Fable 5.1 en tête par défaut).
Reçoit : le code qui a planté, l'erreur, et l'historique des bugs connus de
la colonie (mémoire globale). Renvoie un code candidat qui est TOUJOURS
testé au sandbox avant déploiement — et chaque échec est mémorisé pour que
la tentative suivante « sache mieux faire ».
"""
from __future__ import annotations

import json

from .config import Config
from .knowledge import KnowledgeBase
from .log import log
from .providers.registry import Registry
from .sandbox import test_candidate
from .util import extract_code_block

REPAIR_SYSTEM = """Tu es le Larbin Réparateur d'une colonie d'agents.
On te donne le code Python d'un larbin qui a planté, l'erreur exacte, et
l'historique des bugs connus de la colonie.

Règles ABSOLUES :
1. Tu réponds UNIQUEMENT avec un bloc de code Python dans une clôture ```python ... ```
   (aucune explication avant ou après).
2. Le code DOIT définir `def handle(payload: dict) -> dict`.
3. Il lit son entrée depuis `payload` (un dict) et retourne un dict
   sérialisable en JSON.
4. Interdits : boucles sans borne de sortie, réseau, fichiers, imports
   exotiques, sous-processus.
5. Corrige le bug signalé ET évite TOUS les bugs listés dans l'historique.
6. Code simple, noms explicites, docstring courte."""


class Repairer:
    def __init__(self, registry: Registry, knowledge: KnowledgeBase,
                 cfg: Config):
        self.registry = registry
        self.knowledge = knowledge
        self.cfg = cfg

    async def fix(self, larbin_role: str, code: str, error: str,
                  detail: str, test_payload: dict) -> dict:
        """Retourne {"ok": bool, "code": str?, "reason": str?}."""
        # 1) On enregistre le bug dans la mémoire globale
        self.knowledge.record_bug(larbin_role, error, detail,
                                  code_snippet=code)

        # 2) Choix de l'IA réparatrice (Fable 5.1 en tête de chaîne)
        provider = (self.registry.pick("repairer")
                    or self.registry.pick("chat"))
        if provider is None:
            return {"ok": False,
                    "reason": "aucune IA disponible pour réparer"}

        history = self.knowledge.prompt_context(larbin_role)
        prompt = f"""# Larbin à réparer (rôle : {larbin_role})

## Code qui a planté
```python
{code}
```

## Erreur rencontrée
{error}
{detail[:600]}

## Payload qui a fait planter
{json.dumps(test_payload, ensure_ascii=False)[:400]}

## Historique des bugs/réparations pour ce rôle
(NE RÉINTRODUIS AUCUN DE CES BUGS — tire les leçons des tentatives)
{history}

Corrige le code. Réponds UNIQUEMENT par le bloc ```python``` final."""

        log("repairer", f"🔧 recodage par {provider.name} "
                        f"({provider.model}) avec {len(self.knowledge.for_role(larbin_role))} "
                        f"entrées de mémoire...", "🔧")
        raw = await provider.chat(REPAIR_SYSTEM, prompt,
                                  max_tokens=2000, temperature=0.0)
        new_code = extract_code_block(raw)
        if not new_code or "def handle" not in new_code:
            self.knowledge.record_fix(
                larbin_role, "failed_candidate",
                f"réponse sans code valide : {raw[:150]}")
            return {"ok": False, "reason": "pas de bloc python valide "
                                           "dans la réponse de l'IA"}

        # 3) Test sandbox sur le payload original + cas limites
        payloads = [test_payload if isinstance(test_payload, dict) else {},
                    {}]
        ok, reason = await test_candidate(new_code, payloads,
                                          timeout=self.cfg.sandbox_timeout)
        if not ok:
            self.knowledge.record_fix(
                larbin_role, "failed_candidate",
                f"candidat rejeté au sandbox : {reason}",
                candidate_excerpt=new_code[:400])
            return {"ok": False, "reason": reason}

        self.knowledge.record_fix(
            larbin_role, "success",
            f"corrigé et validé au sandbox (bug initial : {error})",
            candidate_excerpt=new_code[:400])
        return {"ok": True, "code": new_code}
