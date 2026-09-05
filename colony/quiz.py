"""Quiz de personnalisation : 50 questions pour générer TA config.

Lancement :
    python -m colony.cli quiz            # guidé (Entrée = réponse conseillée)
    python -m colony.cli quiz --quick    # toutes les réponses conseillées

Écrit `config.perso.json` (+ propose d'ajouter les préférences d'affichage
au .env). Ensuite :
    python -m colony.cli --config config.perso.json demo
"""
from __future__ import annotations

import json
import os

from .config import ROOT, default_config_path, load_env

# ---------------------------------------------------------------- questions
# k : kind -> set (settings) | style | env | wish | chain
# v : valeur par défaut (réponse conseillée ✨)

QUESTIONS: list[dict] = [
    # ---- Thème 1 : identité des larbins
    dict(id=1, t="Identité", k="style", m="tone", q="Ton général des larbins ?",
         o=[("Direct et concis", "direct"), ("Pipelette sympa", "chatty"),
            ("Formel, style rapport", "formel"), ("Militaire, ordres brefs", "militaire")], v=0),
    dict(id=2, t="Identité", k="style", m="language", q="Langue des larbins ?",
         o=[("Français", "fr"), ("Anglais", "en"), ("Bilingue (langue de la demande)", "auto")], v=0),
    dict(id=3, t="Identité", k="style", m="output_format", q="Format de réponse ?",
         o=[("Texte libre", "text"), ("JSON dès que possible", "json"),
            ("Auto (texte humain / JSON entre larbins)", "auto")], v=2),
    dict(id=4, t="Identité", k="style", m="signature", q="Signature en fin de réponse ?",
         o=[("Aucune", "none"), ("Prénom du larbin", "name"), ("Emoji d'humeur", "emoji")], v=0),
    dict(id=5, t="Identité", k="style", m="naming", q="Style de nommage des larbins ?",
         o=[("Métier-N (validator-1)", "metier"), ("Prénoms (alfred, jeeves...)", "prenoms"),
            ("Callsigns (alpha, bravo...)", "callsigns")], v=1),
    dict(id=6, t="Identité", k="set", m="conversation_memory", q="Mémoire de conversation (tours) ?",
         o=[("4 (amnésique)", 4), ("12 (équilibré)", 12), ("30 (bonne mémoire)", 30),
            ("60 (éléphant)", 60)], v=1),
    # ---- Thème 2 : boss & affichage
    dict(id=7, t="Boss", k="style", m="boss_tone", q="Ton du boss ?",
         o=[("Neutre et pro", "neutre"), ("Général d'armée", "general"),
            ("Papa cool", "cool")], v=0),
    dict(id=8, t="Boss", k="env", m="COLONY_VERBOSITY", q="Verbosité des logs ?",
         o=[("Minimal", "minimal"), ("Normal", "normal"), ("Verbeux", "verbose")], v=1),
    dict(id=9, t="Boss", k="env", m="COLONY_NO_EMOJI", q="Emojis dans les logs ?",
         o=[("Oui", "0"), ("Non, sobre", "1")], v=0),
    dict(id=10, t="Boss", k="env", m="COLONY_MONO", q="Couleurs des logs ?",
         o=[("Couleurs", "0"), ("Monochrome", "1")], v=0),
    dict(id=11, t="Boss", k="style", m="report", q="Rapport final de démo ?",
         o=[("Court", "court"), ("Normal", "normal"), ("Détaillé", "detaille")], v=1),
    dict(id=12, t="Boss", k="wish", m="doctor_on_start", q="Doctor automatique au démarrage ?",
         o=[("Oui", True), ("Non, manuel", False)], v=1),
    # ---- Thème 3 : communication
    dict(id=13, t="Communication", k="set", m="request_timeout", q="Timeout de base d'une demande (s) ?",
         o=[("15", 15), ("30", 30), ("60", 60), ("120", 120)], v=2),
    dict(id=14, t="Communication", k="set", m="watchdog_factor", q="Facteur du watchdog ?",
         o=[("x2", 2.0), ("x4", 4.0), ("x6", 6.0), ("x8", 8.0)], v=1),
    dict(id=15, t="Communication", k="set", m="grace_factor", q="Délai global de grâce (facteur) ?",
         o=[("x2", 2.0), ("x4", 4.0), ("x6", 6.0)], v=1),
    dict(id=16, t="Communication", k="set", m="max_escalations", q="Escalades max par demande ?",
         o=[("1", 1), ("2", 2), ("3", 3)], v=1),
    dict(id=17, t="Communication", k="set", m="default_priority", q="Priorité par défaut ?",
         o=[("0 urgent", 0), ("1 normal", 1), ("2 arrière-plan", 2)], v=1),
    dict(id=18, t="Communication", k="set", m="max_history", q="Historique du bus (messages) ?",
         o=[("500", 500), ("2000", 2000), ("10000", 10000)], v=1),
    # ---- Thème 4 : escalade multi-IA
    dict(id=19, t="Escalade", k="wish", m="rate_limit_policy", q="En cas de 429 (rate limit) ?",
         o=[("Attendre et retenter", "wait"), ("Changer d'IA direct", "switch"),
            ("Pause 5 min", "pause")], v=1),
    dict(id=20, t="Escalade", k="set", m="breaker_threshold", q="Seuil du circuit breaker (échecs) ?",
         o=[("2", 2), ("3", 3), ("5", 5)], v=1),
    dict(id=21, t="Escalade", k="set", m="provider_cooldown", q="Cooldown du breaker (s) ?",
         o=[("30", 30), ("60", 60), ("300", 300)], v=1),
    dict(id=22, t="Escalade", k="wish", m="jules_recovery", q="Jules en panne ?",
         o=[("Exclure jusqu'à nouvel ordre", "manual"), ("Retry auto toutes les 30 min", "auto")], v=1),
    dict(id=23, t="Escalade", k="wish", m="health_watch", q="Vérif santé périodique des IAs ?",
         o=[("Oui, chaque heure", True), ("Non, doctor manuel", False)], v=1),
    dict(id=24, t="Escalade", k="wish", m="cost_aware", q="L'escalade selon le coût ?",
         o=[("Gratuit d'abord", "free_first"), ("Je m'en fous", "dont_care")], v=1),
    # ---- Thème 5 : self-healing
    dict(id=25, t="Self-healing", k="set", m="rollback_policy", q="Politique de rollback ?",
         o=[("Ancien code d'abord", "always"), ("Jamais, repair direct", "never")], v=0),
    dict(id=26, t="Self-healing", k="set", m="max_repairs", q="Réparations max par tâche ?",
         o=[("1", 1), ("3", 3), ("5", 5)], v=1),
    dict(id=27, t="Self-healing", k="chain", m="repairer", q="IA réparatrice en tête ?",
         o=[("Fable 5.1", "fable"), ("OpenRouter", "openrouter"), ("Mistral", "mistral")], v=0),
    dict(id=28, t="Self-healing", k="set", m="repair_temperature", q="Température du Réparateur ?",
         o=[("0.0 chirurgical", 0.0), ("0.2 léger", 0.2), ("0.5 joueur", 0.5)], v=0),
    dict(id=29, t="Self-healing", k="set", m="candidate_test_mode", q="Tests des candidats réparés ?",
         o=[("Basic (payload + vide)", "basic"), ("Paranoid (+ cas limites)", "paranoid")], v=0),
    dict(id=30, t="Self-healing", k="set", m="knowledge_scope", q="Mémoire globale des bugs ?",
         o=[("Partagée", "shared"), ("Par rôle", "role"), ("Désactivée", "off")], v=0),
    dict(id=31, t="Self-healing", k="wish", m="human_fallback", q="Après épuisement du self-healing ?",
         o=[("Échec propre", "fail"), ("Demander à l'humain", "human"),
            ("Remettre en file", "queue")], v=0),
    # ---- Thème 6 : délégation
    dict(id=32, t="Délégation", k="set", m="delegation_validation", q="Validation des délégations ?",
         o=[("Règles rapides", "rules"), ("LLM (le boss juge)", "llm")], v=0),
    dict(id=33, t="Délégation", k="wish", m="cycle_depth", q="Anti-cycle ?",
         o=[("Strict A<->B", "strict"), ("Profondeur 2", "depth2")], v=0),
    dict(id=34, t="Délégation", k="set", m="delegation_reuse", q="Larbin inactif disponible ?",
         o=[("Le réutiliser", "reuse"), ("Créer un nouveau", "new")], v=0),
    dict(id=35, t="Délégation", k="wish", m="delegation_depth", q="Profondeur max des délégations ?",
         o=[("1 niveau", 1), ("2 niveaux", 2), ("Illimité", 99)], v=2),
    dict(id=36, t="Délégation", k="wish", m="boss_delegates_during_repair", q="Boss délègue pendant réparation ?",
         o=[("Oui, parallèle", True), ("Non, réparation prioritaire", False)], v=1),
    # ---- Thème 7 : sandbox
    dict(id=37, t="Sandbox", k="set", m="sandbox_timeout", q="Timeout d'exécution du code (s) ?",
         o=[("5", 5), ("15", 15), ("20", 20), ("60", 60)], v=2),
    dict(id=38, t="Sandbox", k="wish", m="sandbox_network", q="Réseau pour le code des larbins ?",
         o=[("Non", "deny"), ("Lecture seule", "ro"), ("Oui", "allow")], v=0),
    dict(id=39, t="Sandbox", k="wish", m="sandbox_fs", q="Écriture de fichiers ?",
         o=[("Non", "deny"), ("Oui, dans data/ seulement", "data")], v=0),
    dict(id=40, t="Sandbox", k="wish", m="sandbox_imports", q="Imports autorisés ?",
         o=[("Stdlib de base", "stdlib"), ("Liste blanche", "whitelist"), ("Tout", "all")], v=0),
    dict(id=41, t="Sandbox", k="set", m="max_versions", q="Versions de code gardées ?",
         o=[("2", 2), ("3", 3), ("5", 5)], v=1),
    # ---- Thème 8 : providers
    dict(id=42, t="Providers", k="chain", m="coder", q="IA principale pour CODER ?",
         o=[("Fable 5.1", "fable"), ("OpenRouter", "openrouter"),
            ("Gemini", "gemini"), ("Groq", "groq")], v=0),
    dict(id=43, t="Providers", k="chain", m="chat", q="IA pour le CHAT courant ?",
         o=[("Groq", "groq"), ("OpenRouter", "openrouter"),
            ("Gemini", "gemini"), ("Mistral", "mistral")], v=1),
    dict(id=44, t="Providers", k="set", m="http_timeout", q="Timeout HTTP des providers (s) ?",
         o=[("60", 60), ("90", 90), ("120", 120), ("180", 180)], v=1),
    dict(id=45, t="Providers", k="set", m="min_interval", q="Intervalle min entre 2 appels (s) ?",
         o=[("0.2", 0.2), ("0.6", 0.6), ("1.0", 1.0), ("2.0", 2.0)], v=2),
    dict(id=46, t="Providers", k="wish", m="custom_provider", q="Provider custom plus tard ?",
         o=[("Oui via base_url", True), ("Non, presets suffisent", False)], v=0),
    dict(id=47, t="Providers", k="wish", m="jules_role", q="Rôle de Jules ?",
         o=[("Larbin codeur dédié", "dedicated"), ("Dernier recours", "backup"),
            ("Désactivé", "off")], v=1),
    # ---- Thème 9 : budget & monitoring
    dict(id=48, t="Monitoring", k="wish", m="cost_tracking", q="Suivi des coûts ?",
         o=[("Aucun", "none"), ("Compteur d'appels", "calls"),
            ("Estimation $", "dollars"), ("Alerte seuil", "alert")], v=0),
    dict(id=49, t="Monitoring", k="wish", m="alerts", q="Alertes ?",
         o=[("Console seulement", "console"), ("Son sur échec", "sound"),
            ("Telegram", "telegram")], v=0),
    dict(id=50, t="Monitoring", k="wish", m="dashboard", q="Dashboard web live ?",
         o=[("Oui, roadmap n°1", True), ("Plus tard", False),
            ("Non, terminal suffit", "never")], v=1),
]

