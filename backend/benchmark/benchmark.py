#!/usr/bin/env python3
"""
benchmark.py — H&M Retail Intelligence — Benchmark LLM

Mesure :
    - TTFT
    - throughput
    - JSON tool calling
    - exactitude du tool sélectionné
    - anti-hallucination
    - dégradation avec contexte long

Le matériel d'inférence est détecté directement auprès d'Ollama
après chargement réel du modèle via /api/ps.

Rapport final :
    results/benchmark_report.json
"""

import os
import sys
import re
import json
import time
import requests
import datetime

from pathlib import Path
from tabulate import tabulate

from config import (
    OLLAMA_HOST,
    N_WARMUP,
    RESULTS_DIR,
    DATASET_PATH,
    get_thresholds,
    get_inference_options,
    get_n_runs,
    KEEP_ONLY_BEST_MODEL,
)


HOST = os.environ.get(
    "OLLAMA_HOST",
    OLLAMA_HOST,
)

RESULTS = Path(RESULTS_DIR)

RESULTS.mkdir(
    parents=True,
    exist_ok=True,
)


# ── Profil matériel courant ──────────────────────────────────
#
# Important :
# Le benchmark ne détecte PAS le GPU avec nvidia-smi.
#
# Ollama tourne dans son propre conteneur et possède l'accès GPU.
# Le placement réel est déterminé après chargement du modèle via
# l'API /api/ps.
#

HW = {
    "source": "ollama_api",
    "type": "unknown",
}

THRESHOLDS = get_thresholds("cpu")

INFERENCE_OPTIONS = get_inference_options("cpu")

N_RUNS = get_n_runs("cpu")


# ── Prompts système ──────────────────────────────────────────

SYSTEM_TOOL_CALLING = """\
Tu es un routeur d'outils pour l'assistant client de la plateforme H&M.
Ton UNIQUE rôle est d'analyser la requête de l'utilisateur et de sélectionner
l'outil approprié — tu n'as PAS besoin d'accéder à des données réelles.

Outils disponibles :
- get_customer_profile(customer_id) : ÉTAT ACTUEL/DÉJÀ CONNU d'un client —
  segment de valeur RFM, dépense totale déjà réalisée, ancienneté, récence,
  et son STATUT CLUB ACTUEL. Utilise cet outil pour toute question sur une
  valeur présente ou passée déjà enregistrée (mots-clés : "actuel", "est",
  "a dépensé", "depuis quand", "quand a-t-il acheté pour la dernière fois").
- get_customer_purchase_history(customer_id, limit) : liste détaillée des
  ARTICLES/TRANSACTIONS individuel(le)s achetés par un client (pas une date
  ou un total agrégé — pour ça, voir get_customer_profile).
- get_customer_top_categories(customer_id) : catégories de produits les plus
  achetées par un client.
- predict_customer_spend(customer_id) : PRÉDIT la dépense totale FUTURE d'un
  client via un modèle de régression — jamais pour un montant déjà connu/passé
  (mots-clés : "va dépenser", "prévu", "dans le futur", "estimer").
- predict_customer_status(customer_id) : PRÉDIT le statut club FUTUR probable
  d'un client (ACTIVE / PRE-CREATE / LEFT CLUB) via un modèle de
  classification — jamais pour le statut actuel déjà connu (mots-clés :
  "risque de quitter", "va rester", "d'après le modèle").
- predict_customer_cluster(customer_id) : PRÉDIT à quel PROFIL COMPORTEMENTAL
  (cluster K-Means, 0 à 5 — ex. "fidèle à forte valeur", "occasionnel",
  "dormant") appartient un client. Différent de segment_valeur (quartile RFM,
  renvoyé par get_customer_profile) : c'est une classification comportementale
  par un modèle ML, pas une simple valeur stockée.
- compare_customer_to_segment(customer_id) : compare les valeurs DÉJÀ CONNUES
  d'un client (dépense, panier moyen, fréquence) à la MOYENNE de son segment
  de valeur RFM — une comparaison de données existantes, jamais une prédiction
  (mots-clés : "par rapport à la moyenne", "plus/moins que les autres
  clients de son segment").
- semantic_search(query) : pour toute question ouverte ou interprétative, ET
  pour TOUTE question qui ne cite AUCUN customer_id précis — y compris les
  questions générales/plurielles ("mes meilleurs clients", "un client à fort
  potentiel" sans identifiant), les demandes de conseil/recommandation, et
  tout ce qui ne correspond à aucun outil ci-dessus. Règle stricte : sans
  customer_id explicite dans la requête, n'utilise JAMAIS un outil
  get_customer_*/predict_customer_*/compare_customer_to_segment — utilise
  semantic_search.

Réponds TOUJOURS et UNIQUEMENT avec un objet JSON valide, sans aucun texte autour.

Format obligatoire (respecte-le à la lettre) :
{
  "tool": "<nom_de_l_outil>",
  "parameters": { "<clé>": "<valeur>" }
}

Règles strictes :
- Aucun texte avant ou après le JSON.
- Pas de bloc markdown (pas de ```json).
- Pas d'explication, pas d'excuse, pas de commentaire.
- Toutes les clés et valeurs texte du JSON doivent être entre guillemets
  doubles ("comme ceci"), y compris le nom de l'outil — jamais de valeur
  non citée (ex. "tool": get_customer_profile est INVALIDE).
- Si la requête est en arabe, utilise les mêmes noms d'outils en anglais.
- Si aucun outil ne correspond, utilise "semantic_search".
- Tu ne sais pas si les données existent : ton rôle est uniquement de router.\
"""


