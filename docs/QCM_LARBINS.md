# 📋 QCM de personnalisation de la Colonie — 50 questions

Réponds à ces 50 questions pour configurer TA colonie. Chaque question indique
ce qu'elle change :
- **●** = appliqué directement dans la config / le code
- **○** = noté pour la roadmap (encore non câblé)

Deux façons de répondre :
1. **Interactif** : `python3 -m colony.cli quiz` → génère `config.perso.json` tout seul
2. **À la main** : réponds dans le chat (ex. `1:B 2:A 5:C ...`) ou coche et donne-moi le fichier

---

## 🎭 Thème 1 — Identité des larbins (Q1-6)

### Q1 — Ton général des larbins ? `style.tone` ●
- A. **Direct** — réponses courtes, zéro blabla
- B. **Pipelette** — explique son raisonnement, petites remarques sympas
- C. **Formel** — poli, vouvoiement, style rapport
- D. **Militaire** — ordres brefs, style caserne

→ impact : le prompt système de TOUS les larbins.

### Q2 — Langue des larbins ? `style.language` ●
- A. Français
- B. Anglais
- C. Bilingue (répond dans la langue de la demande)

### Q3 — Format de réponse préféré ? `style.output_format` ●
- A. Texte libre (lisible)
- B. JSON structuré dès que possible
- C. Auto — texte pour l'humain, JSON entre larbins

### Q4 — Signature des larbins ? `style.signature` ●
- A. Aucune
- B. Prénom du larbin en fin de réponse (— alfred)
- C. Emoji d'humeur

### Q5 — Style de nommage ? `style.naming` ●
- A. Métier-N (validator-1, summarizer-2)
- B. Prénoms de larbins (alfred, jeeves, edmund...)
- C. Callsigns militaires (alpha, bravo, charlie...)

### Q6 — Mémoire de conversation d'un larbin ? `settings.conversation_memory` ●
- A. 4 tours (amnésique, économique)
- B. 12 tours (équilibré) ✨
- C. 30 tours (bonne mémoire, plus de tokens)
- D. 60 tours (éléphant, gourmand)

---

## 👑 Thème 2 — Le Boss & l'affichage (Q7-12)

### Q7 — Ton du boss ? `style.boss_tone` ●
- A. Neutre et pro
- B. Général d'armée — bref, autoritaire
- C. Papa cool — encourage les larbins

→ impact : ses messages de log + ses prompts de validation.

### Q8 — Verbosité des logs ? `COLONY_VERBOSITY` ●
- A. Minimal — juste les événements clés
- B. Normal ✨
- C. Verbeux — tout ce qui se passe

### Q9 — Emojis dans les logs ? `COLONY_NO_EMOJI` ●
- A. Oui (👑🩹🔁...) ✨
- B. Non, sobre

### Q10 — Couleurs des logs ? `COLONY_MONO` ●
- A. Couleurs (chaque larbin a sa couleur) ✨
- B. Monochrome (pour logs dans un fichier)

### Q11 — Rapport final de démo ? `style.report` ●
- A. Court — statut + résultat
- B. Normal — + événements du boss ✨
- C. Détaillé — + larbins, providers, mémoire

### Q12 — Doctor automatique au démarrage ? ○
- A. Oui — ping les IAs avant chaque session
- B. Non, manuel ✨

---

## 💬 Thème 3 — Communication entre larbins (Q13-18)

