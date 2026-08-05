# H&M Retail Intelligence Platform

<p align="center">
  <a href="./README.md">🇫🇷 Français</a> ·
  <a href="./README.en.md"><strong>🇬🇧 English</strong></a>
</p>

Data & AI platform built around the Kaggle **H&M Personalized Fashion Recommendations** dataset.
This README describes **only what is actually implemented and functional today**, with a clear
explanation of how it works. Unimplemented pieces are listed separately at the end, without being
presented as operational.

---

## 1. What is implemented, and how it works

### 1.1 Overview of the real data flow

```
data/raw/*.csv (Kaggle: customers, articles, transactions)
        │
        ▼  spark-submit pipeline_hm.py
   PostgreSQL — star schema + Data Marts
   (key table: customers_features_train)
        │
        ▼  ml/training/train_*.py --register
   MLflow — experiment tracking + Model Registry ("champion" alias)
        │
        ▼  models:/<name>@champion  (or local fallback ml/models/*.joblib)
   ml/serving/app.py — FastAPI inference API (/predict/*)
        │
        ▼
   ml/monitoring/drift_report.py — drift report (Evidently AI)

In parallel, independently of this real-time flow:
notebooks/01→07 — full EDA + ML pipeline on a CSV snapshot of the same data
```

This diagram is deliberately shorter than what one might imagine for a full "retail
intelligence" platform: it only shows what actually runs today.

### 1.2 The analytics pipeline — `notebooks/`

**What it is**: a series of 7 Jupyter notebooks, already executed on the real Kaggle data
(results, charts, and scores already visible in the `.ipynb` files, nothing needs to be re-run).

**How it works**: each notebook reads the Kaggle CSVs (`data/raw/`) or the objects produced by
the previous notebook (`intermediate/` folder, generated at execution time, not versioned),
applies one pipeline step (cleaning, EDA, enrichment, feature engineering, modeling), then
exports its results for the next notebook. Notebooks 06 and 07 also export the selected models
directly (`joblib.dump`) to `ml/models/`.

**Full detail**: [`notebooks/README.md`](./notebooks/README.md) (execution order, usage) and
[`notebooks/DETAILS.md`](./notebooks/DETAILS.md) (methodology).

### 1.3 The Big Data pipeline — `spark/`

**What it is**: a batch Spark job that turns the 3 raw Kaggle CSVs into a ready-to-use
PostgreSQL Data Warehouse.

**How it works**: `spark/jobs/pipeline_hm.py` reads `data/raw/*.csv`, applies cleaning
(`spark/utils/cleaning.py`: median/mode imputation, age buckets), computes RFM customer
features (`spark/utils/features.py`: recency, frequency, monetary value, purchase diversity),
and writes everything via JDBC into PostgreSQL as a star schema and Data Marts — including the
`customers_features_train` table, which is **the single source of truth** consumed downstream
by `ml/`.

**Run it**:
```bash
docker exec shop-spark-worker \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
  /opt/spark/work-dir/jobs/pipeline_hm.py
```

**Full detail**: [`spark/README.md`](./spark/README.md).

### 1.4 Model training, tracking, and serving — `ml/`

**What it is**: the 3 models validated in notebooks 06-07 (club status classification, total
spend regression, customer segmentation), replayed in a scripted, industrialized way.

**How it works**, step by step:
1. `ml/training/train_classification.py`, `train_regression.py`, `train_clustering.py` load
   `customers_features_train` from PostgreSQL (`ml/common.py`), or automatically fall back to a
   synthetic dataset with the same schema if the table is empty/unreachable (useful in CI).
2. Each script reproduces exactly the recipe validated in the notebooks (same hyperparameters,
   same feature selection), trains the model, and logs to **MLflow** (parameters, metrics,
   model) — with `--register` to also register it in the **Model Registry**.
3. `ml/serving/app.py` (FastAPI API) loads the model tagged with the `champion` alias from the
   Registry, or failing that a local copy in `ml/models/`, and exposes 3 single-record prediction
   routes (`/predict/club-status`, `/predict/segment`, `/predict/spend`), a batch-scoring route
   (`/predict/batch` — scores an entire Postgres table and returns an aggregated summary, used by
   the `hm-rfm-nocturne-notifications` n8n workflow, see §1.5), plus `/health`.
4. `ml/monitoring/drift_report.py` compares a reference window and a current window of
   `customers_features_train` (Evidently AI) and generates an HTML drift report.