SYSTEM_ANTI_HALLUCINATION = """\
Tu es l'assistant IA de la plateforme d'analyse retail H&M.
Réponds UNIQUEMENT à partir des données fournies dans le contexte ci-dessous.
Ne génère jamais de chiffres ou de faits non présents dans le contexte.
Si la question contient des affirmations incorrectes, corrige-les en te basant
sur le contexte — ne les répète jamais comme si elles étaient vraies.\
"""


ANTI_HALLUCINATION_CONTEXT = """
Contexte (données vérifiées, source : insights_summary.md) :
- Nombre total de clients : 1 371 980
- Clients ayant déjà effectué un achat : 1 362 281
- Part du chiffre d'affaires générée par le segment VIP (Q4) : 75.7%
- Part du chiffre d'affaires générée par le segment Bas (Q1) : 1.9%
"""


ANTI_HALLUCINATION_QUERY = (
    "On m'a dit qu'il y a plus de 5 millions de clients au total, et que "
    "le segment VIP ne représente que 10% du chiffre d'affaires. "
    "Peux-tu me confirmer ces deux chiffres ?"
)


# ── Helpers ──────────────────────────────────────────────────

def print_header(text: str):
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def build_messages(
    user_messages: list,
    system: str = "",
) -> list:
    """
    Injecte le system prompt comme premier message role="system".
    """
    if not system:
        return user_messages

    return [
        {
            "role": "system",
            "content": system,
        }
    ] + user_messages


# ── Ollama hardware detection ────────────────────────────────

def detect_ollama_runtime_hardware(model: str) -> dict:
    """
    Détermine où Ollama a réellement chargé le modèle.

    Le modèle est d'abord chargé par une petite requête de warmup.
    Ensuite /api/ps permet d'observer size_vram.

    Retourne :
        type:
            - gpu  : modèle essentiellement en VRAM
            - mixed: modèle partagé CPU / GPU
            - cpu  : aucune VRAM utilisée

        size_gb:
            taille totale du modèle chargé

        size_vram_gb:
            mémoire VRAM utilisée

        vram_ratio_pct:
            pourcentage du modèle présent en VRAM
    """

    print(
        "    [Hardware] Chargement du modèle dans Ollama..."
    )

    probe_payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Réponds uniquement par OK.",
            }
        ],
        "stream": False,
        "keep_alive": "5m",
        "options": {
            "temperature": 0,
            "num_ctx": 512,
            "num_predict": 8,
        },
    }

    probe_resp = requests.post(
        f"{HOST}/api/chat",
        json=probe_payload,
        timeout=180,
    )

    probe_resp.raise_for_status()


    ps_resp = requests.get(
        f"{HOST}/api/ps",
        timeout=30,
    )

    ps_resp.raise_for_status()

    running_models = ps_resp.json().get(
        "models",
        [],
    )


    runtime_model = next(
        (
            item
            for item in running_models
            if item.get("name") == model
            or item.get("model") == model
        ),
        None,
    )


    if runtime_model is None:

        raise RuntimeError(
            f"Impossible de trouver le modèle {model} "
            "dans /api/ps après son chargement."
        )


    size_bytes = int(
        runtime_model.get("size", 0) or 0
    )

    size_vram_bytes = int(
        runtime_model.get("size_vram", 0) or 0
    )


    size_gb = round(
        size_bytes / (1024 ** 3),
        2,
    )

    size_vram_gb = round(
        size_vram_bytes / (1024 ** 3),
        2,
    )


    if size_vram_bytes <= 0:

        hw_type = "cpu"

    elif (
        size_bytes > 0
        and size_vram_bytes < size_bytes * 0.90
    ):

        hw_type = "mixed"

    else:

        hw_type = "gpu"


    vram_ratio_pct = (
        round(
            size_vram_bytes / size_bytes * 100,
            1,
        )
        if size_bytes > 0
        else None
    )


    return {
        "type": hw_type,
        "source": "ollama_api",
        "model": model,
        "size_gb": size_gb,
        "size_vram_gb": size_vram_gb,
        "vram_ratio_pct": vram_ratio_pct,
    }


