# MLOps Guide — H&M Retail Intelligence Platform

<p align="center">
  <a href="./MLOPS_GUIDE.md"><strong>🇬🇧 English</strong></a> ·
  <a href="./MLOPS_GUIDE.fr.md">🇫🇷 Français</a>
</p>

This guide documents the concrete implementation of the MLOps stack announced in
`ARCHITECTURE.md` §5 (Git, DVC, DagsHub, MLflow, GitHub Actions, Evidently AI). It takes the `ml/`
folder from "placeholder" to an end-to-end runnable pipeline: versioned and tracked training, an
inference service, drift monitoring, CI/CD — **wired to the platform's real data source: the
PostgreSQL `customers_features_train` table, produced by `spark/jobs/pipeline_hm.py`** (not a
CSV).

> **Who is this guide for?** Anyone picking up the project after the Spark → PostgreSQL pipeline
> has been set up, who needs to either rerun training, wire the backend/frontend to the models, or
> monitor their drift in production.

---

## 1. Overview of the ML part

```
data/raw/*.csv (Kaggle)
        │
        ▼  spark-submit pipeline_hm.py (see spark/README.md)
┌─────────────────────────┐
│  PostgreSQL              │
│  customers_features_train│  ◀── table produced by compute_customer_features()
│  (+ dim_*, fact_*, marts)│      (spark/utils/features.py)
└──────────┬───────────────┘
           │  SELECT * FROM customers_features_train  (ml/common.py::load_customer_features)
           ▼
┌───────────────────────┐
│   ml/training/          │   train_classification.py  -> club_member_status
│   (scripts, --register) │   train_regression.py      -> total_spend
│                         │   train_clustering.py      -> segment (K-Means, k=6)
└───────────┬─────────────┘
           │  tracking (params, metrics, artifacts)
           ▼
┌───────────────────────┐
│   MLflow Tracking       │──▶ Model Registry ("champion" alias)
│   Server (Docker)       │
└───────────┬─────────────┘
           │  models:/<name>@champion
           ▼
┌───────────────────────┐        ┌──────────────────────────┐
│   ml/serving/app.py     │◀──────▶│  ml/models/*/*.joblib      │
│   (FastAPI API)          │       │  (local fallback outside MLflow) │
└───────────┬─────────────┘        └──────────────────────────┘
           │ /predict/*
           ▼
       backend/app/  (application API, consumes ml/serving/)

┌───────────────────────┐
│   ml/monitoring/         │  Evidently AI: drift report
│   drift_report.py         │  (reference vs current window of customers_features_train)
└───────────────────────┘

CI/CD orchestration: .github/workflows/mlops-ci.yml
```

Every script in the `ml/` folder reuses logic already validated in the notebooks (features,
preprocessing, algorithm choice): see `ml/config.yaml` for the exact mapping to notebooks 05-07,
and the comments at the top of each script for which notebook section it's based on.

**What this guide covers:** setting up the tooling (Postgres access, MLflow, CI/CD, monitoring)
and how to use it. **What it does not cover:** the predictive quality of the models themselves,
which depends on the real Kaggle data and is discussed in `notebooks/README.md` §3 and
`notebooks/DETAILS.md`.

---

## 2. The source of the features: PostgreSQL, not a CSV

**Important architectural point, easy to miss**: the repo's `data/features/` folder **is no
longer fed by the active pipeline**. `spark/jobs/pipeline_hm.py` reads the Kaggle CSVs from
`data/raw/`, but writes exclusively to PostgreSQL (see `spark/README.md` §5-7) — the
`customers_features_train` table (and the other star-schema tables) are therefore **the single
source of truth** for customer features.

`ml/common.py::load_customer_features()` runs `SELECT * FROM customers_features_train` via
SQLAlchemy/psycopg2, with these columns (produced by
`spark/utils/features.py::compute_customer_features`):

| Column | Role |
|---|---|
| `customer_key` | Customer identifier (`crc32` hash, replaces `customer_id` in the warehouse) — never used as a feature |
| `age`, `age_group`, `club_member_status`, `fashion_news_frequency`, `postal_code` | Demographic attributes (joined from `customers_clean`) |
| `total_spend`, `n_transactions`, `first_purchase`, `last_purchase` | Basic RFM |
| `recency_days`, `tenure_days`, `avg_basket_value`, `purchase_frequency_per_month` | Derived RFM |
| `n_distinct_categories` | Purchase diversity |
| `segment_valeur` | Value segment by quartile (`Bas (Q1)` → `Haut (Q4 - VIP)`), computed via `approxQuantile` |

