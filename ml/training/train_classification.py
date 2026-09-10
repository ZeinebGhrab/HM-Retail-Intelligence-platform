"""
Entraînement du modèle de classification `club_member_status`.

Reproduit le modèle **effectivement retenu** dans notebooks/06_ML_Classification_Regression.ipynb
(section 17.5.1, confirmé par la synthèse §17.8) : un `RandomForestClassifier` avec
`class_weight="balanced"`, dont les hyperparamètres (`n_estimators=200`, `max_depth=20`,
`min_samples_leaf=5`) sont le résultat exact d'un `GridSearchCV` (cellule 25 du notebook,
`best_params_`).

Ce modèle bat, sur le jeu de test du notebook, tous les modèles de boosting testés avec
SMOTE/rééquilibrage (section 17.5.2) — y compris le meilleur d'entre eux, CatBoost+SMOTE
(F1-macro=0.3652 contre 0.3889 pour ce Random Forest). **Le modèle final ne comporte donc pas
de SMOTE** : c'est un choix du notebook, pas un oubli de ce script.

Usage :
    python ml/training/train_classification.py [--config ml/config.yaml] [--register]
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import (  # noqa: E402
    configure_mlflow,
    load_config,
    load_customer_features,
    models_dir,
)


def train(config_path: str | None = None, register: bool = False) -> dict:
    config = load_config(config_path)
    clf_cfg = config["classification"]
    df = load_customer_features(config)

    features = config["behavior_features"]
    target = clf_cfg["target"]
    df = df.dropna(subset=[target]).copy()

    X = df[features].fillna(0)
    y = df[target].astype(str)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    Xtr, Xte, ytr, yte = train_test_split(
        X_scaled, y, test_size=config["data"]["test_size"],
        stratify=y, random_state=config["data"]["random_state"],
    )

    le = LabelEncoder()
    ytr_enc = le.fit_transform(ytr)
    yte_enc = le.transform(yte)

    hp = clf_cfg["hyperparameters"]
    model = RandomForestClassifier(
        n_estimators=hp["n_estimators"],
        max_depth=hp["max_depth"],
        min_samples_leaf=hp["min_samples_leaf"],
        class_weight=hp["class_weight"],
        random_state=42,
        n_jobs=-1,
    )
    model.fit(Xtr, ytr_enc)

    pred = model.predict(Xte)
    metrics = {
        "f1_macro": float(f1_score(yte_enc, pred, average="macro")),
        "accuracy": float(accuracy_score(yte_enc, pred)),
        "n_train": int(len(Xtr)),
        "n_test": int(len(Xte)),
    }
    report = classification_report(yte_enc, pred, target_names=le.classes_, zero_division=0)
    print("Algorithme : RandomForestClassifier (optimisé GridSearchCV, notebook 06 §17.5.1)")
    print(f"F1-macro (test) : {metrics['f1_macro']:.4f} | Accuracy : {metrics['accuracy']:.4f}")
    print(report)

    mlflow = configure_mlflow(config)
    with mlflow.start_run(run_name="train_classification") as run:
        mlflow.log_params({
            "algorithm": "random_forest",
            "features": features,
            "n_estimators": hp["n_estimators"],
            "max_depth": hp["max_depth"],
            "min_samples_leaf": hp["min_samples_leaf"],
            "class_weight": hp["class_weight"],
            "test_size": config["data"]["test_size"],
        })
        mlflow.log_metrics(metrics)
        mlflow.log_text(report, "classification_report.txt")

        model_name = clf_cfg["model_name"]
        mlflow.sklearn.log_model(
            model, name="model",
            registered_model_name=model_name if register else None,
        )

        import joblib
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            joblib.dump(scaler, tmp_path / "scaler.joblib")
            joblib.dump(le, tmp_path / "label_encoder.joblib")
            mlflow.log_artifacts(str(tmp_path), artifact_path="preprocessing")

            # Repli local (toujours utile pour ml/serving/ hors MLflow Model Registry)
            local_dir = models_dir() / "classification"
            local_dir.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, local_dir / "model.joblib")
            joblib.dump(scaler, local_dir / "scaler.joblib")
            joblib.dump(le, local_dir / "label_encoder.joblib")

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