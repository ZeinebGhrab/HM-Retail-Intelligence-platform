# ============================================================
# tools/history.py — get_customer_purchase_history, get_customer_top_categories
#
# Postgres UNIQUEMENT (fact_transaction), sans repli CSV : les fichiers
# exportés par le notebook 04 (products_performance.csv) sont agrégés sur
# tout le catalogue, pas par client — voir db.py et la décision du
# 2026-08-28 (aucun fichier client x article x date n'a été fourni).
# ============================================================
from __future__ import annotations

import db

_UNAVAILABLE = (
    "L'historique d'achat détaillé n'est pas disponible pour le moment "
    "(nécessite la table fact_transaction en base — non connectée dans "
    "cette configuration)."
)


def get_customer_purchase_history(customer_id: str, limit: int = 10) -> str:
    rows = db.fetch_purchase_history(customer_id, limit=limit)
    if rows is None:
        return _UNAVAILABLE
    if not rows:
        return f"Aucune transaction trouvée pour le client {customer_id}."

    lines = [f"Dernières transactions du client {customer_id} :"]
    for r in rows:
        canal = "en ligne" if r["sales_channel_id"] == 2 else "en magasin"
        lines.append(
            f"- {r['date']} : {r['prod_name']} ({r['product_group_name']}) — "
            f"prix (indice) {r['price']:.4f} — achat {canal}"
        )
    return "\n".join(lines)


def get_customer_top_categories(customer_id: str, top_n: int = 5) -> str:
    rows = db.fetch_top_categories(customer_id, top_n=top_n)
    if rows is None:
        return _UNAVAILABLE
    if not rows:
        return f"Aucune catégorie de produit trouvée pour le client {customer_id}."

    lines = [f"Catégories les plus achetées par le client {customer_id} :"]
    for r in rows:
        lines.append(f"- {r['product_group_name']} : {r['n_achats']} achats")
    return "\n".join(lines)