### Prerequisites before training on real data

1. Place the 3 Kaggle CSVs (`customers.csv`, `articles.csv`, `transactions_train.csv`) in
   `data/raw/`.
2. Start the infrastructure: `./run.sh infra` (or `./run.sh all`).
3. Run the Spark job (see `spark/README.md` §9):
   ```bash
   docker exec shop-spark-worker \
     /opt/spark/bin/spark-submit \
     --master spark://spark-master:7077 \
     /opt/spark/work-dir/jobs/pipeline_hm.py
   ```
4. Check that the table exists (via Adminer at `http://localhost:8081`, or `psql`):
   ```sql
   SELECT count(*) FROM customers_features_train;
   ```
5. Only from that point on will `ml/training/train_*.py` and `ml/serving/app.py` read real data.
   **As long as this table doesn't exist or is empty**, `ml/common.py` automatically falls back to
   a synthetic dataset with the same schema (with an explicit console `WARNING`) — handy for
   developing/testing without depending on the full pipeline, but never to be confused with real
   training.

### Connection variables (`.env`)

`ml/common.py` reuses the PostgreSQL variables already defined for the rest of the platform
(`POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`), plus one new variable
specific to `ml/`:

```bash
# .env
POSTGRES_HOST=localhost   # ml/ scripts run outside Docker (port published on the host)
```

The `ml-serving` service in `docker-compose.yml` (see §5) automatically forces
`POSTGRES_HOST=postgres` (the Docker service name) — this variable only needs to be set in `.env`
for running the `ml/training/`/`ml/serving/` scripts **outside Docker**, on a dev machine.

---

## 3. Two ways to obtain the trained models

### 3.0 Direct path (recommended): export from the notebooks

Notebooks 06 and 07 contain, right after the conclusion of each model comparison, a
`joblib.dump(...)` cell that exports **the model actually selected** (the one documented in the
§17.8 summary) directly into the repo's `ml/models/<task>/`:

| Notebook | Export cell (after…) | Files produced |
|---|---|---|
| `06_ML_Classification_Regression.ipynb` | §17.5.1 (optimized Random Forest), before the boosting/SMOTE section 17.5.2 | `ml/models/classification/model.joblib`, `scaler.joblib` |
| `06_ML_Classification_Regression.ipynb` | §17.6.5 (residual analysis), before the end-of-section memory cleanup | `ml/models/regression/model.joblib`, `scaler.joblib`, `selector.joblib`, `feature_columns.joblib` |
| `07_ML_Clustering_Approfondi_Synthese.ipynb` | §17.7.5 (clustering summary), before the overall summary 17.8 | `ml/models/clustering/model.joblib`, `scaler.joblib` |

**Steps to follow:**
1. Run the 01 → 07 series in order on the real Kaggle data (see `notebooks/README.md`). These
   notebooks still read the Kaggle CSVs directly (`customers.csv` etc. placed next to the notebook
   or on Drive) — they are **independent** from the Spark/PostgreSQL pipeline, which is the path
   used by `ml/training/` and the rest of the real-time platform. Both paths start from the same
   raw CSVs and apply the same cleaning, but remain two separate runs (see §7 "Limitations").
2. If the notebooks are opened/run **from the `notebooks/` folder** (the standard local case), the
   export cells automatically detect `../ml/models/` and write there directly — nothing else to
   do, `ml/serving/app.py` will use these files as soon as the API is next started.
3. On Google Colab (or any run where the repo's `ml/` isn't visible from the current directory),
   the cells detect the folder is missing and export to
   `<BASE_PATH>/ml_models_export/<task>/` instead, with an explicit message — you then need to
   manually copy this folder into the repo's `ml/models/`.

These cells export **exactly** the model object that produced the metrics already shown in the
notebook (`gs_rf.best_estimator_`, `fitted_reg_v2[best_reg_v2_name][0]`, `kmeans_v2`) — not a
reimplementation. No `label_encoder.joblib` is exported for classification: the
`RandomForestClassifier` is trained directly on the text labels (`club_member_status`), and
`ml/serving/app.py` natively handles this case (uses `model.classes_`).