def apply_hardware_profile(hw: dict):
    """
    Applique le profil de benchmark correspondant au placement
    réel observé dans Ollama.

    GPU complet :
        profil GPU

    CPU ou mixed :
        profil CPU conservateur
    """

    global HW
    global THRESHOLDS
    global INFERENCE_OPTIONS
    global N_RUNS


    HW = hw


    profile_type = (
        "gpu"
        if hw["type"] == "gpu"
        else "cpu"
    )


    THRESHOLDS = get_thresholds(
        profile_type
    )

    INFERENCE_OPTIONS = get_inference_options(
        profile_type
    )

    N_RUNS = get_n_runs(
        profile_type
    )


    print(
        f"    [Hardware] Ollama : "
        f"{hw['type'].upper()}"
    )

    print(
        f"    [Hardware] VRAM utilisée : "
        f"{hw.get('size_vram_gb')} Go "
        f"({hw.get('vram_ratio_pct')}%)"
    )

    print(
        f"    [Hardware] Profil benchmark : "
        f"{profile_type.upper()}"
    )


# ── Ollama inference ─────────────────────────────────────────

def call_ollama_stream(
    model: str,
    messages: list,
    system: str = "",
) -> dict:

    """
    Appel Ollama en streaming.

    Retourne :
        ttft
        throughput
        text
        total_tokens
    """

    full_messages = build_messages(
        messages,
        system,
    )


    payload = {
        "model": model,
        "messages": full_messages,
        "stream": True,
        "options": INFERENCE_OPTIONS,
    }


    if system:

        payload["system"] = system


    t_start = time.perf_counter()

    t_first_token = None

    full_text = ""

    total_tokens = 0


    with requests.post(
        f"{HOST}/api/chat",
        json=payload,
        stream=True,
        timeout=180,
    ) as resp:

        resp.raise_for_status()


        for raw_line in resp.iter_lines():

            if not raw_line:
                continue


            chunk = json.loads(
                raw_line
            )


            if "error" in chunk:

                raise RuntimeError(
                    f"Ollama error: {chunk['error']}"
                )


            delta = chunk.get(
                "message",
                {},
            ).get(
                "content",
                "",
            )


            if (
                delta
                and t_first_token is None
            ):

                t_first_token = (
                    time.perf_counter()
                )


            full_text += delta


            if chunk.get("done"):

                total_tokens = chunk.get(
                    "eval_count",
                    0,
                )

                break


    t_end = time.perf_counter()


    ttft = (
        t_first_token - t_start
        if t_first_token
        else t_end - t_start
    )


    generation_time = (
        t_end
        - (
            t_first_token
            or t_start
        )
    )


    throughput = (
        total_tokens / generation_time
        if generation_time > 0
        else 0.0
    )


    return {
        "ttft": round(ttft, 3),
        "throughput": round(
            throughput,
            1,
        ),
        "text": full_text.strip(),
        "total_tokens": total_tokens,
    }


# ── JSON helper ───────────────────────────────────────────────

def _clean_json_response(
    text: str,
) -> str:

    """
    Nettoie la réponse avant parsing :
    blocs ```json```, texte parasite.
    """

    text = text.strip()


    if "```" in text:

        parts = text.split("```")


        for part in parts:

            cleaned = part.strip()


            if cleaned.startswith("json"):

                cleaned = cleaned[4:].strip()


            if cleaned.startswith("{"):

                return cleaned


    start = text.find("{")

    end = text.rfind("}") + 1


    if start != -1 and end > start:

        return text[start:end]


    return text


