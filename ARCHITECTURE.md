# Technical Architecture — H&M Retail Intelligence Platform

<p align="center">
  <a href="./ARCHITECTURE.md"><strong>🇬🇧 English</strong></a> ·
  <a href="./ARCHITECTURE.fr.md">🇫🇷 Français</a>
</p>

This document describes **only the architecture that is actually in place today**: the data flow
that runs end to end, the exact role of each Docker service supporting it, and how each piece fits
together. A final section (§5) separately lists the pieces that are still placeholders, without
presenting them as functional.

---

## 1. The implemented data flow, diagrammed

```
                         ┌──────────────────────────┐
   Kaggle CSVs      ───▶ │   Notebooks (01 → 07)     │ ───▶ results already computed in the .ipynb
  (data/raw/)            │   cleaning → EDA → ML     │      files + ml/models/ (direct export of the
                         └──────────────────────────┘      06-07 models)

                         ┌──────────────────────────┐
   Kaggle CSVs      ───▶ │   Spark (spark/jobs/,     │
  (data/raw/)            │   spark/utils/)           │
                         └───────────┬──────────────┘
                                     │ JDBC (write)
                                     ▼
                    ┌─────────────────────────────────┐
                    │   PostgreSQL                      │
                    │   star schema + Data Marts         │
                    │   including customers_features_train│
                    └───────────┬─────────────────────┘
                                 │ SELECT (ml/common.py)
                                 ▼
                    ┌─────────────────────────────────┐
                    │   ml/training/train_*.py           │──▶ MLflow (tracking + Model Registry,
                    │   (classification, regression,     │    "champion" alias)
                    │    clustering)                      │
                    └───────────┬─────────────────────┘
                                 │ models:/<name>@champion (or local fallback ml/models/)
                                 ▼
                    ┌─────────────────────────────────┐
                    │   ml/serving/app.py                │──▶ /predict/club-status
                    │   (FastAPI API)                    │    /predict/segment
                    └─────────────────────────────────┘    /predict/spend

                    ┌─────────────────────────────────┐
                    │   ml/monitoring/drift_report.py     │──▶ HTML drift report (Evidently AI)
                    └─────────────────────────────────┘

CI/CD: .github/workflows/mlops-ci.yml (lint, tests, image build, scheduled retraining)
```

**Important point not to miss**: the notebooks and the Spark pipeline both start from the **same
raw CSVs**, but they are **two independent paths** that don't run one after the other:
- the notebooks produce results that are already visible (analysis, directly exported models) on a
  fixed snapshot of the data;
- the Spark → PostgreSQL → `ml/` pipeline is the "live" path, replayable at will, that feeds the
  serving API.

Both apply the same cleaning and the same model recipes, without a strict guarantee that they run
on exactly the same data snapshot at the same time (see `ml/MLOPS_GUIDE.md` §10).

---

## 2. Detailed role of each implemented piece

| Piece | Role | How it actually works |
|---|---|---|
| `notebooks/` | Full EDA → feature engineering → ML analysis | 7 notebooks run in order, each consuming the previous one's output (`intermediate/` folder, generated at execution time). Notebooks 06-07 directly export the selected models to `ml/models/`. |
| `data/raw/` | Input to the Spark pipeline | Raw Kaggle CSVs (`customers.csv`, `articles.csv`, `transactions_train.csv`), not currently versioned in Git (DVC is configured but the remote still needs finalizing, see §5). |
| `spark/` | Turns the raw CSVs into a PostgreSQL Data Warehouse | `jobs/pipeline_hm.py` orchestrates reading (`utils/schemas.py`) → cleaning (`utils/cleaning.py`) → RFM feature engineering (`utils/features.py`) → JDBC write. Full detail: `spark/README.md`. |
| `ml/training/` | Trains the 3 models validated in the notebooks, in a scripted way | Loads `customers_features_train` (PostgreSQL, with a synthetic fallback), reproduces the exact recipe from notebooks 06-07, logs to MLflow, `--register` for the Model Registry. |
| `ml/serving/` | Exposes the models via an API | FastAPI, loads `models:/<name>@champion` (MLflow Registry) with automatic fallback to `ml/models/*.joblib`. Never connects to PostgreSQL at inference time — features arrive in the HTTP request. |
| `ml/monitoring/` | Detects data drift | Compares a reference window and a current window of `customers_features_train` with Evidently AI, generates an HTML report. |
| `.github/workflows/mlops-ci.yml` | CI/CD | Lint + tests on every push/PR touching `ml/`; builds the `ml-serving` image on `main`; retraining + monitoring on a weekly cron (requires a runner with network access to PostgreSQL/MLflow, see `ml/MLOPS_GUIDE.md` §7). |
| `docker-compose.yml` | Runs the containers for the pieces above | See §3 for the service-by-service detail. |