> **Why didn't these cells exist from the start?** A Jupyter notebook (`.ipynb`) only keeps the
> code and the outputs already displayed (text, charts) — never the trained Python objects held in
> memory. Without an explicit export cell, a model trained in a notebook is unrecoverable once the
> session is closed.

### 3.1 Alternative path: `ml/training/` scripts (CI, automated retraining, Postgres data)

For scriptable retraining (CI/CD, cron, without going back through Jupyter) **and wired to the
real-time platform's up-to-date data** (the `customers_features_train` table, refreshed on every
run of the Spark pipeline), the `ml/training/train_*.py` scripts reproduce the exact same recipe
(same hyperparameters, same feature selection) as the notebooks — see the summary table in §4.
Unlike the notebooks, these scripts read PostgreSQL, not CSVs: they therefore reflect the most
recent data processed by Spark, not necessarily what was seen at the time the 01-07 notebooks ran.

Both paths produce artifacts compatible with `ml/serving/app.py` (same file names), so they're
interchangeable depending on context: notebooks for human review with visualizations on a CSV
snapshot, scripts for automation on the warehouse's live data.

---

## 4. Experiment tracking & Model Registry — MLflow

### Starting an MLflow server

Locally with Docker Compose (the `mlflow` service added to `docker-compose.yml`):
```bash
cp .env.example .env      # if not already done — defines MLFLOW_PORT (5000 by default)
./run.sh ml                # starts mlflow + ml-serving (or ./run.sh all for the full stack)
```
The UI is available at `http://localhost:5000`: experiments, run comparison, metric curves, model
registry.

Locally without Docker (dev machine):
```bash
pip install -r ml/requirements.txt
mlflow server --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlruns_artifacts --port 5000
export MLFLOW_TRACKING_URI=http://localhost:5000   # or set it in .env
```

