"""
Tests de l'API FastAPI (ml/serving/app.py) sur le repli local, à partir des
modèles produits par les scripts ml/training/. Ce test dépend de
test_training_smoke.py pour avoir des modèles locaux disponibles dans
ml/models/ ; en CI, la CI exécute d'abord les entraînements (cf.
.github/workflows/mlops-ci.yml).
"""
import sys
from pathlib import Path

import pytest

ML_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ML_DIR))
sys.path.insert(0, str(ML_DIR / "serving"))


@pytest.fixture(scope="module", autouse=True)
def _ensure_local_models():
    """S'assure que des modèles locaux existent (les entraîne si besoin)."""
    sys.path.insert(0, str(ML_DIR / "training"))
    for task in ("classification", "regression", "clustering"):
        model_path = ML_DIR / "models" / task / "model.joblib"
        if not model_path.exists():
            module = __import__(f"train_{task}")
            module.train()


@pytest.fixture
def client(monkeypatch):
    # Un tracking URI "file://" échoue vite (backend filestore obsolète dans
    # MLflow récent) contrairement à une adresse réseau injoignable, qui peut
    # traîner plusieurs dizaines de secondes en retries HTTP avant d'échouer.
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "file:///tmp/hm_mlops_test_unreachable")
    import app as app_module
    from fastapi.testclient import TestClient

    app_module._REGISTRY.clear()
    return TestClient(app_module.app)


BEHAVIOR_PAYLOAD = {
    "age": 34, "n_transactions": 27, "tenure_days": 540, "n_distinct_categories": 6,
    "avg_basket_value": 42.5, "purchase_frequency_per_month": 1.8, "recency_days": 12,
}

SPEND_PAYLOAD = {
    "age": 34, "n_transactions": 27, "tenure_days": 540, "n_distinct_categories": 6,
    "purchase_frequency_per_month": 1.8, "recency_days": 12,
    "club_member_status": "ACTIVE", "fashion_news_frequency": "Regularly", "age_group": "26-35",
}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert all(body["models_loaded"].values())


def test_predict_club_status(client):
    r = client.post("/predict/club-status", json=BEHAVIOR_PAYLOAD)
    assert r.status_code == 200
    body = r.json()
    assert body["club_member_status"] in body["probabilities"]
    assert abs(sum(body["probabilities"].values()) - 1.0) < 1e-3


def test_predict_segment(client):
    r = client.post("/predict/segment", json=BEHAVIOR_PAYLOAD)
    assert r.status_code == 200
    assert isinstance(r.json()["cluster"], int)


def test_predict_spend(client):
    r = client.post("/predict/spend", json=SPEND_PAYLOAD)
    assert r.status_code == 200
    assert r.json()["predicted_total_spend"] >= 0


def test_predict_invalid_payload(client):
    r = client.post("/predict/club-status", json={"age": -5})
    assert r.status_code == 422