---

## 3. Docker services supporting an implemented piece

| Service | Image | What it actually does today |
|---|---|---|
| `postgres` | `postgres:15-alpine` | Stores the star schema + Data Marts produced by `spark/jobs/pipeline_hm.py`, including `customers_features_train` |
| `adminer` | `adminer:latest` | Web interface to browse PostgreSQL's contents (`http://localhost:8081`) |
| `spark-master` / `spark-worker` | local build (`spark/Dockerfile`) | Run `spark/jobs/pipeline_hm.py` |
| `mlflow` | `ghcr.io/mlflow/mlflow` | Tracking server + Model Registry, used by `ml/training/` and `ml/serving/` |
| `ml-serving` | local build (`ml/serving/Dockerfile`) | Runs the FastAPI API from `ml/serving/app.py` |

They all communicate on the `shop_data_net` Docker network, using their **service name**
(`postgres`, `mlflow`) — not `localhost` — when calling each other inside Docker. Named volumes
(`postgres_data`, `mlflow_data`) ensure persistence across restarts.

**Minimal startup for these 5 services**:
```bash
docker compose up -d postgres adminer spark-master spark-worker mlflow ml-serving
```

---

## 4. Use cases covered by the implemented flow

1. **Customer data cleaning & quality** (statistically justified median/mode imputation) —
   notebook 01, reused in `spark/utils/cleaning.py`.
2. **Large-scale product & transaction exploration** (33.7M transaction rows) — notebook 02.
3. **Enriched RFM segmentation** (weather, public holidays) — notebook 03.
4. **Customer feature engineering** — notebook 04, industrialized in
   `spark/utils/features.py` → `customers_features_train` table.
5. **Dimensionality reduction & exploratory clustering** — notebook 05.
6. **Club status classification** (`club_member_status`, Random Forest) and **total spend
   regression** (`total_spend`, XGBoost) — notebook 06, reproduced by
   `ml/training/train_classification.py` and `train_regression.py`, served by `ml/serving/`.
7. **Customer segmentation** (K-Means, k=6) — notebook 07, reproduced by
   `ml/training/train_clustering.py`, served by `ml/serving/`.

---

## 5. What is not implemented (for reference, without ambiguity)

These elements exist in the repo (folder, Dockerfile, or Docker service that starts) but **contain
no functional logic connected to the rest**:

| Element | Actual state |
|---|---|
| `kafka/producers/`, `kafka/consumers/` | Empty folders (`.gitkeep`). The `kafka` service starts but nothing publishes/consumes messages. |
| `n8n/workflows/` | Empty folder. The `n8n` service starts but no workflow is defined. |
| `backend/app/` | Empty folder. No application API. |
| `frontend/src/` | Empty folder. No user interface. |
| RAG chatbot (`ollama`, `qdrant`) | Docker services that start, but not connected to a knowledge base or a frontend. |
| `data/processed/`, `data/features/` | Not fed by the active pipeline (leftover from an earlier version). |
| DVC/DagsHub remote | `.dvc/config` contains a URL template, to be replaced with the real DagsHub repo. |
| Docker image publishing (`build-serving-image` in CI) | The build works, but publishing to an image registry is pre-written as a comment, not enabled. |

---

## 6. How to contribute to an unimplemented piece

1. Remove the `.gitkeep` from the relevant folder once real content has been added.
2. Respect the intended role of that folder (e.g. `kafka/producers/` should only publish events,
   not contain business logic).
3. Update this document and `README.md` to reflect the new state — the rule for this repo is that
   a folder is never documented as "implemented" until it actually runs what is described.