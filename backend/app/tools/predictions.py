# ============================================================
# tools/predictions.py — predict_customer_spend, predict_customer_status,
# predict_customer_cluster
#
# ml/serving/app.py n'accepte pas de customer_id (voir ml/serving/schemas.py)
# : il attend les features déjà calculées dans le corps de la requête. Ce
# module fait le pont — lookup du client (Postgres/CSV, cf. tools/profile.py)
# puis appel à /predict/*. ml-serving reste inchangé, comme décidé le
# 2026-08-28 (le service ne doit jamais lire Postgres à l'inférence).
# ============================================================
from __future__ import annotations

import requests

from config import ML_SERVING_URL
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

_UNAVAILABLE = "Le service de prédiction (ml-serving) est indisponible pour le moment."


def _call_ml_serving(path: str, payload: dict) -> dict | None:
    try:
        resp = requests.post(f"{ML_SERVING_URL}{path}", json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def predict_customer_spend(customer_id: str) -> str:
    row, _ = get_customer_row(customer_id)
    if row is None:
        return f"Aucun client trouvé avec l'identifiant {customer_id}."

    payload = {
        **{k: row.get(k) for k in _BEHAVIOR_FIELDS},
        "club_member_status": row.get("club_member_status"),
        "fashion_news_frequency": row.get("fashion_news_frequency"),
        "age_group": row.get("age_group"),
    }
    result = _call_ml_serving("/predict/spend", payload)
    if result is None:
        return _UNAVAILABLE

    return (
        f"Dépense future prédite pour le client {customer_id} (modèle "
        f"{result.get('model_version')}) : {spend_index(result['predicted_total_spend'])}. "
        f"Pour rappel, son indice de dépense passée est de {spend_index(row.get('total_spend'))}."
    )


def predict_customer_status(customer_id: str) -> str:
    row, _ = get_customer_row(customer_id)
    if row is None:
        return f"Aucun client trouvé avec l'identifiant {customer_id}."

    payload = {k: row.get(k) for k in _BEHAVIOR_FIELDS}
    result = _call_ml_serving("/predict/club-status", payload)
    if result is None:
        return _UNAVAILABLE

    proba = ", ".join(f"{k}: {v:.0%}" for k, v in result.get("probabilities", {}).items())
    return (
        f"Statut club prédit pour le client {customer_id} : "
        f"{result['club_member_status']} (probabilités — {proba}). "
        f"Statut actuellement enregistré : {row.get('club_member_status')}."
    )


def predict_customer_cluster(customer_id: str) -> str:
    row, _ = get_customer_row(customer_id)
    if row is None:
        return f"Aucun client trouvé avec l'identifiant {customer_id}."

    payload = {k: row.get(k) for k in _BEHAVIOR_FIELDS}
    result = _call_ml_serving("/predict/segment", payload)
    if result is None:
        return _UNAVAILABLE

    return (
        f"Segment comportemental (cluster K-Means) du client {customer_id} : "
        f"cluster {result['cluster']} (modèle {result.get('model_version')}). "
        "Voir notebook 07 pour l'interprétation métier des 6 clusters."
    )