> **Why SQLite/Postgres and not the file backend (`./mlruns`)?** Recent MLflow versions have put
> the file backend into maintenance mode: the Model Registry (needed for `--register`) requires a
> database backend. `sqlite:///mlflow.db` is enough for local use; in production, point to the
> PostgreSQL database already present in `docker-compose.yml` (create a schema/database dedicated
> to MLflow, separate from `hm_retail`, so ML tracking doesn't mix with business data).

### Running a training run (with tracking, PostgreSQL data if available)
```bash
python ml/training/train_classification.py            # tracks the run, without registering the model
python ml/training/train_classification.py --register  # + registers it in the Model Registry
python ml/training/train_regression.py --register
python ml/training/train_clustering.py --register
```
Each script:
1. loads the `customers_features_train` table from PostgreSQL (or generates a synthetic dataset
   with the same schema if the connection fails or the table is empty — handy in CI/demos, see the
   warning shown in the console);
2. reproduces the preprocessing from the corresponding notebook (standardization, one-hot,
   feature selection for regression);
3. trains **exactly the model selected in the notebook** (see table below), not an approximate
   reimplementation — the hyperparameters come directly from results already run in notebooks
   06-07;
4. logs to MLflow: hyperparameters, metrics (F1-macro/accuracy, RMSE/MAE/R², silhouette), and the
   model itself (MLflow flavor matching the algorithm);
5. also saves a local copy to `ml/models/<task>/` for the serving API's fallback outside MLflow
   (§5).

### Reproduced models (from notebooks 06-07, not a rough reimplementation)

| Task | Selected model | Source | Result (notebook) |
|---|---|---|---|
| `club_member_status` classification | `RandomForestClassifier(n_estimators=200, max_depth=20, min_samples_leaf=5, class_weight="balanced")` — **without SMOTE** | Exact `best_params_` from `GridSearchCV`, notebook 06 §17.5.1 | F1-macro=0.3889 (beats CatBoost+SMOTE at 0.3652, §17.5.2) |
| `total_spend` regression | `SelectKBest(f_regression, k=12)` then `XGBRegressor(random_state=42)` (default hyperparameters) on `log1p(total_spend)` | Notebook 06 §17.6.2 and §17.6.4 | R²(test, log)=0.943 |
| Clustering | `KMeans(n_clusters=6, n_init=10)` | Notebook 07 §17.7.2 (beats GMM and hierarchical on silhouette) | Silhouette=0.2537 |

> **Point to note**: notebooks 06/07 themselves did not export any trained model before the cells
> added in §3.0 (no `joblib.dump`/`pickle.dump` on the final models originally) — only the §17.8
> summary documented the winner of each comparison. The `ml/training/` scripts therefore re-run
> the same recipe (same hyperparameters, same feature selection, same transformed target) to
> produce an artifact that's actually servable from the PostgreSQL data, instead of starting over
> with different choices.

### Promoting a model to production (alias)
MLflow 2.9+ replaces the old "stages" (Staging/Production) with **aliases**. After comparing
several runs in the MLflow UI and picking the best one:
```bash
mlflow models set-alias hm-club-status-classifier champion 3   # promotes version 3
```
`ml/serving/app.py` always loads `models:/<name>@champion`: changing the alias is enough to deploy
a new version without touching the serving code or redeploying the API.

### Names of the registered models
Defined in `ml/config.yaml`:
| Task | Name in the Registry |
|---|---|
| `club_member_status` classification | `hm-club-status-classifier` |
| `total_spend` regression | `hm-spend-regressor` |
| Clustering / segmentation | `hm-customer-segmentation` |

---

## 5. Inference service — `ml/serving/`

### Running the API locally
```bash
pip install -r ml/requirements.txt
uvicorn ml.serving.app:app --reload --port 8500
```
Auto-generated interactive documentation: `http://localhost:8500/docs`.

### Endpoints
| Method | Route | Description |
|---|---|---|
| GET | `/health` | API status + availability of each model |
| POST | `/predict/club-status` | Predicts `club_member_status` (ACTIVE / PRE-CREATE / LEFT CLUB) + probabilities |
| POST | `/predict/segment` | Predicts the K-Means cluster (0 to 5) |
| POST | `/predict/spend` | Predicts `total_spend` (estimated total spend) |

Example call:
```bash
curl -X POST http://localhost:8500/predict/club-status \
  -H "Content-Type: application/json" \
  -d '{"age": 34, "n_transactions": 27, "tenure_days": 540, "n_distinct_categories": 6,
       "avg_basket_value": 42.5, "purchase_frequency_per_month": 1.8, "recency_days": 12}'
```

### Model loading strategy
1. **MLflow Model Registry**, via the `champion` alias (`models:/<name>@champion`), if
   `MLFLOW_TRACKING_URI` points to a reachable MLflow server.
2. **Automatic local fallback** to `ml/models/<task>/*.joblib` otherwise (dev machine without
   MLflow running, or first deployment before the Registry is fully configured — including
   artifacts placed directly by the notebook export cells, §3.0).

This lets the API be developed and tested without permanently depending on a live MLflow server.
Each response's `model_version` field indicates which source was used (`"registry:champion"` or
`"local"`), useful for debugging and monitoring dashboards.

**Important**: `ml/serving/app.py` serves already-trained models (`ml/models/` or the Registry) —
it only queries PostgreSQL at training time (`ml/training/`) or monitoring time
(`ml/monitoring/`), never at inference time. The features needed for a prediction are provided in
the HTTP request body by the caller (typically `backend/app/`, which will itself have read them
from PostgreSQL or computed them on the fly).

### Docker
```bash
docker build -t hm-ml-serving ml/
docker run -p 8500:8500 -e MLFLOW_TRACKING_URI=http://mlflow:5000 hm-ml-serving
```
Or, in the full stack: `./run.sh ml` (starts `mlflow` + `ml-serving`, both added to
`docker-compose.yml`, with `POSTGRES_HOST=postgres` set automatically for `ml-serving`).

### Integration with `backend/app/`
The application backend (FastAPI/Node, to be developed) should simply call these 3 endpoints over
internal HTTP (`http://ml-serving:8500/predict/...` on the `shop_data_net` Docker network), never
loading a model itself: this keeps the responsibility for loading/versioning models entirely
inside `ml/`.

---

## 6. Drift monitoring — Evidently AI

### Why
Customer behavior evolves (seasonality, sales, new segments): a model trained on a snapshot of the
data degrades over time (*data drift* / *concept drift*). Evidently AI compares a reference window
(training data) to a current window and quantifies drift column by column.

