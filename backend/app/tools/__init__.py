# ============================================================
# tools/__init__.py — registre des outils + prompt système du routeur.
#
# Palier historique validé par backend/benchmark/ (dataset/
# tool_calling_queries.json, benchmark.py::SYSTEM_TOOL_CALLING) — NOTE DE
# DÉRIVE (2026-08-31) : ce fichier a divergé du dataset de benchmark suite à
# la décision du même jour de retirer predict_customer_spend/
# predict_customer_status (customer_id) au profit de predict_spend_hypothetical/
# predict_status_hypothetical (profil hypothétique, sans customer_id) — voir
# tools/predictions.py pour la justification complète. Le benchmark n'a pas
# été rejoué avec ce nouveau palier ; ses résultats (backend/benchmark/
# results/benchmark_report.json) restent valables pour le palier précédent
# mais ne couvrent plus exactement les outils actuels.
# ============================================================
from __future__ import annotations

from tool_signals import unavailable
from tools.history import get_customer_purchase_history, get_customer_top_categories
from tools.predictions import (
    predict_customer_cluster,
    predict_spend_hypothetical,
    predict_status_hypothetical,
)
from tools.profile import compare_customer_to_segment, get_customer_profile
from tools.semantic import semantic_search

# Outils qui prennent (customer_id) et rien d'autre.
_CUSTOMER_ID_ONLY = {
    "get_customer_profile": get_customer_profile,
    "compare_customer_to_segment": compare_customer_to_segment,
    "predict_customer_cluster": predict_customer_cluster,
}

# Outils "profil hypothétique" : aucun customer_id, uniquement des valeurs
# de features extraites de la question elle-même (voir predictions.py).
_PROFILE_FIELDS = {
    "predict_spend_hypothetical": [
        "age",
        "n_transactions",
        "tenure_days",
        "n_distinct_categories",
        "purchase_frequency_per_month",
        "recency_days",
        "club_member_status",
        "fashion_news_frequency",
        "age_group",
    ],
    "predict_status_hypothetical": [
        "age",
        "n_transactions",
        "tenure_days",
        "n_distinct_categories",
        "avg_basket_value",
        "purchase_frequency_per_month",
        "recency_days",
    ],
}
_PROFILE_TOOLS = {
    "predict_spend_hypothetical": predict_spend_hypothetical,
    "predict_status_hypothetical": predict_status_hypothetical,
}

TOOL_NAMES = (
    list(_CUSTOMER_ID_ONLY)
    + list(_PROFILE_TOOLS)
    + [
        "get_customer_purchase_history",
        "get_customer_top_categories",
        "semantic_search",
    ]
)


SYSTEM_TOOL_CALLING = """\
Tu es un routeur d'outils pour l'assistant client de la plateforme H&M.
Ton UNIQUE rôle est d'analyser la requête de l'utilisateur et de sélectionner
l'outil approprié — tu n'as PAS besoin d'accéder à des données réelles.

Outils disponibles :
- get_customer_profile(customer_id) : ÉTAT ACTUEL/DÉJÀ CONNU d'un client —
  segment de valeur RFM, dépense totale déjà réalisée, ancienneté, récence,
  et son STATUT CLUB ACTUEL. Utilise cet outil pour toute question sur une
  valeur présente ou passée déjà enregistrée d'un client EXISTANT (mots-clés :
  "actuel", "est", "a dépensé", "depuis quand", "quand a-t-il acheté pour la
  dernière fois", "va-t-il quitter le club" — même formulée au futur, s'il
  s'agit d'un client EXISTANT identifié par customer_id, c'est une donnée déjà
  connue, pas une prédiction : ce dataset n'a pas de client "jamais vu à
  l'entraînement", donc aucun modèle ne "prédit" rien de nouveau pour un
  client existant sur son propre statut/dépense).
- get_customer_purchase_history(customer_id, limit) : liste détaillée des
  ARTICLES/TRANSACTIONS individuel(le)s achetés par un client (pas une date
  ou un total agrégé — pour ça, voir get_customer_profile).
- get_customer_top_categories(customer_id) : catégories de produits les plus
  achetées par un client.
- predict_customer_cluster(customer_id) : PRÉDIT à quelle TYPOLOGIE
  COMPORTEMENTALE (cluster K-Means, 0 à 5 — ex. "fidèle à forte valeur",
  "occasionnel", "dormant") appartient un client EXISTANT. Cas particulier :
  contrairement au statut club ou à la dépense, AUCUNE colonne "cluster"
  n'existe dans les données pour aucun client — c'est la seule vraie
  prédiction possible sur un client existant, le modèle K-Means étant l'unique
  source de cette information.
- predict_spend_hypothetical(age, n_transactions, tenure_days,
  n_distinct_categories, purchase_frequency_per_month, recency_days,
  club_member_status, fashion_news_frequency, age_group) : PRÉDIT la dépense
  totale d'un SCÉNARIO CLIENT IMAGINÉ (pas un client existant, pas de
  customer_id) décrit par des caractéristiques explicites dans la question
  (ex. "un client actif depuis 400 jours avec 30 achats..."). Extrais
  uniquement les valeurs explicitement données ; n'invente jamais les
  valeurs manquantes.
- predict_status_hypothetical(age, n_transactions, tenure_days,
  n_distinct_categories, avg_basket_value, purchase_frequency_per_month,
  recency_days) : PRÉDIT le statut club probable (ACTIVE / PRE-CREATE /
  LEFT CLUB) d'un SCÉNARIO CLIENT IMAGINÉ décrit par des caractéristiques
  explicites — mêmes règles que predict_spend_hypothetical.
- compare_customer_to_segment(customer_id) : compare les valeurs DÉJÀ CONNUES
  d'un client existant (dépense, panier moyen, fréquence) à la MOYENNE de son
  segment de valeur RFM — une comparaison de données existantes, jamais une
  prédiction (mots-clés : "par rapport à la moyenne", "plus/moins que les
  autres clients de son segment").
- semantic_search(query) : pour toute question ouverte ou interprétative, ET
  pour TOUTE question sur un client EXISTANT qui ne cite AUCUN customer_id
  précis — y compris les questions générales/plurielles ("mes meilleurs
  clients" sans identifiant), les demandes de conseil/recommandation, et
  tout ce qui ne correspond à aucun outil ci-dessus. Règle stricte : sans
  customer_id explicite ET sans scénario chiffré dans la requête, n'utilise
  JAMAIS un outil get_customer_*/predict_customer_cluster/
  compare_customer_to_segment — utilise semantic_search.

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
- Le nom de l'outil doit être EXACTEMENT l'un des noms listés ci-dessus,
  jamais un nom inventé.\
"""


