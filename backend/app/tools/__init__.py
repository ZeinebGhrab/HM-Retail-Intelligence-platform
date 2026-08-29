# ============================================================
# tools/__init__.py — registre des outils + prompt système du routeur.
#
# Reprend le palier de tools validé par backend/benchmark/ (voir
# dataset/tool_calling_queries.json et benchmark.py::SYSTEM_TOOL_CALLING),
# maintenant câblés à de vraies données au lieu d'être simulés.
# ============================================================
from __future__ import annotations

from tools.history import get_customer_purchase_history, get_customer_top_categories
from tools.predictions import (
    predict_customer_cluster,
    predict_customer_spend,
    predict_customer_status,
)
from tools.profile import compare_customer_to_segment, get_customer_profile
from tools.semantic import semantic_search

# Outils qui prennent (customer_id) et rien d'autre.
_CUSTOMER_ID_ONLY = {
    "get_customer_profile": get_customer_profile,
    "compare_customer_to_segment": compare_customer_to_segment,
    "predict_customer_spend": predict_customer_spend,
    "predict_customer_status": predict_customer_status,
    "predict_customer_cluster": predict_customer_cluster,
}

TOOL_NAMES = list(_CUSTOMER_ID_ONLY) + [
    "get_customer_purchase_history",
    "get_customer_top_categories",
    "semantic_search",
]


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
- predict_customer_cluster(customer_id) : PRÉDIT à quel TYPOLOGIE
  COMPORTEMENTALE (cluster K-Means, 0 à 5 — ex. "fidèle à forte valeur",
  "occasionnel", "dormant") appartient un client. Différent de segment_valeur
  (quartile RFM, renvoyé par get_customer_profile) : c'est une classification
  comportementale par un modèle ML, pas une simple valeur stockée.
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
    l'appelant de l'API)."""

    if tool_name in _CUSTOMER_ID_ONLY:
        if not customer_id:
            return "Aucun client n'est actuellement sélectionné pour répondre à cette question."
        return _CUSTOMER_ID_ONLY[tool_name](customer_id)

    if tool_name == "get_customer_purchase_history":
        if not customer_id:
            return "Aucun client n'est actuellement sélectionné pour répondre à cette question."
        limit = parameters.get("limit") or 10
        return get_customer_purchase_history(customer_id, limit=int(limit))

    if tool_name == "get_customer_top_categories":
        if not customer_id:
            return "Aucun client n'est actuellement sélectionné pour répondre à cette question."
        top_n = parameters.get("top_n") or 5
        return get_customer_top_categories(customer_id, top_n=int(top_n))

    if tool_name == "semantic_search":
        return semantic_search(parameters.get("query") or question)

    return "Cet outil n'est pas reconnu."