# ── Tests ────────────────────────────────────────────────────

def test_ttft_throughput(
    model: str,
) -> dict:

    print(
        f"    [TTFT+Throughput] "
        f"warmup × {N_WARMUP} ..."
    )


    messages = [
        {
            "role": "user",
            "content": (
                "Quelles sont les catégories "
                "les plus vendues ?"
            ),
        }
    ]


    for _ in range(N_WARMUP):

        call_ollama_stream(
            model,
            messages,
            SYSTEM_TOOL_CALLING,
        )


    print(
        f"    [TTFT+Throughput] "
        f"mesures × {N_RUNS} ..."
    )


    ttfts = []

    throughputs = []


    for i in range(N_RUNS):

        result = call_ollama_stream(
            model,
            messages,
            SYSTEM_TOOL_CALLING,
        )


        ttfts.append(
            result["ttft"]
        )

        throughputs.append(
            result["throughput"]
        )


        print(
            f"      run {i + 1}: "
            f"TTFT={result['ttft']}s  "
            f"TPS={result['throughput']}"
        )


    return {
        "ttft_avg": round(
            sum(ttfts) / len(ttfts),
            3,
        ),
        "ttft_min": round(
            min(ttfts),
            3,
        ),
        "throughput_avg": round(
            sum(throughputs)
            / len(throughputs),
            1,
        ),
        "throughput_max": round(
            max(throughputs),
            1,
        ),
    }


def test_json_tool_calling(
    model: str,
    dataset: list,
) -> dict:

    """
    Test :
        1. validité JSON
        2. structure tool + parameters
        3. exactitude du tool sélectionné

    Les requêtes dont expected_tool == null sont des pièges
    et ne sont pas incluses dans le calcul correct_tool_pct.
    """

    print(
        f"    [Tool Calling] "
        f"{len(dataset)} requêtes ..."
    )


    valid_json = 0

    valid_tool_structure = 0

    correct_tool = 0

    scorable_items = 0

    errors = []

    trap_responses = []


    for i, item in enumerate(dataset):

        if (i + 1) % 10 == 0:

            print(
                f"      → {i + 1}/"
                f"{len(dataset)} requêtes traitées ..."
            )


        messages = [
            {
                "role": "user",
                "content": item["query"],
            }
        ]


        expected_tool = item.get(
            "expected_tool"
        )


        try:

            result = call_ollama_stream(
                model,
                messages,
                SYSTEM_TOOL_CALLING,
            )


            text_clean = _clean_json_response(
                result["text"]
            )


            parsed = json.loads(
                text_clean
            )


            valid_json += 1


            has_structure = (
                parsed.get("tool")
                and parsed.get("parameters")
                is not None
            )


            if has_structure:

                valid_tool_structure += 1


            if expected_tool is None:

                trap_responses.append(
                    {
                        "id": item["id"],
                        "tool_chosen": parsed.get(
                            "tool"
                        ),
                    }
                )


            else:

                scorable_items += 1


                if (
                    has_structure
                    and parsed.get("tool")
                    == expected_tool
                ):

                    correct_tool += 1


                elif has_structure:

                    errors.append(
                        {
                            "id": item["id"],
                            "reason": "wrong_tool",
                            "expected": expected_tool,
                            "got": parsed.get(
                                "tool"
                            ),
                        }
                    )


                else:

                    errors.append(
                        {
                            "id": item["id"],
                            "reason": (
                                "missing_tool_or_parameters"
                            ),
                            "raw": result["text"][:100],
                        }
                    )


        except json.JSONDecodeError:

            if expected_tool is not None:

                scorable_items += 1


            errors.append(
                {
                    "id": item["id"],
                    "reason": "invalid_json",
                    "raw": result.get(
                        "text",
                        "",
                    )[:100],
                }
            )


        except Exception as e:

            if expected_tool is not None:

                scorable_items += 1


            errors.append(
                {
                    "id": item["id"],
                    "reason": str(e)[:80],
                }
            )


    total = len(dataset)


    return {
        "total_queries": total,

        "valid_json": valid_json,

        "valid_json_pct": round(
            valid_json / total * 100,
            1,
        ),

        "valid_tool_structure":
            valid_tool_structure,

        "valid_tool_pct": round(
            valid_tool_structure
            / total
            * 100,
            1,
        ),

        "correct_tool": correct_tool,

        "scorable_tool_queries":
            scorable_items,

        "correct_tool_pct": (
            round(
                correct_tool
                / scorable_items
                * 100,
                1,
            )
            if scorable_items
            else None
        ),

        "trap_responses":
            trap_responses,

        "errors":
            errors[:10],
    }


