"""
Utilitaires partagés par ml/training/, ml/serving/ et ml/monitoring/.

Centralise :
- le chargement de la config (ml/config.yaml)
- la configuration du tracking MLflow (URI, expérience)
- la connexion PostgreSQL et le chargement de la table de features clients
  `customers_features_train` (produite par spark/jobs/pipeline_hm.py), avec
  repli synthétique pratique pour les tests/CI/démo quand PostgreSQL n'est
  pas accessible (pas encore lancé, pipeline pas encore exécuté, etc.)
"""
from __future__ import annotations

import os

# Timeout/retries HTTP MLflow réduits par défaut : sans cela, une URI MLflow injoignable
# (ex. MLFLOW_TRACKING_URI absente, ou serveur pas démarré) fait attendre le client MLflow
# plusieurs minutes (120s de timeout x 7 tentatives par défaut) avant d'échouer, ce qui bloque
# `configure_mlflow()` bien avant que son repli automatique (voir plus bas) ne puisse agir.
# `setdefault` : ne prime jamais sur une valeur explicitement définie par la personne.
os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "5")
os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ML_DIR = Path(__file__).resolve().parent


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Charge ml/config.yaml (chemin surchargeable pour les tests)."""
    cfg_path = Path(path) if path else ML_DIR / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_mlflow_tracking_uri(config: dict[str, Any]) -> str:
    """La variable d'env MLFLOW_TRACKING_URI (définie dans .env) prime sur le config.yaml.

    Utilise `or` plutôt que `os.environ.get(clé, défaut)` : dans GitHub Actions, un secret non
    configuré (ex. MLFLOW_TRACKING_URI absent des secrets du repo) résout `${{ secrets.X }}` en
    chaîne VIDE, mais la variable d'environnement reste tout de même définie (juste vide) — donc
    `os.environ.get("MLFLOW_TRACKING_URI", défaut)` renverrait cette chaîne vide au lieu du défaut,
    et MLflow interpréterait une URI vide comme un stockage fichier local ("./mlruns"), désormais
    bloqué ("filesystem tracking backend ... in maintenance mode"). `or` ignore aussi bien
    l'absence que la chaîne vide.
    """
    return os.environ.get("MLFLOW_TRACKING_URI") or config["mlflow"]["tracking_uri"]


def configure_mlflow(config: dict[str, Any]):
    """Configure mlflow (tracking URI + expérience) et retourne le module prêt à l'emploi.

    Ne fait jamais planter l'entraînement : si l'URI configurée (secret manquant, serveur MLflow
    non démarré, backend fichier obsolète...) est injoignable ou invalide, bascule automatiquement
    sur un tracking local SQLite (`ml/mlflow_fallback.db`) avec un WARNING explicite, plutôt que de
    lever une exception qui interromprait tout le script avant même l'entraînement du modèle.
    """
    import mlflow

    uri = get_mlflow_tracking_uri(config)
    mlflow.set_tracking_uri(uri)
    try:
        mlflow.set_experiment(config["mlflow"]["experiment_name"])
    except Exception as e:
        fallback_uri = f"sqlite:///{ML_DIR / 'mlflow_fallback.db'}"
        print(
            f"[WARN] Tracking MLflow '{uri}' injoignable ou incompatible ({e}). "
            f"Repli sur un tracking local : {fallback_uri} "
            "(les runs ne seront visibles que sur cette machine)."
        )
        mlflow.set_tracking_uri(fallback_uri)
        mlflow.set_experiment(config["mlflow"]["experiment_name"])
    return mlflow


def get_postgres_engine(config: dict[str, Any]):
    """
    Construit un engine SQLAlchemy vers PostgreSQL à partir des variables d'env
    définies dans .env (POSTGRES_PORT/DB/USER/PASSWORD, communes à tous les
    services du docker-compose) + POSTGRES_HOST, propre à ml/ :
    - "postgres" (nom du service Docker) depuis un conteneur du réseau
      shop_data_net (ex. le service ml-serving ajouté au docker-compose) ;
    - "localhost" par défaut, pour un poste de dev exécutant les scripts hors
      Docker (le port PostgreSQL est publié sur l'hôte par docker-compose.yml).
    """
    from sqlalchemy import create_engine

    pg_cfg = config["postgres"]
    host = os.environ.get("POSTGRES_HOST", pg_cfg["host_default"])
    port = os.environ.get(pg_cfg["port_env"], "5432")
    db = os.environ.get(pg_cfg["db_env"])
    user = os.environ.get(pg_cfg["user_env"])
    password = os.environ.get(pg_cfg["password_env"])

    if not db or not user:
        raise RuntimeError(
            "Variables PostgreSQL manquantes (POSTGRES_DB/POSTGRES_USER) — "
            "copier .env.example en .env et renseigner de vraies valeurs."
        )

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


def load_customer_features(config: dict[str, Any], path: str | Path | None = None) -> pd.DataFrame:
    """
    Charge la table `customers_features_train` depuis PostgreSQL (sortie de
    spark/jobs/pipeline_hm.py, voir spark/README.md).

    Si PostgreSQL est inaccessible (pas démarré, pipeline pas encore exécuté,
    table vide, poste de dev sans Docker) ou si le paramètre `path` pointe vers
    un CSV existant (repli explicite, ex. export manuel), un jeu de données
    synthétique de même schéma est généré à la place. Un WARNING est émis pour
    ne jamais confondre ce mode avec un entraînement sur données réelles.
    """
    if path is not None and Path(path).exists():
        return pd.read_csv(path)

    table = config["postgres"]["features_table"]
    try:
        engine = get_postgres_engine(config)
        df = pd.read_sql(f"SELECT * FROM {table}", engine)
        if df.empty:
            raise ValueError(f"la table '{table}' est vide (pipeline Spark pas encore exécuté ?)")
        return df
    except Exception as e:
        print(
            f"[WARN] Lecture de la table PostgreSQL '{table}' impossible ({e}). "
            "Génération d'un jeu de données synthétique (mode démo/CI). "
            "Démarrer PostgreSQL (`./run.sh infra`) et exécuter le pipeline Spark "
            "(voir spark/README.md §9) pour entraîner sur les vraies données."
        )
        return _generate_synthetic_customer_features(config)


def _generate_synthetic_customer_features(config: dict[str, Any], n: int = 2000, seed: int = 42) -> pd.DataFrame:
    """Génère une table synthétique avec le même schéma que `customers_features_train`
    (colonnes de spark/utils/features.py -> compute_customer_features)."""
    rng = np.random.RandomState(seed)
    club_status = rng.choice(
        ["ACTIVE", "PRE-CREATE", "LEFT CLUB"], size=n, p=[0.7, 0.2, 0.1]
    )
    fashion_news = rng.choice(["NONE", "Regularly", "Monthly"], size=n, p=[0.5, 0.3, 0.2])
    age = rng.randint(18, 80, size=n)
    # Bins exacts de spark/utils/cleaning.py::clean_customers (identiques au notebook 01),
    # cf. config.yaml -> age_group_bins/age_group_labels.
    age_group = pd.cut(
        age, bins=config["age_group_bins"], labels=config["age_group_labels"], right=False,
    ).astype(str)
    n_transactions = rng.poisson(15, size=n) + 1
    tenure_days = rng.randint(30, 2000, size=n)
    n_distinct_categories = rng.randint(1, 15, size=n)
    avg_basket_value = np.round(rng.gamma(2.0, 15.0, size=n), 2)
    purchase_frequency_per_month = np.round(n_transactions / (tenure_days / 30 + 1), 3)
    recency_days = rng.randint(0, 365, size=n)
    total_spend = np.round(n_transactions * avg_basket_value * rng.uniform(0.8, 1.2, size=n), 2)
    q1, q2, q3 = np.quantile(total_spend, [0.25, 0.5, 0.75])
    segment_valeur = np.select(
        [total_spend <= q1, total_spend <= q2, total_spend <= q3],
        ["Bas (Q1)", "Moyen-bas (Q2)", "Moyen-haut (Q3)"],
        default="Haut (Q4 - VIP)",
    )

    return pd.DataFrame({
        "customer_key": np.arange(n),
        "age": age,
        "age_group": age_group,
        "club_member_status": club_status,
        "fashion_news_frequency": fashion_news,
        "n_transactions": n_transactions,
        "tenure_days": tenure_days,
        "n_distinct_categories": n_distinct_categories,
        "avg_basket_value": avg_basket_value,
        "purchase_frequency_per_month": purchase_frequency_per_month,
        "recency_days": recency_days,
        "total_spend": total_spend,
        "segment_valeur": segment_valeur,
        "postal_code": ["synthetic"] * n,
    })


def models_dir() -> Path:
    """Répertoire de repli local pour les modèles quand le registre MLflow est indisponible."""
    d = ML_DIR / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d