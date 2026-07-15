"""
API d'inférence exposant les 3 modèles entraînés dans ml/training/ au backend
applicatif (backend/app/).

Stratégie de chargement des modèles (au démarrage de l'API) :
1. MLflow Model Registry (alias "champion", cf. MLFLOW_TRACKING_URI) si disponible.
2. Repli sur les artefacts locaux ml/models/<tache>/*.joblib produits par le
   dernier `python ml/training/train_*.py` exécuté localement.
Cela permet de développer/tester l'API sans dépendre d'un serveur MLflow actif.

Lancement local :
    uvicorn ml.serving.app:app --reload --port 8500

Endpoints :
    GET  /health
    POST /predict/club-status
    POST /predict/spend
    POST /predict/segment
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# Timeout/retries réduits pour ne jamais bloquer l'API si le tracking server
# MLflow configuré (MLFLOW_TRACKING_URI) est injoignable : mieux vaut basculer
# vite sur le repli local que de laisser une requête pendre plusieurs minutes.
os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "3")
os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException

# On ajoute à la fois ml/ (pour "common") et ml/serving/ (pour "schemas") à sys.path,
# car ce module est chargé de deux façons différentes selon le contexte :
# - localement : `uvicorn ml.serving.app:app` depuis la racine du dépôt (uvicorn n'ajoute
#   alors que la racine du dépôt à sys.path, pas ml/serving/) ;
# - en conteneur : `uvicorn serving.app:app` avec WORKDIR=/opt/ml (uvicorn ajoute /opt/ml,
#   pas /opt/ml/serving/).
# Dans les deux cas, un simple "from common import ..." fonctionne (ml/ est bien ajouté),
# mais "from schemas import ..." échoue sans l'ajout explicite de ce second répertoire.
_THIS_DIR = Path(__file__).resolve().parent
_ML_DIR = _THIS_DIR.parent
for _p in (_ML_DIR, _THIS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from common import load_config, models_dir  # noqa: E402
from schemas import (  # noqa: E402
    BehaviorFeatures,
    ClubStatusPrediction,
    HealthResponse,
    SegmentPrediction,
    SpendFeatures,
    SpendPrediction,
)

CONFIG = load_config()
app = FastAPI(
    title="H&M Retail Intelligence — ML Serving API",
    description="API d'inférence pour la segmentation, la classification et la prédiction de dépense clients.",
    version="1.0.0",
)

_REGISTRY: dict[str, Any] = {}


class _Bundle:
    """Regroupe modèle + objets de pré-traitement pour une tâche donnée."""

    def __init__(self, model, scaler=None, extra: dict | None = None, version: str | None = None):
        self.model = model
        self.scaler = scaler
        self.extra = extra or {}
        self.version = version


def _try_load_from_registry(model_name: str) -> _Bundle | None:
    """Tente de charger le modèle "champion" depuis le MLflow Model Registry.

    On utilise l'alias "champion" (mécanisme recommandé depuis MLflow 2.9+, qui
    remplace les anciens "stages") : `mlflow models set-alias hm-... champion 3`
    après une phase de validation manuelle ou automatisée (cf. MLOPS_GUIDE.md).
    """
    try:
        import mlflow

        mlflow.set_tracking_uri(
            __import__("os").environ.get("MLFLOW_TRACKING_URI", CONFIG["mlflow"]["tracking_uri"])
        )
        model_uri = f"models:/{model_name}@champion"
        model = mlflow.pyfunc.load_model(model_uri)
        if model is None or not hasattr(model, "predict"):
            raise RuntimeError("mlflow.pyfunc.load_model a retourné un modèle invalide")
        return _Bundle(model=model, version="registry:champion")
    except Exception as e:  # pragma: no cover - dépend d'un serveur MLflow distant
        print(f"[INFO] Registre MLflow indisponible pour '{model_name}' ({e}). Repli local.")
        return None


def _load_local_bundle(task: str) -> _Bundle | None:
    import joblib

    task_dir = models_dir() / task
    model_path = task_dir / "model.joblib"
    if not model_path.exists():
        return None
    model = joblib.load(model_path)
    scaler_path = task_dir / "scaler.joblib"
    scaler = joblib.load(scaler_path) if scaler_path.exists() else None

    extra = {}
    for extra_name in ("label_encoder", "feature_columns", "selector"):
        p = task_dir / f"{extra_name}.joblib"
        if p.exists():
            extra[extra_name] = joblib.load(p)

    return _Bundle(model=model, scaler=scaler, extra=extra, version="local")


def _get_bundle(task: str, registry_model_name: str) -> _Bundle:
    cache_key = task
    if cache_key in _REGISTRY:
        return _REGISTRY[cache_key]

    bundle = _try_load_from_registry(registry_model_name) or _load_local_bundle(task)
    if bundle is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Aucun modèle disponible pour '{task}'. Entraîner d'abord le modèle : "
                f"python ml/training/train_{task}.py"
            ),
        )
    _REGISTRY[cache_key] = bundle
    return bundle


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    statuses = {}
    for task in ("classification", "regression", "clustering"):
        statuses[task] = (models_dir() / task / "model.joblib").exists() or task in _REGISTRY
    return HealthResponse(status="ok", models_loaded=statuses)


@app.post("/predict/club-status", response_model=ClubStatusPrediction)
def predict_club_status(features: BehaviorFeatures) -> ClubStatusPrediction:
    bundle = _get_bundle("classification", CONFIG["classification"]["model_name"])
    cols = CONFIG["behavior_features"]
    X = pd.DataFrame([features.model_dump()])[cols]

    if bundle.version == "local":
        X_scaled = bundle.scaler.transform(X)
        pred = bundle.model.predict(X_scaled)
        le = bundle.extra.get("label_encoder")
        label = le.inverse_transform(pred)[0] if le else str(pred[0])
        if hasattr(bundle.model, "predict_proba"):
            proba = bundle.model.predict_proba(X_scaled)[0]
            classes = le.classes_ if le else [str(c) for c in bundle.model.classes_]
            probabilities = {str(c): float(p) for c, p in zip(classes, proba)}
        else:
            probabilities = {label: 1.0}
    else:
        pred = bundle.model.predict(X)
        label = str(pred[0]) if not hasattr(pred, "iloc") else str(pred.iloc[0])
        probabilities = {label: 1.0}

    return ClubStatusPrediction(club_member_status=label, probabilities=probabilities, model_version=bundle.version)


@app.post("/predict/segment", response_model=SegmentPrediction)
def predict_segment(features: BehaviorFeatures) -> SegmentPrediction:
    bundle = _get_bundle("clustering", CONFIG["clustering"]["model_name"])
    cols = CONFIG["behavior_features"]
    X = pd.DataFrame([features.model_dump()])[cols]

    if bundle.version == "local":
        X_scaled = bundle.scaler.transform(X)
        cluster = int(bundle.model.predict(X_scaled)[0])
    else:
        cluster = int(np.asarray(bundle.model.predict(X))[0])

    return SegmentPrediction(cluster=cluster, model_version=bundle.version)


@app.post("/predict/spend", response_model=SpendPrediction)
def predict_spend(features: SpendFeatures) -> SpendPrediction:
    bundle = _get_bundle("regression", CONFIG["regression"]["model_name"])
    reg_cfg = CONFIG["regression"]
    raw = features.model_dump()

    num = {k: raw[k] for k in reg_cfg["numeric_features"]}
    cat = {k: str(raw[k]) for k in reg_cfg["categorical_features"]}
    X_num = pd.DataFrame([num])
    X_cat = pd.get_dummies(pd.DataFrame([cat]), drop_first=True)

    if bundle.version == "local":
        feature_columns = bundle.extra.get("feature_columns", list(X_num.columns) + list(X_cat.columns))
        X_full = pd.concat([X_num, X_cat], axis=1).reindex(columns=feature_columns, fill_value=0)
        X_scaled = bundle.scaler.transform(X_full)
        selector = bundle.extra.get("selector")
        X_selected = selector.transform(X_scaled) if selector is not None else X_scaled
        pred_log = bundle.model.predict(X_selected)[0]
    else:
        X_full = pd.concat([X_num, X_cat], axis=1)
        pred_log = float(np.asarray(bundle.model.predict(X_full))[0])

    predicted = float(np.expm1(pred_log)) if reg_cfg["log_target"] else float(pred_log)
    return SpendPrediction(predicted_total_spend=round(predicted, 2), model_version=bundle.version)