LETTERS = "ABCDEFGH"


def _order(first: str, pool: list[str]) -> list[str]:
    return [first] + [p for p in pool if p != first]


def build_chains(coder_first: str, repairer_first: str, chat_first: str) -> dict:
    chat = _order(chat_first, ["openrouter", "gemini", "groq", "mistral",
                               "deepseek", "together", "cerebras", "fireworks",
                               "cloudflare", "openai"])
    coder = _order(coder_first, ["fable", "openrouter", "mistral", "gemini"])
    return {
        "repairer": _order(repairer_first, ["fable", "openrouter", "mistral"]),
        "coder": coder,
        "validator": coder,
        "boss": chat[:2],
        "chat": chat,
        "jules-tasks": ["jules"],
    }


def ask(q: dict) -> tuple[int, object]:
    print(f"\n❓ Q{q['id']} — {q['q']}  [{q['t']}]")
    for i, (label, _val) in enumerate(q["o"]):
        star = " ✨" if i == q["v"] else ""
        print(f"   {LETTERS[i]}. {label}{star}")
    while True:
        raw = input(f"   Ta réponse (Entrée = ✨) : ").strip().lower()
        if raw == "":
            return q["v"], q["o"][q["v"]][1]
        if raw.isdigit() and 1 <= int(raw) <= len(q["o"]):
            i = int(raw) - 1
            return i, q["o"][i][1]
        if len(raw) == 1 and raw.upper() in LETTERS[:len(q["o"])]:
            i = LETTERS.index(raw.upper())
            return i, q["o"][i][1]
        print("   ⚠️ réponse invalide")


