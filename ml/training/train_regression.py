"""
Entraînement du modèle de régression `total_spend`.

Reproduit le modèle **effectivement retenu** dans notebooks/06_ML_Classification_Regression.ipynb
(section 17.6.4, confirmé par la synthèse §17.8) :
1. Construction des features candidates (numériques + catégorielles one-hot), standardisées.
2. Sélection des 12 meilleures features par `SelectKBest(f_regression, k=12)` (section 17.6.2) —
   retenue plutôt que la Backward Elimination (section 17.6.3), qui sert de validation croisée
   complémentaire mais n'alimente pas le modèle final (voir l'interprétation du notebook).
3. `XGBRegressor` à hyperparamètres **par défaut** (`xgb.XGBRegressor(random_state=42)`, sans
   réglage additionnel) sur la cible `log1p(total_spend)` — R²(test, log)=0.943 dans le notebook,
   loin devant Lasso/Ridge/ElasticNet/régression linéaire (R²≈0.89).

Différence assumée avec le notebook : `SelectKBest` y est ajusté sur l'intégralité de l'échantillon
avant le split train/test (fuite d'information mineure sur le choix des colonnes, pas sur
l'entraînement du modèle lui-même). Ce script l'ajuste uniquement sur le jeu d'entraînement, par
bonne pratique — les colonnes sélectionnées peuvent donc différer légèrement de celles listées
dans le notebook selon le jeu de données utilisé.

Usage :
    python ml/training/train_regression.py [--config ml/config.yaml] [--register]
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import configure_mlflow, load_config, load_customer_features, models_dir  # noqa: E402


def _build_model():
    """XGBoost Regressor à hyperparamètres par défaut — modèle retenu dans le notebook.
    Repli sur ElasticNet si xgboost n'est pas installé (ex. environnement CI minimal)."""
    try:
        import xgboost as xgb
        return xgb.XGBRegressor(random_state=42), "xgboost"
    except ImportError:
        print("[WARN] xgboost indisponible, repli sur ElasticNet(alpha=0.01, l1_ratio=0.5).")
        from sklearn.linear_model import ElasticNet
        return ElasticNet(alpha=0.01, l1_ratio=0.5, random_state=42), "elasticnet"


def train(config_path: str | None = None, register: bool = False) -> dict:
    config = load_config(config_path)
    reg_cfg = config["regression"]
    df = load_customer_features(config)

    target = reg_cfg["target"]
    df = df.dropna(subset=[target]).copy()

    num_features = reg_cfg["numeric_features"]
    cat_features = reg_cfg["categorical_features"]

    X_num = df[num_features].fillna(0).reset_index(drop=True)
    X_cat = pd.get_dummies(df[cat_features].astype(str), drop_first=True).reset_index(drop=True)
    X_full = pd.concat([X_num, X_cat], axis=1)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_full)

    y_raw = df[target].reset_index(drop=True)
    y = np.log1p(y_raw) if reg_cfg["log_target"] else y_raw

    Xtr_full, Xte_full, ytr, yte = train_test_split(
        X_scaled, y, test_size=config["data"]["test_size"], random_state=config["data"]["random_state"],
    )

    # Sélection des k meilleures features (notebook §17.6.2), ajustée sur le train uniquement.
    k = min(reg_cfg["select_k_best"], Xtr_full.shape[1])
    selector = SelectKBest(score_func=f_regression, k=k)
    Xtr = selector.fit_transform(Xtr_full, ytr)
    Xte = selector.transform(Xte_full)
    selected_columns = [c for c, keep in zip(X_full.columns, selector.get_support()) if keep]
    print(f"Features sélectionnées (SelectKBest, k={k}) : {selected_columns}")

    model, algorithm_used = _build_model()
    model.fit(Xtr, ytr)

    pred_log = model.predict(Xte)
    if reg_cfg["log_target"]:
        pred = np.expm1(pred_log)
        true = np.expm1(yte)
    else:
        pred, true = pred_log, yte

    metrics = {
        "rmse": float(mean_squared_error(true, pred) ** 0.5),
        "mae": float(mean_absolute_error(true, pred)),
        "r2_log_target": float(r2_score(yte, pred_log)),
        "n_train": int(len(Xtr)),
        "n_test": int(len(Xte)),
    }
    print(f"Algorithme utilisé : {algorithm_used}")
    print(f"RMSE (test) : {metrics['rmse']:.2f} | MAE : {metrics['mae']:.2f} | R² (log) : {metrics['r2_log_target']:.4f}")

    mlflow = configure_mlflow(config)
    with mlflow.start_run(run_name="train_regression") as run:
        mlflow.log_params({
            "algorithm": algorithm_used,
            "numeric_features": num_features,
            "categorical_features": cat_features,
            "select_k_best": k,
            "selected_columns": selected_columns,
            "log_target": reg_cfg["log_target"],
        })
        mlflow.log_metrics(metrics)

        model_name = reg_cfg["model_name"]
        log_model_fn = mlflow.xgboost.log_model if algorithm_used == "xgboost" else mlflow.sklearn.log_model
        log_model_fn(
            model, name="model",
            registered_model_name=model_name if register else None,
        )

        import joblib
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            joblib.dump(scaler, tmp_path / "scaler.joblib")
            joblib.dump(selector, tmp_path / "selector.joblib")
            joblib.dump(list(X_full.columns), tmp_path / "feature_columns.joblib")
            mlflow.log_artifacts(str(tmp_path), artifact_path="preprocessing")

            local_dir = models_dir() / "regression"
            local_dir.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, local_dir / "model.joblib")
            joblib.dump(scaler, local_dir / "scaler.joblib")
            joblib.dump(selector, local_dir / "selector.joblib")
            joblib.dump(list(X_full.columns), local_dir / "feature_columns.joblib")

        if register:
            print(f"Modèle enregistré dans le Model Registry sous '{model_name}'.")
        print(f"Run MLflow : {run.info.run_id}")

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None, help="Chemin vers ml/config.yaml")
    parser.add_argument("--register", action="store_true", help="Enregistrer dans le Model Registry MLflow")
    args = parser.parse_args()
    train(args.config, args.register)