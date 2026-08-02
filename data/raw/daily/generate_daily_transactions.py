"""
Générateur de transactions H&M synthétiques.

Simule l'arrivée quotidienne de transactions (même structure et mêmes
distributions statistiques que transactions_train.csv), à utiliser pour tester
le pipeline Kafka -> PySpark -> feature store.
les pools de customer_id / article_id ne sont plus
générés artificiellement (hash / entier aléatoire), ils sont échantillonnés
dans les vrais fichiers de référence articles.csv et customers.csv fournis par H&M.
Seules la popularité (loi de Zipf), le prix et le canal restent simulés,
puisqu'ils ne sont pas connus à l'avance pour un jour futur.

Usage:
    python generate_daily_transactions.py --date 2026-07-20 --rows 5000 \
        --articles articles.csv --customers customers.csv --out transactions_2026-07-20.csv
"""

import argparse
from datetime import datetime

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)

# Si le pool réel dépasse ces tailles, on sous-échantillonne pour garder
# des poids Zipf lisibles (sinon la longue traîne devient trop plate).
MAX_CUSTOMERS_POOL = 20000
MAX_ARTICLES_POOL = 20000


def load_customer_pool(customers_csv: str) -> np.ndarray:
    df = pd.read_csv(customers_csv, dtype=str, usecols=["customer_id"])
    ids = df["customer_id"].dropna().unique()
    if len(ids) > MAX_CUSTOMERS_POOL:
        ids = rng.choice(ids, size=MAX_CUSTOMERS_POOL, replace=False)
    return ids


def load_article_pool(articles_csv: str) -> np.ndarray:
    df = pd.read_csv(articles_csv, dtype=str, usecols=["article_id"])
    ids = df["article_id"].dropna().unique()
    if len(ids) > MAX_ARTICLES_POOL:
        ids = rng.choice(ids, size=MAX_ARTICLES_POOL, replace=False)
    return ids


def zipf_weights(n: int) -> np.ndarray:
    # quelques clients/articles très actifs, une longue traîne, comme dans l'EDA
    w = 1 / np.arange(1, n + 1)
    return w / w.sum()


def generate_daily_transactions(
    date_str: str,
    n_rows: int,
    customers: np.ndarray,
    articles: np.ndarray,
) -> pd.DataFrame:
    # on mélange les pools une fois pour ne pas corréler le rang Zipf avec
    # l'ordre d'apparition dans les fichiers sources (souvent trié par code produit)
    customers = rng.permutation(customers)
    articles = rng.permutation(articles)

    customer_weights = zipf_weights(len(customers))
    article_weights = zipf_weights(len(articles))

    customer_ids = rng.choice(customers, size=n_rows, p=customer_weights)
    article_ids = rng.choice(articles, size=n_rows, p=article_weights)

    # distribution du prix calquée sur l'EDA : concentrée entre 0 et 0.1, quelques
    # valeurs plus hautes jusqu'à ~0.6
    prices = np.clip(rng.gamma(shape=1.5, scale=0.015, size=n_rows), 0.005, 0.6)
    # ratio observé dans l'EDA : ~30% canal 1 (magasin), ~70% canal 2 (en ligne)
    channels = rng.choice([1, 2], size=n_rows, p=[0.3, 0.7])

    df = pd.DataFrame({
        "t_dat": date_str,
        "customer_id": customer_ids,
        "article_id": article_ids,
        "price": np.round(prices, 6),
        "sales_channel_id": channels,
    })
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.today().strftime("%Y-%m-%d"),
                         help="Date du lot (format YYYY-MM-DD)")
    parser.add_argument("--rows", type=int, default=5000,
                         help="Nombre de transactions à générer pour ce jour")
    parser.add_argument("--articles", default="articles.csv",
                         help="Chemin vers le fichier articles.csv H&M")
    parser.add_argument("--customers", default="customers.csv",
                         help="Chemin vers le fichier customers.csv H&M")
    parser.add_argument("--out", default=None, help="Chemin du fichier de sortie")
    args = parser.parse_args()

    customer_pool = load_customer_pool(args.customers)
    article_pool = load_article_pool(args.articles)

    df = generate_daily_transactions(args.date, args.rows, customer_pool, article_pool)
    out_path = args.out or f"transactions_{args.date}.csv"
    df.to_csv(out_path, index=False)
    print(f"{len(df)} lignes générées -> {out_path} "
          f"(pool clients={len(customer_pool)}, pool articles={len(article_pool)})")
