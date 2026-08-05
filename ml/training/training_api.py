"""
API HTTP de déclenchement des ré-entraînements (ml/training/train_*.py), pensée
pour être appelée depuis le workflow n8n (voir
n8n/workflows/HM Streaming Pipeline.json et n8n/workflows/README.md) ou
manuellement en local/CI.

Complète le point laissé en suspens dans ml/MLOPS_GUIDE.md §10
("Limites actuelles & prochaines étapes") : la promotion de l'alias MLflow
"champion" n'était jusqu'ici qu'une commande manuelle
(`mlflow models set-alias <nom> champion <version>`, cf. §9 du guide) et
aucun garde-fou n'empêchait de promouvoir un modèle moins bon que le
précédent — ni même un modèle simplement mauvais en absolu. Ce service
automatise trois choses :

1. il entraîne (via les fonctions `train()` déjà définies dans
   ml/training/train_*.py, réutilisées telles quelles — aucune logique de
   ML dupliquée ici) ;
2. il vérifie un seuil de qualité absolu par tâche (`QUALITY_GATES`
   ci-dessous) — un modèle qui ne l'atteint pas n'est JAMAIS promu, même
   s'il n'y a pas encore de champion ou si le champion actuel est pire ;
3. seulement si ce seuil est passé, il compare la métrique clé du nouveau
   run à celle du champion actuel (lue via l'API MLflow) et ne promeut la
   nouvelle version que si elle est meilleure ou égale.

Le run est toujours enregistré dans le Model Registry MLflow si
`register=true` (utile pour l'audit/la comparaison manuelle dans l'UI
MLflow), qu'il passe ou non le seuil de qualité — seule la promotion en
`champion` est bloquée.

Lancement local :
    uvicorn ml.training.training_api:app --reload --port 8600

Endpoints :
    GET  /health
    POST /train/classification[?register=true&promote=true]
    POST /train/regression[?register=true&promote=true]
    POST /train/clustering[?register=true&promote=true]
    POST /train/all[?register=true&promote=true]
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

# Même stratégie double sys.path que ml/serving/app.py : ce module est chargé
# différemment localement (`uvicorn ml.training.training_api:app` depuis la
# racine du dépôt) qu'en conteneur (`uvicorn training.training_api:app` avec
# WORKDIR=/opt/ml, cf. training/Dockerfile) — on ajoute donc à la fois ml/
# (pour "common") et ml/training/ (pour les imports "train_*" en direct).
_THIS_DIR = Path(__file__).resolve().parent
_ML_DIR = _THIS_DIR.parent
for _p in (_ML_DIR, _THIS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from common import load_config  # noqa: E402
from train_classification import train as train_classification  # noqa: E402
from train_clustering import train as train_clustering  # noqa: E402
from train_regression import train as train_regression  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ml-training-trigger")

app = FastAPI(
    title="H&M Retail Intelligence — ML Training Trigger API",
    description=(
        "Déclenche les ré-entraînements des 3 modèles et promeut automatiquement "
        "l'alias MLflow 'champion' en cas d'amélioration."
    ),
    version="1.0.0",
)

# Pour chaque tâche : fonction d'entraînement (ml/training/train_*.py, non
# modifiées), clé de config (ml/config.yaml) pour le nom du modèle enregistré,
# et métrique utilisée pour décider si le nouveau run mérite de devenir
# champion ("higher" = plus haut est meilleur, "lower" = plus bas est meilleur).
TASKS: dict[str, dict[str, Any]] = {
    "classification": {"train_fn": train_classification, "config_key": "classification", "metric": "f1_macro", "direction": "higher"},
    "regression": {"train_fn": train_regression, "config_key": "regression", "metric": "rmse", "direction": "lower"},
    "clustering": {"train_fn": train_clustering, "config_key": "clustering", "metric": "silhouette_score", "direction": "higher"},
}

# Seuil de qualité absolu par tâche : en dessous, un modèle n'est JAMAIS promu
# "champion", même s'il n'y a pas encore de champion ou si le champion actuel
# est pire (ce que la comparaison relative de TASKS/_is_better ne peut pas
# détecter à elle seule). Les trois métriques choisies ici sont bornées et
# comparables indépendamment de l'échelle des données ("higher is better"
# dans les trois cas), contrairement à `rmse` (dépend de l'échelle monétaire
# de total_spend) utilisé pour la comparaison relative.
#
# Valeurs de départ à AJUSTER par l'équipe (cf. ml/MLOPS_GUIDE.md §10,
# "Tests de qualité prédictive... pas encore automatisés") — fixées ici
# nettement en dessous des scores obtenus sur les vraies données dans les
# notebooks (F1-macro=0.3889 pour la classification, R²(log)=0.943 pour la
# régression) : le but est de bloquer un modèle clairement cassé (bug de
# feature engineering, données vides...), pas d'exiger de battre le
# notebook à chaque run.
QUALITY_GATES: dict[str, dict[str, Any]] = {
    "classification": {"metric": "f1_macro", "min": 0.20},
    "regression": {"metric": "r2_log_target", "min": 0.50},
    "clustering": {"metric": "silhouette_score", "min": 0.10},
}


def _current_champion_metric(model_name: str, metric: str) -> float | None:
    """Lit la métrique `metric` du run MLflow associé à l'alias 'champion' actuel.

    Retourne None si le modèle n'a pas encore de champion (première
    promotion) ou si le tracking server MLflow est injoignable.
    """
    try:
        import mlflow
        from mlflow.tracking import MlflowClient

        client = MlflowClient()
        version = client.get_model_version_by_alias(model_name, "champion")
        run = mlflow.get_run(version.run_id)
        value = run.data.metrics.get(metric)
        return float(value) if value is not None else None
    except Exception as e:
        logger.info("Pas de champion actuel pour '%s' (%s) — première promotion possible.", model_name, e)
        return None


def _check_quality_gate(task: str, metrics: dict[str, Any]) -> dict[str, Any]:
    """Vérifie le seuil de qualité absolu défini dans QUALITY_GATES pour `task`.

    Retourne un dict {metric, min, value, passed} inclus tel quel dans la
    réponse de l'API, pour que n8n (et un humain qui relit les logs) voie
    immédiatement pourquoi une promotion a été bloquée.
    """
    gate = QUALITY_GATES[task]
    value = metrics.get(gate["metric"])
    passed = value is not None and value >= gate["min"]
    return {"metric": gate["metric"], "min": gate["min"], "value": value, "passed": passed}


def _is_better(new_value: float, current_value: float | None, direction: str) -> bool:
    if current_value is None:
        return True
    if direction == "higher":
        return new_value >= current_value
    return new_value <= current_value


def _promote_latest_version(model_name: str) -> str:
    """Pointe l'alias 'champion' vers la version la plus récente de `model_name`."""
    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    latest = max(client.search_model_versions(f"name='{model_name}'"), key=lambda v: int(v.version))
    client.set_registered_model_alias(model_name, "champion", latest.version)
    return latest.version


