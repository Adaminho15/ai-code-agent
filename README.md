# ai-code-agent — la Colonie 👑

**Un boss, des larbins, et une armée d'IAs de secours.**

Application personnelle d'agents IA : quand tu parles au boss, il crée des
sous-agents (larbins) qui **se parlent entre eux**, bossent avec **n'importe
laquelle de tes IAs** (Fable 5.1, OpenRouter, Cloudflare, Gemini, Groq,
Mistral, Jules... 12 providers natifs), **réparent leur propre code** quand
il bugue, et **recréent un larbin sur une autre IA** quand l'une d'elles
tombe en maintenance.

> Conçu d'après le design validé point par point (topologie *mesh supervisé*,
> request/response avec timeout, enveloppe JSON + corps en langage naturel,
> délégation horizontale validée par le boss, self-healing avec mémoire des
> bugs, escalade multi-IA « jamais la même IA »).

---

## 🖥️ Dashboard web live

```bash
python3 -m colony.cli dashboard            # tes IAs du .env (fallback mocks)
python3 -m colony.cli dashboard --mock     # mode démo sans aucune clé
python3 -m colony.cli dashboard --port 8420 --config config.perso.json
```

Dans le navigateur :
- **fil de messages temps réel** (SSE + polling de secours) : chaque échange
  entre larbins, escalades, réparations… en direct et en couleur ;
- **bouton 🎬 Scénario complet** : rejoue en live le bug → réparation →
  délégation → escalade multi-IA ;
- **donne des tâches** à la colonie depuis la barre du bas (rôle au choix) ;
- panneaux : larbins (statut, IA, réparations), providers (appels, erreurs,
  breaker), chaînes de fallback, événements du boss, mémoire des bugs.

Zéro dépendance (serveur HTTP asyncio stdlib), interface autonome
(`colony/static/dashboard.html`).

## 🎨 Personnalisation (50 questions)

Deux façons de régler TA colonie aux petits oignons :