5. `.github/workflows/mlops-ci.yml` runs lint + tests on every push, builds the inference
   service's Docker image on `main`, and can retrain/monitor drift on a weekly cron.

**Full detail, with all commands**: [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) — the most
detailed document in the repo, read this first for anything ML-related.

### 1.5 The streaming pipeline & orchestration — `kafka/` + `n8n/`

**What it is**: a second flow, independent of the batch flow described in §1.3, that ingests
transactions in near real time via Kafka, plus 3 n8n workflows that schedule the whole pipeline
(batch + streaming + retraining).

**How it works**:
1. `kafka/producers/transactions_producer.py` (exposed via `kafka/producers/producer_api.py`,
   port `8090`) reads a daily CSV (`data/raw/daily/`, generated by
   `data/raw/daily/generator_api.py`) and publishes each transaction to the Kafka topic
   `transactions.raw`.
2. `spark/streaming_pipeline/jobs/streaming_job.py` continuously consumes this topic, validates
   each message, and writes valid/rejected rows into PostgreSQL (`stream_transactions_ingested` /
   `stream_transactions_rejected`).
3. `spark/batch_ml_pipeline/jobs/merge_stream_to_warehouse.py` then merges this streaming data
   into the warehouse (`fact_transaction`, `dim_date`), using a watermark to process only new
   rows.
4. Three n8n workflows orchestrate all of this, now **split into 3 independent files** in
   [`n8n/workflows/`](./n8n/workflows/):
   - [`hm-simulation-quotidienne-kafka.json`](./n8n/workflows/hm-simulation-quotidienne-kafka.json)
     — generates the day's transactions and triggers the Kafka producer (every day at 06:00).
   - [`hm-rfm-nocturne-notifications.json`](./n8n/workflows/hm-rfm-nocturne-notifications.json)
     — merges streaming data into the warehouse, recomputes RFM, generates a summary via Ollama,
     and broadcasts it (every day at 02:00).
   - [`hm-reentrainement-hebdomadaire.json`](./n8n/workflows/hm-reentrainement-hebdomadaire.json)
     — retrains the 3 ML models and reloads `ml-serving` (every Monday at 06:00).

   Full detail of every node: [`n8n/workflows/README.md`](./n8n/workflows/README.md).

**Important — what is NOT wired up in this flow**: the `hm-rfm-nocturne-notifications` workflow
calls endpoints (`Push SSE → Django`, `Envoyer au Chatbot`, `Envoyer FCM`) that point to a
Django backend, a chatbot, and an FCM service that are **absent from this repository** — these
are integrations planned for another project (`ShopAnalytics`), not code that exists here.
Similarly, `ollama` (used to generate the text summary) and `qdrant` (vector database) start via
Docker, but only `ollama` is actually called by this workflow; `qdrant` receives no data
anywhere in the current repo.

### 1.6 Docker infrastructure — `docker-compose.yml`

**What it is**: the orchestration of all containers needed for the implemented parts above (plus
a few infrastructure pieces that are ready but not yet wired to application code, see §2).

**Services supporting an implemented, functional part**:

| Service | Actual role today |
|---|---|
| `postgres` | Stores the Data Warehouse produced by `spark/jobs/pipeline_hm.py`, including `customers_features_train` |
| `adminer` | Web interface to browse PostgreSQL (`http://localhost:8081`) |
| `spark-master` / `spark-worker` | Run `spark/jobs/pipeline_hm.py` |
| `mlflow` | Tracking server + Model Registry for `ml/training/` and `ml/serving/` |
| `ml-serving` | Runs the FastAPI API from `ml/serving/app.py` in a container |

**Minimal startup for the implemented flow** (without the services not yet wired to code):
```bash
cp .env.example .env        # fill in real values
docker compose up -d postgres adminer spark-master spark-worker mlflow ml-serving
```

**Full startup of the repo's infrastructure** (also includes the services listed in §2, present
in `docker-compose.yml` but not yet consumed by application code):
```bash
./run.sh all                # or run.bat all on Windows
./run.sh status              # check that the containers are running
```

### 1.7 Summary: quick start for the actually implemented flow