def run_tool(tool_name: str, parameters: dict, *, customer_id: str | None, question: str) -> str:
    """Exécute l'outil choisi par le routeur.

    customer_id vient TOUJOURS de la requête API (schemas.ChatRequest), pas
    des "parameters" renvoyés par le LLM : on ne fait jamais confiance à un
    modèle pour retranscrire fidèlement un identifiant de 64 caractères — le
    backend l'injecte lui-même. Voir la décision du 2026-08-28 (pas de
    session/auth cette itération : customer_id est fourni explicitement par
    l'appelant de l'API).

    Les outils "profil hypothétique" (_PROFILE_TOOLS) sont l'exception :
    par construction ils n'ont pas de customer_id du tout, uniquement des
    valeurs extraites de la question par le LLM lui-même — voir
    tools/predictions.py."""

    # Filet déterministe : le routeur choisit parfois un outil client alors
    # qu'aucun customer_id n'est réellement fourni par l'appelant (constaté
    # en test réel le 2026-08-31 — 3 des 5 erreurs de routage observées sur
    # 22 cas suivaient exactement ce schéma, malgré une règle explicite dans
    # SYSTEM_TOOL_CALLING). Plutôt que de simplement refuser, on bascule sur
    # semantic_search : la question n'a jamais eu de client en contexte, donc
    # c'est presque toujours une question générale mal aiguillée, pas un
    # oubli de sélection — semantic_search reste la bonne réponse dans les
    # deux cas (elle répond si l'info existe, ou dit honnêtement qu'elle ne
    # trouve rien de pertinent sinon), alors qu'un refus pur perd toute
    # chance de répondre à une vraie question générale.
    if tool_name in _CUSTOMER_ID_ONLY and not customer_id:
        return semantic_search(question)

    if tool_name in _CUSTOMER_ID_ONLY:
        return _CUSTOMER_ID_ONLY[tool_name](customer_id)

    if tool_name in _PROFILE_TOOLS:
        fields = {k: parameters.get(k) for k in _PROFILE_FIELDS[tool_name]}
        return _PROFILE_TOOLS[tool_name](**fields)

    if tool_name == "get_customer_purchase_history":
        if not customer_id:
            return semantic_search(question)
        limit = parameters.get("limit") or 10
        return get_customer_purchase_history(customer_id, limit=int(limit))

    if tool_name == "get_customer_top_categories":
        if not customer_id:
            return semantic_search(question)
        top_n = parameters.get("top_n") or 5
        return get_customer_top_categories(customer_id, top_n=int(top_n))

    if tool_name == "semantic_search":
        return semantic_search(parameters.get("query") or question)

    return unavailable("Cet outil n'est pas reconnu.")