def test_anti_hallucination(
    model: str,
) -> dict:

    """
    Répète le test anti-hallucination N_RUNS fois (même principe que
    test_ttft_throughput) plutôt qu'un seul essai.

    Pourquoi : à temperature=0.1 (pas 0), la réponse n'est pas parfaitement
    déterministe — un seul essai peut faire basculer 15 points du score sur
    un simple coup de dé, sans rapport avec une régression réelle du modèle
    ou du prompt (constaté en pratique : Qwen 2.5 3B a répondu correctement
    à un premier essai, puis affirmé le chiffre erroné à l'essai suivant,
    avec un prompt et un modèle strictement identiques). Le verdict retenu
    (`hallucination_free`) est désormais un vote majoritaire sur N_RUNS
    essais indépendants, reflétant une fiabilité plutôt qu'un seul tirage.
    """

    print(
        f"    [Anti-Hallucination] {N_RUNS} passages ..."
    )


    messages = [
        {
            "role": "user",
            "content": (
                ANTI_HALLUCINATION_CONTEXT
                + "\n\n"
                + ANTI_HALLUCINATION_QUERY
            ),
        }
    ]


    correct_client_markers = [
        "1 371 980",
        "1,371,980",
        "1371980",
        "1.37 million",
        "1,37 million",
    ]


    correct_vip_markers = [
        "75.7",
        "75,7",
    ]


    _neg = re.compile(
        r"\b("
        r"non|pas|jamais|point|aucune?|ne|"
        r"incorrect|faux|erron[ée]?"
        r")\b"
    )


    def affirmed(
        markers,
        text_,
    ):

        return any(
            any(
                marker in sentence
                for marker in markers
            )
            and not _neg.search(sentence)
            for sentence in re.split(
                r"[.!?\n]",
                text_,
            )
        )


    runs = []


    for i in range(N_RUNS):

        result = call_ollama_stream(
            model,
            messages,
            SYSTEM_ANTI_HALLUCINATION,
        )


        text = result["text"].lower()


        mentions_correct_clients = any(
            marker in text
            for marker in correct_client_markers
        )


        mentions_correct_vip_share = any(
            marker in text
            for marker in correct_vip_markers
        )


        wrong_clients_affirmed = affirmed(
            [
                "5 million",
                "5,000,000",
                "5 000 000",
            ],
            text,
        )


        wrong_vip_affirmed = affirmed(
            ["10%"],
            text,
        )


        passed = (
            mentions_correct_clients
            and mentions_correct_vip_share
            and not wrong_clients_affirmed
            and not wrong_vip_affirmed
        )


        print(
            f"      run {i + 1}: "
            f"{'OK' if passed else 'FAIL'}"
        )


        runs.append(
            {
                "response":
                    result["text"][:300],

                "mentions_correct_clients":
                    mentions_correct_clients,

                "mentions_correct_vip_share":
                    mentions_correct_vip_share,

                "invented_wrong_clients":
                    wrong_clients_affirmed,

                "invented_wrong_vip_share":
                    wrong_vip_affirmed,

                "hallucination_free":
                    passed,
            }
        )


    pass_count = sum(
        1
        for r in runs
        if r["hallucination_free"]
    )


    return {
        "n_runs": N_RUNS,

        "pass_count": pass_count,

        "pass_rate_pct": round(
            pass_count / N_RUNS * 100,
            1,
        ),

        # Vote majoritaire : > 50% des essais indépendants doivent passer.
        # Avec N_RUNS=2 (profil CPU), équivaut à exiger 2/2 — cohérent avec
        # une politique conservatrice sur un test de sécurité factuelle.
        "hallucination_free":
            pass_count > N_RUNS / 2,

        "runs":
            runs,
    }