### Q13 — Timeout de base d'une demande ? `settings.request_timeout` ●
- A. 15 s (nerfs d'acier)
- B. 30 s
- C. 60 s ✨ (les vraies IAs sont parfois lentes)
- D. 120 s (zen)

### Q14 — Facteur du watchdog ? `settings.watchdog_factor` ●
*(watchdog = expected_seconds × facteur)*
- A. ×2 — intraitable
- B. ×4 ✨
- C. ×6 — patient
- D. ×8 — très patient

### Q15 — Délai global de grâce ? `settings.grace_factor` ●
*(dureté max = timeout × facteur, escalades comprises)*
- A. ×2 — rapide à abandonner
- B. ×4 ✨
- C. ×6 — laisse beaucoup de chances

### Q16 — Escalades max par demande ? `settings.max_escalations` ●
- A. 1 — une seule IA de secours
- B. 2 ✨
- C. 3 — insistant

### Q17 — Priorité par défaut des tâches ? `settings.default_priority` ●
- A. 0 — tout est urgent
- B. 1 — normal ✨
- C. 2 — arrière-plan

### Q18 — Historique du bus gardé en mémoire ? `settings.max_history` ●
- A. 500 messages
- B. 2000 ✨
- C. 10000 (pour gros dashboards)

---

## 🔁 Thème 4 — Escalade multi-IA (Q19-24)

### Q19 — Quand une IA répond 429 (rate limit) ? ○
- A. Attendre son cooldown et retenter
- B. Changer d'IA immédiatement ✨ *(c'est le comportement actuel)*
- C. Pause totale 5 min de la colonie

### Q20 — Seuil du circuit breaker ? `settings.breaker_threshold` ●
*(nb d'échecs consécutifs avant d'ignorer une IA)*
- A. 2 — intolérant
- B. 3 ✨
- C. 5 - patient

### Q21 — Cooldown du circuit breaker ? `settings.provider_cooldown` ●
- A. 30 s
- B. 60 s ✨
- C. 300 s — longue punition

### Q22 — Jules tombe en panne, on fait quoi ? ○
- A. L'exclure jusqu'à nouvel ordre (manuel)
- B. Retry auto toutes les 30 min ✨ *(approx. actuel : cooldown breaker)*

### Q23 — Vérification de santé périodique des IAs ? ○
- A. Oui, toutes les heures
- B. Non, seulement au doctor ✨

### Q24 — L'escalade doit-elle tenir compte du coût ? ○
- A. Gratuit d'abord, payant en dernier
- B. Je m'en fous ✨ *(approx. actuel : ordre des chaînes)*

---

## 🩹 Thème 5 — Self-healing & Réparateur (Q25-31)

### Q25 — Politique de rollback ? `settings.rollback_policy` ●
- A. Toujours essayer l'ancien code d'abord ✨
- B. Jamais — repair direct

### Q26 — Réparations max par larbin et par tâche ? `settings.max_repairs` ●
- A. 1 — une seule chance
- B. 3 ✨
- C. 5 — acharné

### Q27 — IA réparatrice en tête de chaîne ? `chain repairer` ●
- A. Fable 5.1 (Anthropic) ✨
- B. OpenRouter
- C. Mistral

### Q28 — Température du Réparateur ? `settings.repair_temperature` ●
- A. 0.0 — déterministe, chirurgical ✨
- B. 0.2 — un poil de créativité
- C. 0.5 — joueur (risqué pour du code)

### Q29 — Tests des candidats réparés ? `settings.candidate_test_mode` ●
- A. Basic — payload original + payload vide ✨
- B. Paranoid — + cas limites supplémentaires

### Q30 — Mémoire globale des bugs ? `settings.knowledge_scope` ●
- A. Partagée — tout le monde voit tout ✨
- B. Par rôle — chaque rôle apprend seul
- C. Désactivée — amnésie entre incidents

### Q31 — Après épuisement du self-healing ? ○
- A. Échec propre et explicite ✨ *(actuel)*
- B. Demander à l'humain
- C. Remettre en file pour plus tard

---

## 🤝 Thème 6 — Délégation entre larbins (Q32-36)

### Q32 — Validation des délégations ? `settings.delegation_validation` ●
- A. Règles rapides (corps, usurpation, cycles) ✨
- B. LLM — le boss juge avec son IA
- C. Les deux

### Q33 — Anti-cycle ? ○
- A. Strict — interdire A↔B ✨ *(actuel)*
- B. Profondeur 2 — interdire aussi A→B→C→A

### Q34 — Larbin inactif disponible ? `settings.delegation_reuse` ●
- A. Le réutiliser ✨
- B. Créer un nouveau larbin à chaque fois

