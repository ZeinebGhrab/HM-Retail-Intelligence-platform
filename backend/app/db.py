# ============================================================
# db.py — Connexion PostgreSQL (customers_features_train, fact_transaction)
#
# Client léger et autonome (pas de dépendance vers ml/common.py) : ce service
# est construit dans son propre conteneur Docker (context: ./backend/app),
# qui n'embarque pas le dossier ml/ — voir Dockerfile.
# ============================================================
from __future__ import annotations

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


def fetch_customer_row(customer_id: str) -> dict | None:
    """SELECT * FROM customers_features_train WHERE customer_id = ...

    Retourne None si la table est inaccessible, vide, ou si le client n'y
    figure pas — jamais d'exception : c'est le signal pour que l'appelant
    bascule sur le repli CSV (voir data_store.py)."""
    try:
        engine = get_engine()
        df = pd.read_sql(
            "SELECT * FROM customers_features_train WHERE customer_id = %(cid)s",
            engine,
            params={"cid": customer_id},
        )
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    except Exception:
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
            SELECT article_id, price, sales_channel_id, date_key
            FROM fact_transaction
            WHERE customer_id = %(cid)s
            ORDER BY date_key DESC
            LIMIT %(limit)s
            """,
            engine,
            params={"cid": customer_id, "limit": limit},
        )
        if df.empty:
            return None
        return df.to_dict(orient="records")
    except Exception:
        return None


def fetch_top_categories(customer_id: str, top_n: int = 5) -> list[dict] | None:
    try:
        engine = get_engine()
        df = pd.read_sql(
            """
            SELECT a.product_group_name, COUNT(*) AS n_achats
            FROM fact_transaction t
            JOIN dim_article a ON a.article_id = t.article_id
            WHERE t.customer_id = %(cid)s
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
    except Exception:
        return None