def _run_task(task: str, register: bool, promote: bool) -> dict[str, Any]:
    if task not in TASKS:
        raise HTTPException(status_code=404, detail=f"Tâche inconnue : {task}")

    spec = TASKS[task]
    config = load_config()
    model_name = config[spec["config_key"]]["model_name"]
    metric_name = spec["metric"]

    logger.info("Lancement de l'entraînement '%s' (register=%s, promote=%s)", task, register, promote)
    try:
        metrics = spec["train_fn"](register=register)
    except Exception as e:
        logger.exception("Échec de l'entraînement '%s'", task)
        raise HTTPException(
            status_code=500,
            detail=f"Entraînement '{task}' échoué : {type(e).__name__}: {e}",
        )

    quality_gate = _check_quality_gate(task, metrics)

    result: dict[str, Any] = {
        "task": task,
        "model_name": model_name,
        "metrics": metrics,
        "quality_gate": quality_gate,
        "promoted": False,
    }

    if not quality_gate["passed"]:
        logger.warning(
            "Entraînement '%s' SOUS le seuil de qualité minimal (%s=%s < %s) — promotion bloquée, "
            "même si aucun champion n'existe encore ou si le champion actuel est pire.",
            task, quality_gate["metric"], quality_gate["value"], quality_gate["min"],
        )
        return result

    if register and promote:
        current = _current_champion_metric(model_name, metric_name)
        new_value = metrics.get(metric_name)
        result["current_champion_metric"] = current
        if new_value is not None and _is_better(new_value, current, spec["direction"]):
            version = _promote_latest_version(model_name)
            result["promoted"] = True
            result["champion_version"] = version
            logger.info(
                "Nouveau champion pour '%s' : version %s (%s=%.4f).",
                model_name, version, metric_name, new_value,
            )
        else:
            logger.info(
                "Nouvelle version de '%s' NON promue : %s=%s pas meilleur que le champion actuel (%s).",
                model_name, metric_name, new_value, current,
            )

    return result


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/train/{task}")
def train_task(task: str, register: bool = True, promote: bool = True) -> dict[str, Any]:
    return _run_task(task, register, promote)


@app.post("/train/all")
def train_all(register: bool = True, promote: bool = True) -> dict[str, Any]:
    results: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []

    for task in TASKS:
        try:
            results[task] = _run_task(task, register, promote)
        except HTTPException as e:
            failures.append({"task": task, "detail": e.detail})
            results[task] = {"task": task, "error": e.detail}

    if failures:
        # 207-like : on renvoie quand même les résultats des tâches réussies,
        # mais un statut d'erreur global pour que n8n déclenche sa branche
        # d'échec (voir n8n/workflows/README.md).
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Un ou plusieurs entraînements ont échoué.",
                "failures": failures,
                "results": results,
            },
        )

    return {"status": "success", "results": results}