### Q35 — Profondeur max des délégations en chaîne ? ○
- A. 1 niveau
- B. 2 niveaux
- C. Illimité (avec anti-cycle) ✨ *(approx. actuel)*

### Q36 — Le boss peut-il déléguer PENDANT une réparation ? ○
- A. Oui — parallèle total
- B. Non — réparations priorité absolue ✨ *(actuel : file priorisée)*

---

## 🏰 Thème 7 — Sandbox & sécurité (Q37-41)

### Q37 — Timeout d'exécution du code ? `settings.sandbox_timeout` ●
- A. 5 s — brutal
- B. 15 s
- C. 20 s ✨
- D. 60 s — pour les gros jobs

### Q38 — Le code des larbins peut-il accéder au réseau ? ○
- A. Non ✨ *(actuel : pas de contrôle fin, évite le code inconnu)*
- B. Lecture seule
- C. Oui

### Q39 — Écriture de fichiers ? ○
- A. Non ✨ *(actuel)*
- B. Oui mais seulement dans data/

### Q40 — Imports Python autorisés ? ○
- A. Stdlib de base ✨ *(actuel : rien de bloqué, sois prudent)*
- B. Liste blanche
- C. Tout

### Q41 — Versions de code gardées pour rollback ? `settings.max_versions` ●
- A. 2
- B. 3 ✨
- C. 5

---

## 🔌 Thème 8 — Providers & chaînes d'IA (Q42-47)

### Q42 — IA principale pour CODER ? `chain coder` ●
- A. Fable 5.1 ✨
- B. OpenRouter
- C. Gemini
- D. Groq

### Q43 — IA pour le CHAT courant (résumés, reviews) ? `chain chat` ●
- A. Groq (rapide et gratuit)
- B. OpenRouter ✨
- C. Gemini
- D. Mistral

### Q44 — Timeout HTTP des providers ? `settings.http_timeout` ●
- A. 60 s
- B. 90 s ✨
- C. 120 s
- D. 180 s (Jules est lent)

### Q45 — Intervalle min entre 2 appels à la même IA ? `settings.min_interval` ●
- A. 0.2 s — speedrun (risque de 429)
- B. 0.6 s
- C. 1.0 s ✨
- D. 2.0 s — très prudent

### Q46 — Ajouter un provider custom plus tard ? ○
- A. Oui — via base_url libre (déjà supporté !) ✨
- B. Non, les presets suffisent

### Q47 — Rôle de Jules dans la colonie ? ○
- A. Larbin codeur dédié (tasks de repo GitHub)
- B. Dernier recours seulement ✨ *(actuel : chaîne jules-tasks)*
- C. Désactivé

---

## 💰 Thème 9 — Budget & monitoring (Q48-50)

### Q48 — Suivi des coûts ? ○
- A. Aucun ✨ *(actuel)*
- B. Compteur d'appels par provider *(déjà dans les rapports)*
- C. Estimation $ par provider
- D. Alerte au-delà d'un seuil

### Q49 — Alertes de la colonie ? ○
- A. Console seulement ✨ *(actuel)*
- B. Son sur échec critique
- C. Notification Telegram

### Q50 — Dashboard web live ? ○
- A. Oui, je le veux (roadmap n°1)
- B. Plus tard ✨
- C. Non, le terminal me suffit

---

## ✨ Config solo équilibrée conseillée (si tu veux aller vite)

```
1:A 2:A 3:C 4:A 5:B 6:B 7:A 8:B 9:A 10:A 11:B 12:B
13:C 14:B 15:B 16:B 17:B 18:B 19:B 20:B 21:B 22:B 23:B 24:B
25:A 26:B 27:A 28:A 29:A 30:A 31:A 32:A 33:A 34:A 35:C 36:B
37:C 38:A 39:A 40:A 41:B 42:A 43:B 44:B 45:C 46:A 47:B 48:A 49:A 50:B
```

Ou simplement : `python3 -m colony.cli quiz` et laisse-toi guider. 🐜