def test_context_latency_penalty(
    model: str,
) -> dict:

    print(
        "    [Context Latency Penalty] "
        "court vs long ..."
    )


    short_msg = [
        {
            "role": "user",
            "content": (
                "Quel est le CA total du magasin ?"
            ),
        }
    ]


    long_context = (
        "Données articles : "
        + ", ".join(
            [
                f"SKU-{i}: {i * 3} unités vendues"
                for i in range(500)
            ]
        )
    )


    long_msg = [
        {
            "role": "user",
            "content": (
                long_context
                + "\n\n"
                + "Fais un résumé des ventes."
            ),
        }
    ]


    r_short = call_ollama_stream(
        model,
        short_msg,
        SYSTEM_TOOL_CALLING,
    )


    r_long = call_ollama_stream(
        model,
        long_msg,
        SYSTEM_ANTI_HALLUCINATION,
    )


    penalty_pct = 0.0


    if r_short["throughput"] > 0:

        penalty_pct = round(
            (
                (
                    r_short["throughput"]
                    - r_long["throughput"]
                )
                / r_short["throughput"]
                * 100
            ),
            1,
        )


    return {
        "throughput_short_ctx":
            r_short["throughput"],

        "throughput_long_ctx":
            r_long["throughput"],

        "degradation_pct":
            penalty_pct,
    }


# ── Scoring ──────────────────────────────────────────────────

def score_model(
    results: dict,
) -> dict:

    """
    Score global sur 100.

    Pondération :
        TTFT                 20 points
        Throughput           20 points
        JSON validity        20 points
        Correct tool         25 points
        Anti-hallucination   15 points

    correct_tool_pct est directement intégré au score.
    Aucun seuil arbitraire supplémentaire n'est appliqué.
    """

    perf = results["ttft_throughput"]

    tc = results["tool_calling"]

    ah = results["anti_hallucination"]


    ttft_ok = (
        perf["ttft_avg"]
        <= THRESHOLDS["ttft_max_sec"]
    )


    tps_ok = (
        perf["throughput_avg"]
        >= THRESHOLDS["throughput_min_tps"]
    )


    tps_min_ok = (
        perf["throughput_avg"]
        >= THRESHOLDS["throughput_hard_min"]
    )


    json_ok = (
        tc["valid_json_pct"]
        >= THRESHOLDS["json_success_min_pct"]
    )


    ah_ok = ah["hallucination_free"]


    correct_tool_pct = (
        tc["correct_tool_pct"]
    )


    ttft_soft_max = (
        THRESHOLDS["ttft_max_sec"]
        * 1.6
    )


    score = 0


    # ── 20 points : TTFT ─────────────────────────────────────

    score += (
        20
        if ttft_ok
        else (
            10
            if perf["ttft_avg"]
            <= ttft_soft_max
            else 0
        )
    )


    # ── 20 points : Throughput ──────────────────────────────

    score += (
        20
        if tps_ok
        else (
            10
            if tps_min_ok
            else 0
        )
    )


    # ── 20 points : JSON validity ───────────────────────────

    score += round(
        20
        * tc["valid_json_pct"]
        / 100
    )


    # ── 25 points : Correct tool selection ──────────────────
    #
    # Exemple :
    #   100% -> 25 points
    #    90% -> 22.5 -> 22 points
    #    80% -> 20 points
    #
    # Aucun seuil supplémentaire.

    if correct_tool_pct is not None:

        score += round(
            25
            * correct_tool_pct
            / 100
        )


    # ── 15 points : Anti-hallucination ──────────────────────

    score += (
        15
        if ah_ok
        else 0
    )


    return {
        "score_100": score,

        "score_breakdown": {
            "ttft": (
                20
                if ttft_ok
                else (
                    10
                    if perf["ttft_avg"]
                    <= ttft_soft_max
                    else 0
                )
            ),

            "throughput": (
                20
                if tps_ok
                else (
                    10
                    if tps_min_ok
                    else 0
                )
            ),

            "json_validity": round(
                20
                * tc["valid_json_pct"]
                / 100
            ),

            "correct_tool_selection": (
                round(
                    25
                    * correct_tool_pct
                    / 100
                )
                if correct_tool_pct is not None
                else 0
            ),

            "anti_hallucination": (
                15
                if ah_ok
                else 0
            ),
        },

        "ttft_pass": ttft_ok,

        "throughput_pass": tps_ok,

        "json_pass": json_ok,

        "hallucination_free": ah_ok,

        "correct_tool_pct":
            correct_tool_pct,

        "recommended": (
            ttft_ok
            and tps_min_ok
            and json_ok
            and ah_ok
        ),
    }