```bash
# 0. Configuration
cp .env.example .env

# 1. Infrastructure needed for the implemented flow
docker compose up -d postgres adminer spark-master spark-worker mlflow ml-serving

# 2. Place the 3 Kaggle CSVs in data/raw/, then run the Spark pipeline
docker exec shop-spark-worker \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
  /opt/spark/work-dir/jobs/pipeline_hm.py

# 3. Train and register the 3 models
python ml/training/train_classification.py --register
python ml/training/train_regression.py --register
python ml/training/train_clustering.py --register

# 4. Start/check the inference API
uvicorn ml.serving.app:app --reload --port 8500   # http://localhost:8500/docs

# 5. Generate a drift report
python ml/monitoring/drift_report.py
```

Full detail of every command: [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) §9.

**View notebook results without running anything**: opening any `.ipynb` in
[`notebooks/`](./notebooks/) directly shows its already computed results (charts, tables,
scores) — no execution needed to view them.

---

## 2. What is NOT implemented today

These elements exist in the repo as folders/ready Docker images, but **contain no functional
logic** — they are placeholders (`.gitkeep`), not operational features:

| Folder / service | Actual state |
|---|---|
| `kafka/consumers/` | Empty folder (the real "consumer" is the Spark job `spark/streaming_pipeline/jobs/streaming_job.py`, see §1.5) — nothing to add here unless a standalone Kafka consumer is needed. |
| `backend/app/` | Empty folder. No application API exists between a frontend and the data/models. |
| `frontend/src/` | Empty folder. No user interface (dashboard) exists. |
| RAG chatbot (`ollama` + `qdrant`) | The Docker services start. `ollama` is actually called by the `hm-rfm-nocturne-notifications` n8n workflow (text summary generation), but `qdrant` receives no data: no ingestion, no collection created, no vector search wired to a frontend. Notebook 04 prepares data that *could* feed this RAG, but no code currently wires it in. |
| n8n nodes `Push SSE → Django`, `Envoyer au Chatbot`, `Envoyer FCM` | Present in `hm-rfm-nocturne-notifications.json`, but point to a Django backend, a chatbot, and an FCM service that don't exist in this repo (integrations planned for the `ShopAnalytics` project). |
| `.env.example` | Missing from the repo, even though `docker-compose.yml` and this README rely on it (`cp .env.example .env`). Needs to be created before the first startup. |
| `data/processed/`, `data/features/` | Folders inherited from an earlier pipeline version, not fed by the current code. |
| DVC/DagsHub remote | `.dvc/config` contains a URL template, not yet pointed to a real DagsHub repo. |

**Why document them anyway?** So that no one wastes time looking for code that doesn't exist,
and so the next person picking up the project knows exactly where to start if they want to build
out one of these pieces.

---

## 3. Repository layout

```
hm-retail-intelligence-platform/
├── README.md / README.en.md     # this file (FR / EN)
├── ARCHITECTURE.md              # detailed technical diagram, Docker services
├── docker-compose.yml           # orchestration of all services
├── .env.example                  # environment variables to copy into .env
├── run.sh / run.bat              # startup scripts
│
├── notebooks/                    # ✅ implemented — EDA → ML pipeline (see §1.2)
├── data/raw/                     # ✅ used — raw Kaggle CSVs
├── data/processed/, data/features/  # ❌ not used by current code
├── spark/                        # ✅ implemented — batch pipeline → PostgreSQL (see §1.3)
│                                  #    + streaming pipeline (see §1.5)
├── ml/                            # ✅ implemented — training, MLflow, API, monitoring (see §1.4)
├── kafka/                         # ✅ implemented — producer + API (see §1.5); consumers/ empty (§2)
├── n8n/workflows/                 # ✅ implemented — 3 separate workflows (see §1.5)
│   ├── hm-simulation-quotidienne-kafka.json
│   ├── hm-rfm-nocturne-notifications.json
│   └── hm-reentrainement-hebdomadaire.json
├── backend/app/                   # 📂 reserved — empty
└── frontend/src/                  # 📂 reserved — empty
```

---

## 4. Further documentation

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — full technical diagram, exact role of each Docker
  service, implemented / not implemented distinction.
- [`spark/README.md`](./spark/README.md) — Spark → PostgreSQL pipeline in detail (star schema,
  Data Marts, running the job).
- [`n8n/workflows/README.md`](./n8n/workflows/README.md) — detail of the 3 n8n workflows (nodes,
  triggers, services called, known limitations).
- [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) — full ML/MLOps guide: training, MLflow, serving
  API, monitoring, CI/CD, DVC.
- [`notebooks/README.md`](./notebooks/README.md) — notebook execution order, usage.
- [`notebooks/DETAILS.md`](./notebooks/DETAILS.md) — detailed statistical methodology.