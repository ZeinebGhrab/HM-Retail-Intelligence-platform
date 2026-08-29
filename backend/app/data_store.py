# ============================================================
# data_store.py — Repli CSV (notebooks/04, section 15) chargé une seule fois
# en mémoire au démarrage. Utilisé uniquement quand Postgres est
# indisponible ou que customers_features_train est vide — voir db.py et
# tools/profile.py pour l'ordre de priorité (Postgres d'abord).
# ============================================================
from __future__ import annotations

import pandas as pd

from config import DATA_DIR

_customers: pd.DataFrame | None = None
_segments: pd.DataFrame | None = None
_insights_md: str | None = None


def _load_customers() -> pd.DataFrame:
    global _customers
    if _customers is None:
        df = pd.read_csv(DATA_DIR / "customers_features.csv", dtype={"customer_id": str})
        _customers = df.set_index("customer_id", drop=False)
    return _customers


def _load_segments() -> pd.DataFrame:
    global _segments
    if _segments is None:
        df = pd.read_csv(DATA_DIR / "customer_segments_summary.csv")
        _segments = df.set_index("segment_valeur", drop=False)
    return _segments


def get_customer_row_csv(customer_id: str) -> dict | None:
    df = _load_customers()
    if customer_id not in df.index:
        return None
    row = df.loc[customer_id]
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]
    return row.to_dict()


def get_segment_summary_csv(segment_valeur: str) -> dict | None:
    df = _load_segments()
    if segment_valeur not in df.index:
        return None
    return df.loc[segment_valeur].to_dict()


def get_insights_markdown() -> str:
    global _insights_md
    if _insights_md is None:
        _insights_md = (DATA_DIR / "insights_summary.md").read_text(encoding="utf-8")
    return _insights_md


def _chunk_markdown(md: str, default_title: str) -> list[dict[str, str]]:
    """Découpe un markdown par section '##', comme suggéré par le notebook 04
    (§15.1, 'Utilisation suggérée dans un pipeline RAG')."""
    chunks: list[dict[str, str]] = []
    current_title = default_title
    current_body: list[str] = []

    for line in md.splitlines():
        if line.startswith("## "):
            if current_body:
                chunks.append({"title": current_title, "content": "\n".join(current_body).strip()})
            current_title = line[3:].strip()
            current_body = []
        elif not line.startswith("# "):
            current_body.append(line)

    if current_body:
        chunks.append({"title": current_title, "content": "\n".join(current_body).strip()})

    return [c for c in chunks if c["content"]]


# Fichiers markdown indexés pour semantic_search — insights_summary.md
# (export notebook 04, données chiffrées) et company_info.md (rédigé
# manuellement, informations générales sur l'entreprise — voir décision du
# 2026-08-29 : contenu volontairement factuel/prudent, jamais mélangé avec
# les données chiffrées du dataset dans la même affirmation).
_KB_FILES = [
    ("insights_summary.md", "Vue d'ensemble"),
    ("company_info.md", "Informations générales"),
]


def get_insights_chunks() -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for filename, default_title in _KB_FILES:
        path = DATA_DIR / filename
        if path.exists():
            chunks.extend(_chunk_markdown(path.read_text(encoding="utf-8"), default_title))
    return chunks
