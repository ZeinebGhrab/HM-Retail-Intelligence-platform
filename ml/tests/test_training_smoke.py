"""
Tests "smoke" des 3 scripts d'entraînement : ils doivent s'exécuter de bout
en bout sur le jeu de données synthétique de repli (cf. common.py) sans
lever d'exception, et produire des métriques cohérentes.

Ces tests ne valident PAS la qualité prédictive des modèles (impossible sans
les vraies données Kaggle) : ils garantissent que le pipeline (features ->
preprocessing -> entraînement -> tracking MLflow -> sauvegarde locale) reste
exécutable à chaque changement de code, ce qui est l'objet même de la CI.
"""
import sys
from pathlib import Path

import pytest

ML_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ML_DIR))
sys.path.insert(0, str(ML_DIR / "training"))


@pytest.fixture(autouse=True)
def _isolated_mlflow(tmp_path, monkeypatch):
    """Isole chaque test avec son propre tracking MLflow SQLite temporaire."""
    db_path = tmp_path / "mlflow.db"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{db_path}")
    yield


def test_train_classification_smoke():
    import train_classification

    metrics = train_classification.train()
    assert 0.0 <= metrics["f1_macro"] <= 1.0
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert metrics["n_train"] > 0 and metrics["n_test"] > 0


def test_train_regression_smoke():
    import train_regression

    metrics = train_regression.train()
    assert metrics["rmse"] >= 0
    assert metrics["mae"] >= 0
    assert metrics["n_train"] > 0 and metrics["n_test"] > 0


def test_train_clustering_smoke():
    import train_clustering

    metrics = train_clustering.train()
    assert -1.0 <= metrics["silhouette_score"] <= 1.0
    assert metrics["k"] > 0
    assert metrics["n_samples"] > 0