# ============================================================
# tools/profile.py — get_customer_profile, compare_customer_to_segment
#
# Postgres (customers_features_train) d'abord, repli CSV
# (backend/app/data/customers_features.csv, export notebook 04 §14) sinon —
# décision du 2026-08-28.
# ============================================================
from __future__ import annotations

import db
import data_store

# Le prix (donc total_spend, avg_basket_value) est pré-normalisé dans le
# dataset Kaggle H&M — ce ne sont PAS des montants en devise réelle. Le
# system prompt (rag_pipeline.SYSTEM_ANSWER) l'interdit déjà, mais le LLM a
# quand même inventé un "(soit environ 3.09$)" en test réel (2026-08-29) —
# répéter l'avertissement directement dans chaque valeur ci-dessous, pas
# seulement dans le system prompt, réduit nettement la récidive.
def spend_index(value: float) -> str:
    return f"{value:.4f} (indice sans unité, PAS une devise, ne pas convertir ni en $/€ ni en %)"


def get_customer_row(customer_id: str) -> tuple[dict | None, str]:
    row = db.fetch_customer_row(customer_id)
    if row is not None:
        return row, "postgres"
    row = data_store.get_customer_row_csv(customer_id)
    if row is not None:
        return row, "csv"
    return None, "none"


def get_customer_profile(customer_id: str) -> str:
    row, source = get_customer_row(customer_id)
    if row is None:
        return f"Aucun client trouvé avec l'identifiant {customer_id}."

    return (
        f"Profil du client {customer_id} (source : {source}) :\n"
        f"- Segment de valeur (RFM) : {row.get('segment_valeur')}\n"
        f"- Statut club actuel : {row.get('club_member_status')}\n"
        f"- Indice de dépense totale : {spend_index(row.get('total_spend'))}\n"
        f"- Nombre de transactions : {int(row.get('n_transactions', 0))}\n"
        f"- Panier moyen : {spend_index(row.get('avg_basket_value'))}\n"
        f"- Ancienneté (tenure_days) : {int(row.get('tenure_days', 0))} jours\n"
        f"- Récence (jours depuis le dernier achat) : {int(row.get('recency_days', 0))} jours\n"
        f"- Fréquence d'achat mensuelle : {row.get('purchase_frequency_per_month')}\n"
        f"- Catégories distinctes achetées : {int(row.get('n_distinct_categories', 0))}\n"
        f"- Âge : {row.get('age')} ({row.get('age_group')})\n"
        f"- Abonnement newsletter mode : {row.get('fashion_news_frequency')}\n"
    )


def compare_customer_to_segment(customer_id: str) -> str:
    row, source = get_customer_row(customer_id)
    if row is None:
        return f"Aucun client trouvé avec l'identifiant {customer_id}."

    segment = row.get("segment_valeur")
    try:
        seg_row = data_store.get_segment_summary_csv(segment)
    except Exception:
        seg_row = None

    if seg_row is None:
        return (
            f"Client {customer_id} : segment {segment}, indice de dépense "
            f"{spend_index(row.get('total_spend'))} — statistiques du segment "
            "indisponibles pour la comparaison."
        )

    client_spend = row.get("total_spend", 0.0)
    seg_avg = seg_row.get("montant_moyen", 0.0)
    delta_pct = ((client_spend - seg_avg) / seg_avg * 100) if seg_avg else 0.0

    return (
        f"Comparaison du client {customer_id} à son segment ({segment}) :\n"
        f"- Indice de dépense du client : {spend_index(client_spend)}\n"
        f"- Indice de dépense moyen du segment : {spend_index(seg_avg)}\n"
        f"- Écart : {delta_pct:+.1f}% par rapport à la moyenne du segment\n"
        f"- Fréquence d'achat moyenne du client : {row.get('n_transactions')} achats "
        f"vs {seg_row.get('achats_moyen'):.2f} en moyenne dans le segment\n"
        f"- Part du CA total générée par ce segment : {seg_row.get('part_CA_totale_%')}%\n"
    )