1. **Le quiz interactif** — `python3 -m colony.cli quiz`
   50 questions (ton des larbins, langue, nommage, timeouts, self-healing,
   chaînes d'IA...) → génère `config.perso.json` tout seul :
   ```bash
   python3 -m colony.cli quiz             # guidé (Entrée = conseil ✨)
   python3 -m colony.cli quiz --quick     # toutes les réponses conseillées
   python3 -m colony.cli --config config.perso.json demo
   ```
2. **Le QCM papier** — `docs/QCM_LARBINS.md` : les mêmes 50 questions avec
   explications ; réponds dans le chat ou coche le fichier.

Ce qui est personnalisable **directement** (câblé) : ton des larbins, langue,
format de réponse, signature, nommage (métier-N / prénoms / callsigns),
mémoire de conversation, ton du boss, verbosité, emojis, couleurs, rapport
final, tous les timeouts, escalades, breaker, rollback, température du
Réparateur, tests candidats, mémoire des bugs (partagée/par rôle/off),
réutilisation des larbins inactifs, ordre des chaînes d'IA... Les réponses
non câblées sont notées dans `wishes` (roadmap).

## ⚡ Démarrage express

```bash
# 1) Démo complète SANS aucune clé API (100% mockée, 5 secondes)
python3 -m colony.cli demo

# 2) Brancher tes vraies IAs
cp .env.example .env      # puis colle tes clés
python3 -m colony.cli doctor          # vérifie que chaque IA répond
python3 -m colony.cli demo --live     # la même démo, avec tes vraies IAs

# 3) Donner une tâche libre à un larbin codeur (Fable 5.1 en tête de chaîne)
python3 -m colony.cli run "Écris un validateur d'adresses IPv6 en Python"

# Tests (mockés, aucune clé requise)
python3 -m unittest discover -s tests -v
```

Scénario personnalisé : voir `examples/custom_scenario.py`.

---

## 🏗 Architecture

```
                toi ──► le BOSS (orchestrateur, voit TOUT)
                          │  crée / recrée / répare
                          ▼
   ┌──────────┐   request/response    ┌────────────┐
   │ larbin A │ ◄───────────────────► │  larbin B  │     ← mesh supervisé :
   └────┬─────┘   (timeout → escalade)└─────┬──────┘       le boss reçoit une
        │                                   │               copie de CHAQUE
        ▼                                   ▼               message
   son IA (provider)                  son IA (provider)
   fable → openrouter → gemini…       openrouter → gemini → groq…
        │                                   │
        └───────── code bugué ? ───────────┘
                          │
                          ▼
              LARBIN RÉPARATEUR (Fable 5.1)
              mémoire globale des bugs (data/knowledge.json)
              rollback → recodage → test sandbox → déploiement
```

### Les règles d'or implémentées

| Situation | Ce que fait la colonie |
|---|---|
| Une IA est en maintenance / 503 / rate-limit | Le boss **recrée le larbin sur une AUTRE IA** (jamais la même), la demande reprend où elle était |
| Un larbin attend trop (tâche de 10s pas livrée) | Timeout + **watchdog** du boss → escalade, max 2 fois, puis échec propre (jamais de blocage infini) |
| Le **code** d'un larbin bugue | **Rollback** vers la version précédente d'abord ; sinon le **Larbin Réparateur** (Fable 5.1) recode **avec l'historique des bugs en mémoire**, le candidat est **testé au sandbox** avant déploiement |
| Le code recodé est pire | Rollback + l'échec est **mémorisé** → la tentative suivante « sait mieux faire » |
| Un larbin veut déléguer à un autre | Le boss **valide** (corps non vide, pas d'usurpation, **pas de cycle** A→B→A ; option check LLM) |
| Une IA spamme des erreurs | **Circuit breaker** : 3 échecs → provider ignoré 60 s (cooldown) |
| Toutes les IAs d'une chaîne sont mortes | Échec propre et explicite, pas de boucle |

---

## 🧩 Les composants

```
colony/
├── bus.py          # messagerie : enveloppe JSON + corps langage naturel,
│                   #   boîtes aux lettres, copie de tout au boss
├── boss.py         # orchestrateur : spawn dynamique, watchdog, escalades,
│                   #   validation des délégations, file de réparation
├── larbin.py       # sous-agent : mission + IA + tool Python optionnel,
│                   #   self-healing (rollback → réparation → retry)
├── repairer.py     # Larbin Réparateur : recode avec la mémoire des bugs
├── sandbox.py      # exécution du code en sous-processus (timeout anti-
│                   #   boucle infinie, stdin/stdout JSON, tests candidats)
├── knowledge.py    # mémoire globale partagée (data/knowledge.json)
├── config.py       # .env + config.json + réglages
├── providers/
│   ├── base.py         # rate limiter + circuit breaker + santé
│   ├── openai_compat.py# OpenRouter, Cloudflare, Groq, Mistral, DeepSeek,
│   │                   #   Together, Cerebras, Fireworks, Gemini, OpenAI...
│   ├── anthropic.py    # natif Messages API → Fable 5.1 (claude-fable-5-1)
│   ├── jules.py        # Google Jules (sessions REST + polling) ⚠️ expérimental
│   ├── mock.py         # tests/démo sans aucune clé
│   └── registry.py     # chaînes de fallback par capacité
└── cli.py          # demo / doctor / run
```

---

## 🔌 Brancher tes IAs

Tout se passe dans **`.env`** (les clés — jamais commis) et **`config.json`**
(les providers + les chaînes). Un provider sans clé est simplement désactivé
au démarrage (message de log), donc tu peux tout déclarer et ne remplir que
ce que tu as.

Providers natifs (`kind`) :

| kind | Couvre | Notes |
|---|---|---|
| `openai_compat` | OpenRouter, Cloudflare Workers AI, Groq, Mistral, DeepSeek, Together, Cerebras, Fireworks, Gemini, OpenAI, n'importe quelle passerelle | `preset` tout prêt OU `base_url` libre |
| `anthropic` | **Fable 5.1** (`claude-fable-5-1`) | natif `/v1/messages` |
| `jules` | Google Jules | sessions REST, auto-approve du plan, polling ⚠️ expérimental |
| `mock` | tests & démo | `good` / `flaky` / `slow` / `down` |

### 🦙 IA locale (Ollama, LM Studio, llama.cpp) — sans clé

Le provider **`local`** est déjà dans `config.json` (presets `ollama`,
`lmstudio`, `llamacpp`). Aucune clé à fournir : il détecte **tout seul** le
premier modèle installé via l'API Ollama.

```bash
# Installe Ollama → https://ollama.com  puis :
ollama pull qwen2.5-coder:7b      # bon codeur local (ou llama3.1:8b, mistral:7b...)
python3 -m colony.cli doctor      # doit afficher : ✅ local  qwen2.5-coder:7b
```

- Placé en **fin de chaîne** par défaut = planche de secours quand TOUT le
  cloud est mort. Mets-le en premier dans `chains` si tu veux du 100 % local
  (gratuit et illimité).
- Pour LM Studio : `"preset": "lmstudio"` (port 1234), llama.cpp :
  `"llamacpp"` (port 8080).

Les **chaînes** (`chains`) définissent l'ordre de fallback par capacité —
c'est ce qui fait que « si Jules/l'IA X est en maintenance, on en recrée un
sur une autre IA » :

```json
"chains": {
  "repairer": ["fable", "openrouter", "mistral"],
  "coder":    ["fable", "openrouter", "mistral", "gemini"],
  "chat":     ["openrouter", "gemini", "groq", "mistral", "deepseek",
               "together", "cerebras", "fireworks", "cloudflare", "openai"]
}
```

Ajouter une IA = 3 lignes dans `config.json` + 1 clé dans `.env`. C'est tout.

### Réglages (`settings`)

| Clé | Défaut | Rôle |
|---|---|---|
| `request_timeout` | 60 | délai « normal » d'une demande entre agents |
| `watchdog_factor` | 4 | watchdog = expected_seconds × facteur |
| `grace_factor` | 4 | délai global dur = timeout × facteur |
| `max_escalations` | 2 | nb max de recréations de larbin par demande |
| `max_repairs` | 3 | nb max de recodages par larbin et par tâche |
| `sandbox_timeout` | 20 | temps max d'exécution d'un tool (anti boucle infinie) |
| `provider_cooldown` | 60 | cooldown du circuit breaker |
| `delegation_validation` | `rules` | `rules` (rapide) ou `llm` (le boss juge par LLM) |
| `max_versions` | 3 | versions de code gardées pour rollback |

---

## 💬 La messagerie (format hybride)

```json
{
  "type": "request",            // request | response | delegation | escalation |
                                // repair_request | repair_done | error | info
  "from": "larbin:validator-1",
  "to":   "larbin:summarizer-2",
  "body": "Résume ce résultat de validation d'emails en 2 phrases.",
  "payload": { "input": { "results": [...] } },
  "id": "a1b2c3d4e5f6",
  "reply_to": null,
  "priority": 1
}
```

- **Enveloppe** stricte (machine) + **corps** en langage naturel (les IIs
  se parlent comme elles savent le faire).
- Chaque larbin a une **mémoire de conversation** (12 derniers tours) pour
  son IA.
- Le boss reçoit une copie de **tout** → il détecte les blocages.

---

## 🩹 Self-healing en détail

1. Le tool d'un larbin crashe au sandbox (crash / timeout / sortie invalide).
2. **Rollback d'abord** : si la version précédente marche, on la garde.
3. Sinon → `repair_request` (priorité 0) au boss → file de réparation.
4. Le **Larbin Réparateur** (Fable 5.1) recode avec :
   - le code qui a planté + l'erreur + le payload fautif,
   - **l'historique global des bugs et des tentatives** (mémoire).
5. Le candidat est **testé au sandbox** (payload original + cas limites).
   - ✅ → déployé en nouvelle version (max 3 gardées) → retry de la tâche.
   - ❌ → l'échec est **mémorisé** (la prochaine tentative évite cette
     erreur) → nouvelle tentative, jusqu'à `max_repairs` → abandon propre.

La mémoire vit dans `data/knowledge.json` → **la colonie apprend entre les
exécutions**.

---

## 🗺 Roadmap (prochaines étapes)

- [x] ~~Web UI (dashboard live)~~ ✅ `python3 -m colony.cli dashboard`
- [ ] Tools de « vraie » app de code : éditer des fichiers du repo, git,
      lancer les tests (aujourd'hui les larbins ont un tool JSON générique)
- [ ] Jules en larbin de code complet (repo GitHub branché)
- [ ] Budget caps par provider (compteur de tokens/$)
- [ ] Docker compose pour tourner 24/7 sur un petit VPS

---

## ⚠️ Limites actuelles (assume en connaissance de cause)

- Les larbins exécutent du code Python **sur ta machine** (sandbox =
  sous-processus + timeout, pas de conteneur isolé). C'est ton choix
  (« c'est pas grave »), mais n'exécute pas de code de sources inconnues.
- L'adaptateur Jules est expérimental (l'API évolue) — `doctor` te dira
  s'il marche avec ta clé.
- Tout tourne en un seul process : si tu fermes le terminal, la colonie
  s'arrête ( Roadmap : VPS + Docker).
