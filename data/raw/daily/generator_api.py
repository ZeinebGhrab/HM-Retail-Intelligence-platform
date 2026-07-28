"""
Microservice HTTP exposant le générateur de transactions synthétiques,
pensé pour être appelé par n8n juste avant le producer Kafka.

Lancement :
    uvicorn generator_api:app --host 0.0.0.0 --port 8089

Variables d'environnement :
    ARTICLES_CSV   chemin vers articles.csv         (défaut: /data/ref/articles.csv)
    CUSTOMERS_CSV  chemin vers customers.csv        (défaut: /data/ref/customers.csv)
    OUTPUT_DIR     dossier où écrire les CSV du jour (défaut: /data/daily)
                    -> ce dossier doit être le même volume que celui lu par
                       kafka-producer-api, pour que l'étape suivante du
                       workflow n8n puisse le publier sur Kafka.

Endpoint :
    POST /generate?date=2026-07-20&rows=100
    -> { "date": "...", "rows": 5000, "path": "/data/daily/transactions_2026-07-20.csv" }
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
import numpy as np
import pandas as pd

from generate_daily_transactions import (
    generate_daily_transactions,
    load_article_pool,
    load_customer_pool,
)

ARTICLES_CSV = os.environ.get("ARTICLES_CSV", "/data/raw/articles.csv")
CUSTOMERS_CSV = os.environ.get("CUSTOMERS_CSV", "/data/raw/customers.csv")
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/data/raw/daily"))

app = FastAPI(title="HM Daily Transaction Generator")

# Les pools sont chargés une fois au démarrage du service (fichiers de référence
# stables), pas à chaque appel, pour que /generate reste rapide.
_customer_pool = None
_article_pool = None


@app.on_event("startup")
def _load_pools():
    global _customer_pool, _article_pool
    _customer_pool = load_customer_pool(CUSTOMERS_CSV)
    _article_pool = load_article_pool(ARTICLES_CSV)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/generate")
def generate(date: str, rows: int = 5):
    if _customer_pool is None or _article_pool is None:
        raise HTTPException(status_code=503, detail="Pools de référence non chargés")

    df = generate_daily_transactions(date, rows, _customer_pool, _article_pool)
    out_path = OUTPUT_DIR / f"transactions_{date}.csv"
    df.to_csv(out_path, index=False)

    return {"date": date, "rows": len(df), "path": str(out_path)}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "customer_pool_size": None if _customer_pool is None else len(_customer_pool),
        "article_pool_size": None if _article_pool is None else len(_article_pool),
    }