### Generating a report
```bash
# Reference = a sample of customers_features_train (PostgreSQL) at run time.
# Without --current: simulates a "current" window with intentional drift (aging customer base,
# lower purchase frequency) for demonstration purposes.
python ml/monitoring/drift_report.py

# With a real extract of more recent data (e.g. re-export of customers_features_train after a new
# run of the Spark pipeline on updated Kaggle data):
python ml/monitoring/drift_report.py --current data/processed/customers_recent.csv
```
The HTML report is generated at `ml/monitoring/reports/drift_report.html` (can be opened in a
browser) and a summary (share of drifting columns, alert if above the threshold defined in
`ml/config.yaml` → `monitoring.drift_share_threshold`) is printed to the console — usable as a
trigger condition for automatic retraining in CI (§7).

### Current limitation tied to the batch nature of the Spark pipeline
The Kaggle H&M dataset is a fixed historical snapshot: `spark/jobs/pipeline_hm.py` replays it in
batch mode (`mode("overwrite")`, the whole table is recomputed on every run), there is no real
Kafka stream actually wired in yet that would make `customers_features_train` evolve continuously
(see `kafka/producers/` and `kafka/consumers/`, still to be implemented). As long as this
real-time flow doesn't exist, "reference" and "current" come from the same batch run — monitoring
today works in exploratory/simulated mode (`--current` parameter), not yet on a genuinely evolving
data flow.

---

## 7. CI/CD — `.github/workflows/mlops-ci.yml`

Three jobs:

1. **`lint-and-test`** (on every push/PR touching `ml/`): `ruff check` then `pytest ml/tests/`.
   Tests run against the synthetic fallback dataset (`ml/common.py`), so **no PostgreSQL database
   is needed in CI** — they validate that the pipeline (features → preprocessing → training →
   tracking → serving) stays runnable end to end, not the models' predictive quality.

2. **`build-serving-image`** (on push to `main`, after tests succeed): builds the `ml/serving/`
   Docker image. Publishing to an image registry (GHCR, Docker Hub…) is pre-written as a comment,
   to be enabled once the target registry is chosen.

3. **`scheduled-retrain`** (weekly cron + manual trigger): generates the drift report and
   retrains/registers the 3 models in the MLflow Model Registry, **reading
   `customers_features_train` from a PostgreSQL instance reachable from the runner**. A standard
   GitHub-hosted runner cannot reach a `docker-compose` stack running locally on a laptop: this job
   assumes either a **self-hosted** runner on the same network as the stack, or a staging/prod
   PostgreSQL/MLflow instance exposed with dedicated credentials in secrets. It stays "best effort"
   as long as these secrets aren't configured (automatic fallback to synthetic data, same as
   locally).

### GitHub secrets to configure (Settings → Secrets and variables → Actions)
| Secret | Used for |
|---|---|
| `MLFLOW_TRACKING_URI` | Points scheduled retraining to the production MLflow server |
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Reads `customers_features_train` from the production/staging PostgreSQL instance |
| `DAGSHUB_USER` / `DAGSHUB_TOKEN` | `dvc pull` of the versioned raw CSVs from DagsHub (optional, see §8) |

---

## 8. Raw data versioning — DVC + DagsHub (reduced scope)

DVC in this project **does not version the features** (they live in PostgreSQL, not in a file):
its scope is limited to the **raw Kaggle CSVs** (`data/raw/`), consumed as input by
`spark/jobs/pipeline_hm.py`.

```bash
# Once (already done in this repo, see .dvc/):
dvc init

# Declare the DagsHub remote (already pre-filled in .dvc/config, to adapt):
dvc remote modify dagshub url https://dagshub.com/<user>/HM-Retail-Intelligence-platform.dvc
dvc remote modify dagshub --local auth basic
dvc remote modify dagshub --local user <your_dagshub_user>
dvc remote modify dagshub --local password <your_dagshub_token>

# Version the raw Kaggle CSVs
dvc add data/raw/customers.csv data/raw/articles.csv data/raw/transactions_train.csv
git add data/raw/*.dvc .gitignore
git commit -m "Version the raw Kaggle data (DVC)"
dvc push
```