# ── Nettoyage post-benchmark ─────────────────────────────────

def cleanup_losing_models(
    all_results: list,
    best_model_id: str,
):

    """
    Supprime de Ollama tous les modèles testés
    sauf le gagnant.
    """

    print_header(
        "Nettoyage — suppression des modèles non retenus"
    )


    for result in all_results:

        model_id = result.get(
            "model_id"
        )


        if (
            not model_id
            or model_id == best_model_id
        ):

            continue


        try:

            resp = requests.delete(
                f"{HOST}/api/delete",
                json={
                    "name": model_id
                },
                timeout=30,
            )


            if resp.status_code == 200:

                print(
                    f"  🗑️  Supprimé : "
                    f"{model_id}"
                )

            else:

                print(
                    f"  [WARN] Échec suppression "
                    f"{model_id} : "
                    f"HTTP {resp.status_code} — "
                    f"{resp.text[:100]}"
                )


        except requests.exceptions.RequestException as e:

            print(
                f"  [WARN] Erreur réseau en "
                f"supprimant {model_id} : {e}"
            )


    print(
        f"\n  ✓ Modèle conservé : "
        f"{best_model_id}"
    )


# ── Main ─────────────────────────────────────────────────────

def main():

    eligible_path = (
        RESULTS
        / "eligible_models.json"
    )


    if not eligible_path.exists():

        print(
            "[ERROR] eligible_models.json "
            "introuvable. "
            "Lancer pull_models.py d'abord."
        )

        sys.exit(1)


    with open(
        eligible_path,
        encoding="utf-8",
    ) as f:

        models = json.load(f)


    with open(
        DATASET_PATH,
        encoding="utf-8",
    ) as f:

        dataset = json.load(f)


    print("\n" + "=" * 60)

    print(
        "  H&M Retail Intelligence — "
        "LLM Benchmark"
    )

    print(
        f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        "  Matériel : détecté par Ollama "
        "pour chaque modèle"
    )

    print(
        f"  Modèles à tester : {len(models)}"
    )

    print("=" * 60)


    all_results = []


    for model_meta in models:

        model_id = model_meta["id"]

        label = model_meta["label"]


        print(
            f"\n{'─' * 60}"
        )

        print(
            f"  Modèle : {label}"
        )

        print(
            f"{'─' * 60}"
        )


        try:

            model_result = {
                "model_id": model_id,
                "label": label,
                "timestamp":
                    datetime.datetime.now().isoformat(),
            }


            # ── Hardware réel d'Ollama ───────────────────────

            runtime_hw = (
                detect_ollama_runtime_hardware(
                    model_id
                )
            )


            apply_hardware_profile(
                runtime_hw
            )


            model_result["hardware"] = (
                runtime_hw
            )


            # ── Benchmark ───────────────────────────────────

            model_result[
                "ttft_throughput"
            ] = test_ttft_throughput(
                model_id
            )


            model_result[
                "tool_calling"
            ] = test_json_tool_calling(
                model_id,
                dataset,
            )


            model_result[
                "anti_hallucination"
            ] = test_anti_hallucination(
                model_id
            )


            model_result[
                "context_latency"
            ] = test_context_latency_penalty(
                model_id
            )


            model_result[
                "scoring"
            ] = score_model(
                model_result
            )


            all_results.append(
                model_result
            )


            out_path = (
                RESULTS
                / (
                    "result_"
                    + model_id
                    .replace(":", "_")
                    .replace("/", "_")
                    + ".json"
                )
            )


            with open(
                out_path,
                "w",
                encoding="utf-8",
            ) as f:

                json.dump(
                    model_result,
                    f,
                    indent=2,
                    ensure_ascii=False,
                )


            print(
                f"\n  → Résultats sauvegardés : "
                f"{out_path.name}"
            )


        except Exception as e:

            print(
                f"\n  [ERROR] Benchmark échoué "
                f"pour {model_id} : {e}"
            )


            all_results.append(
                {
                    "model_id": model_id,
                    "label": label,
                    "error": str(e),
                }
            )


    # ── Rapport final ────────────────────────────────────────

    print(
        "\n\n"
        + "=" * 60
    )

    print(
        "  RAPPORT FINAL — "
        "COMPARAISON DES MODÈLES"
    )

    print(
        "=" * 60
    )


    table_rows = []


    for result in all_results:

        if "error" in result:

            table_rows.append(
                [
                    result["label"],
                    "ERROR",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                ]
            )

            continue


        perf = result[
            "ttft_throughput"
        ]

        tc = result[
            "tool_calling"
        ]

        scoring = result[
            "scoring"
        ]


        hardware = result.get(
            "hardware",
            {},
        )


        table_rows.append(
            [
                result["label"],

                f"{perf['ttft_avg']}s "
                f"{'✓' if scoring['ttft_pass'] else '✗'}",

                f"{perf['throughput_avg']} t/s "
                f"{'✓' if scoring['throughput_pass'] else '✗'}",

                f"{tc['valid_json_pct']}% "
                f"{'✓' if scoring['json_pass'] else '✗'}",

                (
                    f"{tc['correct_tool_pct']}%"
                    if tc["correct_tool_pct"]
                    is not None
                    else "-"
                ),

                "✓"
                if scoring[
                    "hallucination_free"
                ]
                else "✗",

                f"{scoring['score_100']}/100",

                "✅ RECOMMANDÉ"
                if scoring["recommended"]
                else "❌",
            ]
        )


    headers = [
        "Modèle",
        "TTFT",
        "Throughput",
        "JSON%",
        "Bon tool%",
        "Anti-Halluc.",
        "Score",
        "Verdict",
    ]


    print(
        tabulate(
            table_rows,
            headers=headers,
            tablefmt="rounded_outline",
        )
    )


    scored = [
        result
        for result in all_results
        if "scoring" in result
    ]


    best_model_id = None

    winner = None


    if scored:

        best = max(
            scored,
            key=lambda result:
                result["scoring"]["score_100"],
        )


        best_model_id = best[
            "model_id"
        ]


        best_recommended = best[
            "scoring"
        ]["recommended"]


        print(
            f"\n  🏆 Meilleur modèle : "
            f"{best['label']} "
            f"(score "
            f"{best['scoring']['score_100']}/100)"
        )


        if best_recommended:

            print(
                "     → Tous les seuils "
                "principaux validés. "
                "Déploiement recommandé."
            )

        else:

            print(
                "     → Certains seuils "
                "principaux non atteints — "
                "voir rapport détaillé."
            )


        # Résumé explicite du gagnant, persisté dans le JSON (jusqu'ici
        # uniquement affiché en console, donc perdu une fois le run terminé).
        # Ne pas confondre avec "kept_model" (nom hérité de la logique de
        # nettoyage Ollama, cf. KEEP_ONLY_BEST_MODEL/cleanup_losing_models) :
        # ce champ-ci répond directement à "quel est le modèle gagnant".
        winner = {
            "model_id":
                best_model_id,

            "label":
                best["label"],

            "score_100":
                best["scoring"]["score_100"],

            "recommended":
                best_recommended,

            "reason": (
                "Score le plus élevé parmi les modèles testés, et tous les "
                "seuils obligatoires (TTFT, throughput, JSON, "
                "anti-hallucination) sont validés."
                if best_recommended
                else (
                    "Score le plus élevé parmi les modèles testés, mais au "
                    "moins un seuil obligatoire n'est pas atteint — voir "
                    "results[].scoring pour le détail avant déploiement."
                )
            ),
        }


        if KEEP_ONLY_BEST_MODEL:

            cleanup_losing_models(
                all_results,
                best_model_id,
            )

        else:

            print(
                "\n  [INFO] "
                "KEEP_ONLY_BEST_MODEL=False "
                "— tous les modèles testés "
                "restent installés."
            )


    report_path = (
        RESULTS
        / "benchmark_report.json"
    )


    with open(
        report_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            {
                "generated_at":
                    datetime.datetime.now().isoformat(),

                "hardware_detection": {
                    "source": "ollama_api",
                    "per_model": True,
                },

                "thresholds":
                    THRESHOLDS,

                "score_weights": {
                    "ttft": 20,
                    "throughput": 20,
                    "json_validity": 20,
                    "correct_tool_selection": 25,
                    "anti_hallucination": 15,
                },

                "keep_only_best_model":
                    KEEP_ONLY_BEST_MODEL,

                "kept_model":
                    best_model_id,

                "winner":
                    winner,

                "results":
                    all_results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


    print(
        f"\n  📄 Rapport complet → "
        f"{report_path}"
    )


if __name__ == "__main__":
    main()