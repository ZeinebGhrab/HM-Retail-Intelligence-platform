# ============================================================
# tools/predictions.py — predict_customer_cluster (client existant),
# predict_spend_hypothetical / predict_status_hypothetical (profil
# hypothétique, sans customer_id)
#
# predict_customer_spend(customer_id) et predict_customer_status(customer_id)
# ont existé jusqu'au 2026-08-31 puis ont été retirés : pour un client
# EXISTANT, total_spend et club_member_status sont des faits déjà connus
# (colonnes réelles de customers_features_train, déjà exposées par
# get_customer_profile — voir tools/profile.py) — "prédire" une valeur déjà
# stockée n'est pas une prédiction, c'est juste un lookup déguisé en appel
# ML+LLM coûteux. Confirmé aussi que FULL_SCALE=True (notebooks) a entraîné
# les modèles sur la quasi-totalité des ~1,36M clients, et que le simulateur
# de flux (data/raw/daily/generate_daily_transactions.py) ne fait que
# rejouer des customer_id déjà existants — il n'y a donc aucun client
# "jamais vu à l'entraînement" dans tout le système pour justifier un appel
# modèle plutôt qu'un simple lookup.
#
# predict_customer_cluster reste légitime pour un client existant : aucune
# colonne "cluster" n'existe nulle part dans les données — le modèle K-Means
# est la SEULE source pour cette information, même pour un client qui a
# servi à l'entraîner.
#
# predict_spend_hypothetical / predict_status_hypothetical couvrent le cas où
# une vraie prédiction a un sens : un profil hypothétique/prospectif, sans
# customer_id, pour lequel aucune valeur réelle n'existe nulle part à
# chercher — le modèle est la seule source possible.
#
# ml/serving/app.py n'accepte pas de customer_id (voir ml/serving/schemas.py)
# : il attend les features déjà calculées dans le corps de la requête. Ce
# module fait le pont — lookup du client (Postgres/CSV, cf. tools/profile.py)
# puis appel à /predict/*, ou passage direct des valeurs fournies pour un
# profil hypothétique. ml-serving reste inchangé, comme décidé le 2026-08-28
# (le service ne doit jamais lire Postgres à l'inférence).
# ============================================================
from __future__ import annotations

import requests

from config import ML_SERVING_URL
from tool_signals import unavailable
from tools.profile import get_customer_row, spend_index

_BEHAVIOR_FIELDS = [
    "age",
    "n_transactions",
    "tenure_days",
    "n_distinct_categories",
    "avg_basket_value",
    "purchase_frequency_per_month",
    "recency_days",
]

_SPEND_FIELDS = [
    "age",
    "n_transactions",
    "tenure_days",
    "n_distinct_categories",
    "purchase_frequency_per_month",
    "recency_days",
    "club_member_status",
    "fashion_news_frequency",
    "age_group",
]

_UNAVAILABLE = "Le service de prédiction (ml-serving) est indisponible pour le moment."

# ml-serving charge le modèle "champion" à la demande, au premier appel de
# chaque tâche (_get_bundle), puis le garde en cache pour la vie du
# processus (voir ml/serving/app.py). Constaté en test réel le 2026-08-30 :
# ml/models/classification/model.joblib pèse ~711 Mo (LightGBM+SMOTE, contre
# 481 Ko pour regression et 5,4 Mo pour clustering) — le premier appel après
# un (re)démarrage de ml-serving peut dépasser 15s le temps du chargement
# disque, alors que tous les appels suivants sont quasi instantanés (modèle
# déjà en mémoire). Un timeout de 15s faisait donc systématiquement échouer
# le tout premier appel de la tâche la plus lourde, avant même que la
# prédiction n'ait eu la moindre chance d'aboutir.
_ML_SERVING_TIMEOUT_SEC = 90


def _call_ml_serving(path: str, payload: dict) -> dict | None:
    try:
        resp = requests.post(f"{ML_SERVING_URL}{path}", json=payload, timeout=_ML_SERVING_TIMEOUT_SEC)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def predict_customer_cluster(customer_id: str) -> str:
    row, _ = get_customer_row(customer_id)
    if row is None:
        return unavailable(f"Aucun client trouvé avec l'identifiant {customer_id}.")

    payload = {k: row.get(k) for k in _BEHAVIOR_FIELDS}
    result = _call_ml_serving("/predict/segment", payload)
    if result is None:
        return unavailable(_UNAVAILABLE)

    return (
        f"Segment comportemental (cluster K-Means) du client {customer_id} : "
        f"cluster {result['cluster']} (modèle {result.get('model_version')}). "
        "Voir notebook 07 pour l'interprétation métier des 6 clusters."
    )


def predict_spend_hypothetical(**features) -> str:
    """Profil hypothétique — customer_id volontairement absent de la
    signature : les valeurs viennent entièrement des paramètres extraits par
    le LLM depuis la question (voir tools/SYSTEM_TOOL_CALLING)."""
    missing = [f for f in _SPEND_FIELDS if features.get(f) is None]
    if missing:
        return unavailable(f"Profil incomplet pour cette prédiction — valeurs manquantes : {', '.join(missing)}.")

    payload = {k: features[k] for k in _SPEND_FIELDS}
    result = _call_ml_serving("/predict/spend", payload)
    if result is None:
        return unavailable(_UNAVAILABLE)

    return (
        f"Dépense prédite pour ce profil hypothétique (modèle {result.get('model_version')}) : "
        f"{spend_index(result['predicted_total_spend'])}."
    )


def predict_status_hypothetical(**features) -> str:
    missing = [f for f in _BEHAVIOR_FIELDS if features.get(f) is None]
    if missing:
        return unavailable(f"Profil incomplet pour cette prédiction — valeurs manquantes : {', '.join(missing)}.")

    payload = {k: features[k] for k in _BEHAVIOR_FIELDS}
    result = _call_ml_serving("/predict/club-status", payload)
    if result is None:
        return unavailable(_UNAVAILABLE)

    proba = ", ".join(f"{k}: {v:.0%}" for k, v in result.get("probabilities", {}).items())
    return (
        f"Statut club prédit pour ce profil hypothétique : {result['club_member_status']} "
        f"(probabilités — {proba})."
    )
