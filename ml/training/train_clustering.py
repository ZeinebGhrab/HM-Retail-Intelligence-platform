"""
Entraînement du modèle de segmentation client (clustering).

Reprend la logique validée dans notebooks/07_ML_Clustering_Approfondi_Synthese.ipynb :
K-Means sur les features comportementales standardisées, avec k=6 (validé par
BIC/AIC dans le notebook). Log du score de silhouette pour suivre la qualité
du clustering au fil des ré-entraînements.

Usage :
    python ml/training/train_clustering.py [--config ml/config.yaml] [--register]
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import configure_mlflow, load_config, load_customer_features, models_dir  # noqa: E402


def train(config_path: str | None = None, register: bool = False) -> dict:
    config = load_config(config_path)
    clu_cfg = config["clustering"]
    df = load_customer_features(config)

    features = config["behavior_features"]
    X = df[features].fillna(0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    k = clu_cfg["k"]
    model = KMeans(n_clusters=k, n_init=clu_cfg["n_init"], random_state=42)
    labels = model.fit_predict(X_scaled)

    # Le silhouette score est coûteux en O(n²) : on le calcule sur un échantillon borné.
    sample_n = min(5000, len(X_scaled))
    metrics = {
        "silhouette_score": float(silhouette_score(X_scaled, labels, sample_size=sample_n, random_state=42)),
        "inertia": float(model.inertia_),
        "k": k,
        "n_samples": int(len(X_scaled)),
    }
    print(f"k={k} | silhouette={metrics['silhouette_score']:.4f} | inertia={metrics['inertia']:.1f}")

    mlflow = configure_mlflow(config)
    with mlflow.start_run(run_name="train_clustering") as run:
        mlflow.log_params({"algorithm": "kmeans", "k": k, "features": features})
        mlflow.log_metrics(metrics)

        import joblib

        model_name = clu_cfg["model_name"]
        mlflow.sklearn.log_model(
            model, name="model",
            registered_model_name=model_name if register else None,
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            joblib.dump(scaler, tmp_path / "scaler.joblib")
            mlflow.log_artifacts(str(tmp_path), artifact_path="preprocessing")

            local_dir = models_dir() / "clustering"
            local_dir.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, local_dir / "model.joblib")
            joblib.dump(scaler, local_dir / "scaler.joblib")

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