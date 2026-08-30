# ============================================================
# db.py — Connexion PostgreSQL (customers_features_train, fact_transaction)
#
# Client léger et autonome (pas de dépendance vers ml/common.py) : ce service
# est construit dans son propre conteneur Docker (context: ./backend/app),
# qui n'embarque pas le dossier ml/ — voir Dockerfile.
#
# Schéma réel (vérifié en base le 2026-08-31, différent de ce qui avait été
# supposé initialement) : fact_transaction et customers_features_train
# n'ont PAS de colonne customer_id — seulement customer_key (clé de
# substitution bigint). Le customer_id (hex 64 caractères) vit uniquement
# dans dim_customer, avec customer_key comme clé de jointure. Idem
# fact_transaction.article_key -> dim_article.article_key (article_id est
# la clé "métier", pas la clé de jointure). dim_date fait le pont
# date_key (int) -> date (date réelle).
# ============================================================
from __future__ import annotations

import sys

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from config import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = (
            f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
            f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        )
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def _log_failure(context: str, e: Exception) -> None:
    # Sur stderr (capté par `docker logs`) plutôt qu'avalé silencieusement :
    # un vrai bug SQL (mauvaise colonne, jointure cassée...) doit être
    # visible, pas se confondre avec "Postgres indisponible" — c'est
    # exactement ce qui a caché le bug de schéma découvert le 2026-08-31.
    print(f"[db] {context} a échoué : {e}", file=sys.stderr)


def fetch_customer_row(customer_id: str) -> dict | None:
    """Repli CSV côté appelant (voir data_store.py) si None est retourné —
    que ce soit parce que Postgres est injoignable ou que le client n'existe
    pas."""
    try:
        engine = get_engine()
        df = pd.read_sql(
            """
            SELECT f.*, c.customer_id
            FROM customers_features_train f
            JOIN dim_customer c ON c.customer_key = f.customer_key
            WHERE c.customer_id = %(cid)s
            """,
            engine,
            params={"cid": customer_id},
        )
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    except Exception as e:
        _log_failure("fetch_customer_row", e)
        return None


def fetch_purchase_history(customer_id: str, limit: int = 10) -> list[dict] | None:
    """Historique détaillé des transactions d'un client.

    Contrairement à fetch_customer_row, aucun repli CSV n'existe pour cette
    fonction : les fichiers exportés par le notebook 04 sont des agrégats
    catalogue-entier (products_performance.csv), pas des lignes
    client x article x date. Sans fact_transaction en base, cette
    information n'est simplement pas disponible — voir tools/history.py."""
    try:
        engine = get_engine()
        df = pd.read_sql(
            """
            SELECT a.article_id, a.prod_name, a.product_group_name,
                   t.price, t.sales_channel_id, d.date
            FROM fact_transaction t
            JOIN dim_customer c ON c.customer_key = t.customer_key
            JOIN dim_article a ON a.article_key = t.article_key
            JOIN dim_date d ON d.date_key = t.date_key
            WHERE c.customer_id = %(cid)s
            ORDER BY d.date DESC
            LIMIT %(limit)s
            """,
            engine,
            params={"cid": customer_id, "limit": limit},
        )
        if df.empty:
            return None
        df["date"] = df["date"].astype(str)
        return df.to_dict(orient="records")
    except Exception as e:
        _log_failure("fetch_purchase_history", e)
        return None


def fetch_top_categories(customer_id: str, top_n: int = 5) -> list[dict] | None:
    try:
        engine = get_engine()
        df = pd.read_sql(
            """
            SELECT a.product_group_name, COUNT(*) AS n_achats
            FROM fact_transaction t
            JOIN dim_customer c ON c.customer_key = t.customer_key
            JOIN dim_article a ON a.article_key = t.article_key
            WHERE c.customer_id = %(cid)s
            GROUP BY a.product_group_name
            ORDER BY n_achats DESC
            LIMIT %(top_n)s
            """,
            engine,
            params={"cid": customer_id, "top_n": top_n},
        )
        if df.empty:
            return None
        return df.to_dict(orient="records")
    except Exception as e:
        _log_failure("fetch_top_categories", e)
        return None
