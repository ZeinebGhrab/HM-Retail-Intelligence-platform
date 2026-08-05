"""
Tests du garde-fou de promotion automatique du champion MLflow
(ml/training/training_api.py). Couvre spécifiquement le seuil de qualité
absolu par tâche (`QUALITY_GATES`), qui bloque une promotion même en
l'absence de champion actuel ou face à un champion pire (ce qu'une simple
comparaison relative au champion précédent ne peut pas détecter seule).

Ces tests évitent tout entraînement réel ou accès PostgreSQL/MLflow réseau :
`_run_task` est exercé avec des fonctions d'entraînement factices
(monkeypatch de TASKS[...]["train_fn"]) qui renvoient des métriques
contrôlées.
"""
import sys
from pathlib import Path

import pytest

ML_DIR = Path(__file__).resolve().parent.parent
for p in (ML_DIR, ML_DIR / "training"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import training_api  # noqa: E402

# --- Tests unitaires de _check_quality_gate ----------------------------------

@pytest.mark.parametrize(
    "task,metrics,expected_passed",
    [
        ("classification", {"f1_macro": 0.50}, True),
        ("classification", {"f1_macro": 0.19}, False),   # < min (0.20)
        ("classification", {"f1_macro": 0.20}, True),     # égal au min -> passe
        ("regression", {"r2_log_target": 0.94}, True),
        ("regression", {"r2_log_target": 0.10}, False),   # < min (0.50)
        ("clustering", {"silhouette_score": 0.35}, True),
        ("clustering", {"silhouette_score": 0.05}, False),  # < min (0.10)
        ("classification", {}, False),                    # métrique absente -> jamais promu
    ],
)
def test_check_quality_gate(task, metrics, expected_passed):
    result = training_api._check_quality_gate(task, metrics)
    assert result["passed"] is expected_passed


# --- Tests d'intégration de _run_task (train_fn factice) ---------------------

@pytest.fixture
def patch_train_fn(monkeypatch):
    """Remplace TASKS[task]['train_fn'] par une fonction factice retournant
    les métriques passées, sans entraînement réel ni écriture MLflow."""

    def _patch(task: str, metrics: dict):
        monkeypatch.setitem(
            training_api.TASKS[task], "train_fn", lambda register=False: metrics
        )

    return _patch


def test_bad_model_never_promoted_even_without_champion(monkeypatch, patch_train_fn):
    """Un modèle clairement cassé ne doit JAMAIS être promu, même s'il n'y a
    pas encore de champion (cas que seule une comparaison relative laisserait
    passer, puisque 'pas de champion' -> _is_better() renvoie toujours True)."""
    patch_train_fn("classification", {"f1_macro": 0.05})
    # Pas de champion existant : _current_champion_metric renverrait None de toute façon,
    # mais on le neutralise explicitement pour isoler le test du réseau MLflow.
    monkeypatch.setattr(training_api, "_current_champion_metric", lambda *a, **k: None)

    result = training_api._run_task("classification", register=True, promote=True)

    assert result["quality_gate"]["passed"] is False
    assert result["promoted"] is False


def test_good_model_promoted_without_champion(monkeypatch, patch_train_fn):
    patch_train_fn("classification", {"f1_macro": 0.55})
    monkeypatch.setattr(training_api, "_current_champion_metric", lambda *a, **k: None)
    monkeypatch.setattr(training_api, "_promote_latest_version", lambda model_name: "1")

    result = training_api._run_task("classification", register=True, promote=True)

    assert result["quality_gate"]["passed"] is True
    assert result["promoted"] is True
    assert result["champion_version"] == "1"


def test_good_but_worse_than_champion_not_promoted(monkeypatch, patch_train_fn):
    """Passe le seuil absolu, mais moins bon que le champion actuel -> pas promu."""
    patch_train_fn("regression", {"r2_log_target": 0.80})
    monkeypatch.setattr(training_api, "_current_champion_metric", lambda *a, **k: 0.94)

    result = training_api._run_task("regression", register=True, promote=True)

    assert result["quality_gate"]["passed"] is True
    assert result["promoted"] is False