`dvc.yaml` declares the training stages (`train_classification`, `train_regression`,
`train_clustering`, `drift_report`) with the **code** as a dependency (scripts, `common.py`,
`config.yaml`) — not the Postgres table, which DVC can't track like a file. In practice, `dvc
repro` replays a training run if the code changes, but **does not** detect a change in
`customers_features_train`'s content (a new run of the Spark pipeline). To force a retrain after a
data update, use `dvc repro --force`, or trigger the stages explicitly (n8n, scheduled CI) after
the Spark job — see the comment at the top of `dvc.yaml`.

---

## 9. Quick start (summary)

**Option A — direct path (recommended if you have the Kaggle data):** run notebooks 01 → 07 in
order (`notebooks/README.md`). The export cells in 06 and 07 automatically drop the 3 models into
`ml/models/`. Jump straight to step 4 below.

**Option B — full Spark → PostgreSQL → scripts pipeline (recommended for the real-time
platform):**

```bash
# 0. Python dependencies + infrastructure
pip install -r ml/requirements.txt
cp .env.example .env
./run.sh infra                  # starts kafka, postgres, adminer, qdrant, n8n, mlflow

# 1. Place the Kaggle CSVs in data/raw/, then run the Spark pipeline
docker exec shop-spark-worker \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
  /opt/spark/work-dir/jobs/pipeline_hm.py

# 2. Train the 3 models (reads customers_features_train from PostgreSQL)
python ml/training/train_classification.py --register
python ml/training/train_regression.py --register
python ml/training/train_clustering.py --register

# 3. Promote the selected versions (after review in the MLflow UI at http://localhost:5000)
mlflow models set-alias hm-club-status-classifier champion 1
mlflow models set-alias hm-spend-regressor champion 1
mlflow models set-alias hm-customer-segmentation champion 1
```

**Then, in both cases:**

```bash
# 4. Start the inference API
uvicorn ml.serving.app:app --reload --port 8500
# -> http://localhost:8500/docs

# 5. Generate a drift report
python ml/monitoring/drift_report.py

# 6. Run the tests
pytest ml/tests/ -v
ruff check ml/ --exclude ml/models
```

---

## 10. Current limitations & next steps

- **Two data paths not unified**: the notebooks (§3.0) read Kaggle CSVs directly, while the
  `ml/training/` scripts (§3.1) read the PostgreSQL table produced by Spark. Both apply the same
  cleaning/age bins (verified column by column), but remain two independent runs — no guarantee
  they run on exactly the same data snapshot at a given moment.
- **No strict temporal split yet** for training (inherited from the notebooks, see
  `notebooks/README.md` §3): to fix before a real move to production (train on the past, validate
  on a more recent window, to avoid temporal information leakage).
- **`spark/jobs/pipeline_hm.py` is a batch job** (`mode("overwrite")`, everything is recomputed on
  every run): no real Kafka stream actually wired in as of today (`kafka/producers/` and
  `kafka/consumers/` are still placeholders) — drift monitoring (§6) therefore runs in
  exploratory/simulated mode for lack of a real-time stream continuously feeding
  `customers_features_train`.
- **The notebook path (§3.0) doesn't log anything to MLflow**: it writes the files directly to
  `ml/models/`, without going through experiment tracking or the Model Registry (no run
  comparison, no associated `champion` alias). For full traceability, either rerun `python
  ml/training/train_*.py --register` afterward with the same data, or log the exported model
  manually via `mlflow.sklearn.log_model()` in an additional cell.
- **The DagsHub DVC remote** in `.dvc/config` is a template (`<user>`) to be replaced with the
  project's real DagsHub repo.
- **Docker image publishing** (`build-serving-image`) isn't wired to a real registry — the lines
  are pre-written as comments in the workflow, to be enabled with a registry and secrets chosen by
  the team.
- ~~Predictive quality tests (minimum thresholds before `--register`) not automated~~ —
  **resolved**: `ml/training/training_api.py` (`POST /train/<task>` and `/train/all`) now applies
  an absolute, per-task quality threshold (`QUALITY_GATES`: `f1_macro ≥ 0.20`, `r2_log_target ≥
  0.50`, `silhouette_score ≥ 0.10`) that blocks any `champion` promotion below it — including when
  there is no current champion — then compares against the existing champion via the MLflow API
  before promoting. Tested independently in `ml/tests/test_training_api.py`. This endpoint is
  called by the `hm-reentrainement-hebdomadaire.json` n8n workflow (see
  `n8n/workflows/README.md`). Still to be tuned: the thresholds are intentionally low starting
  values (block a clearly broken model, not require beating the notebooks' score) — to be
  tightened once a run history is available in production.