def run_quiz(quick: bool = False) -> int:
    load_env()
    print("=" * 64)
    print("  🐜 QUIZ DE PERSONNALISATION DE LA COLONIE — 50 questions")
    print("  (Entrée = réponse conseillée ✨ | quick :", quick, ")")
    print("=" * 64)

    settings: dict = {}
    style: dict = {}
    env: dict = {}
    wishes: dict = {}
    chains_sel: dict = {}
    answers: dict[int, str] = {}

    theme = ""
    for q in QUESTIONS:
        if q["t"] != theme:
            theme = q["t"]
            print(f"\n\033[1m— Thème : {theme} —\033[0m")
        if quick:
            idx, val = q["v"], q["o"][q["v"]][1]
        else:
            idx, val = ask(q)
        answers[q["id"]] = LETTERS[idx]
        if q["k"] == "set":
            settings[q["m"]] = val
        elif q["k"] == "style":
            style[q["m"]] = val
        elif q["k"] == "env":
            env[q["m"]] = val
        elif q["k"] == "wish":
            wishes[q["m"]] = val
        elif q["k"] == "chain":
            chains_sel[q["m"]] = val

    # ---------------------------------------------------------- génération
    with open(default_config_path(), encoding="utf-8") as f:
        base = json.load(f)

    min_interval = settings.pop("min_interval", None)
    providers = base.get("providers", {})
    if min_interval is not None:
        for spec in providers.values():
            spec["min_interval"] = min_interval

    config = {
        "settings": {**base.get("settings", {}), **settings},
        "providers": providers,
        "chains": build_chains(chains_sel.get("coder", "fable"),
                               chains_sel.get("repairer", "fable"),
                               chains_sel.get("chat", "openrouter")),
        "style": style,
        "wishes": wishes,
    }
    out = os.path.join(ROOT, "config.perso.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # ---------------------------------------------------------- résumé
    print("\n" + "=" * 64)
    print("  ✅ config.perso.json générée !")
    print("=" * 64)
    compact = " ".join(f"{k}:{v}" for k, v in sorted(answers.items()))
    print(f"\nTes réponses : {compact}")
    print("\nRéglages appliqués :")
    for k, v in settings.items():
        print(f"  ⚙️  {k} = {v}")
    print("Style des larbins :")
    for k, v in style.items():
        print(f"  🎭 {k} = {v}")
    if env:
        print("Affichage (appliquable au .env) :")
        for k, v in env.items():
            print(f"  🖥️  {k} = {v}")
    if wishes:
        print("Roadmap notée :")
        for k, v in wishes.items():
            print(f"  🗺️  {k} = {v}")

    if env and not quick:
        envpath = os.path.join(ROOT, ".env")
        r = input("\nVeux-tu appliquer les préférences d'affichage au .env ? (o/N) : ")
        if r.strip().lower() in ("o", "oui", "y"):
            lines = ["", "# --- style colonie (généré par le quiz) ---"]
            defaults = {"COLONY_VERBOSITY": "normal", "COLONY_NO_EMOJI": "0",
                        "COLONY_MONO": "0"}
            for k, v in env.items():
                if defaults.get(k) != v:
                    lines.append(f"{k}={v}")
            if len(lines) > 2:
                with open(envpath, "a", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                print("  ✅ .env mis à jour")
            else:
                print("  (rien à changer, ce sont les valeurs par défaut)")

    print("\n🚀 Pour lancer TA colonie personnalisée :")
    print("   python3 -m colony.cli --config config.perso.json demo")
    print("   python3 -m colony.cli --config config.perso.json doctor")
    return 0
