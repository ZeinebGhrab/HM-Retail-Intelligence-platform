<div align="center">

# 🛍️ H&M Retail Intelligence Platform

**A data & AI platform built around the Kaggle H&M Personalized Fashion Recommendations dataset —
Big Data pipeline, MLOps, real-time streaming, and orchestration.**

<p align="center">
  <a href="./README.md"><strong>🇬🇧 English</strong></a> ·
  <a href="./README.fr.md">🇫🇷 Français</a>
</p>

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)]()
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)]()
[![Apache Spark](https://img.shields.io/badge/Apache%20Spark-Batch%20%2B%20Streaming-E25A1C?logo=apachespark&logoColor=white)]()
[![Kafka](https://img.shields.io/badge/Kafka-Event%20Streaming-231F20?logo=apachekafka&logoColor=white)]()
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Data%20Warehouse-4169E1?logo=postgresql&logoColor=white)]()
[![MLflow](https://img.shields.io/badge/MLflow-Tracking%20%2B%20Registry-0194E2?logo=mlflow&logoColor=white)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-Serving%20API-009688?logo=fastapi&logoColor=white)]()
[![XGBoost](https://img.shields.io/badge/ML-XGBoost%20%7C%20RandomForest%20%7C%20KMeans-orange)]()
[![n8n](https://img.shields.io/badge/n8n-Orchestration-EA4B71?logo=n8n&logoColor=white)]()
[![Grafana](https://img.shields.io/badge/Grafana-Dashboards-F46800?logo=grafana&logoColor=white)]()
[![DVC](https://img.shields.io/badge/DVC-Data%20Versioning-13ADC7?logo=dvc&logoColor=white)]()
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)]()
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)]()
[![License](https://img.shields.io/badge/license-Proprietary-lightgrey.svg)]()
[![Stars](https://img.shields.io/github/stars/ZeinebGhrab/HM-Retail-Intelligence-platform?style=social)]()
[![Forks](https://img.shields.io/github/forks/ZeinebGhrab/HM-Retail-Intelligence-platform?style=social)]()

</div>

---

> This README describes **only what is actually implemented and functional today**, with a clear
> explanation of how each piece works. Unimplemented pieces are listed separately in [§9](#9-whats-not-implemented-yet),
> without ever being presented as operational.

## 📑 Table of contents

- [1. Overview](#1-overview)
  - [1.1 What this platform does](#11-what-this-platform-does)
  - [1.2 End-to-end data flow](#12-end-to-end-data-flow)
- [2. Analytics pipeline — `notebooks/`](#2-analytics-pipeline--notebooks)
- [3. Big Data pipeline — `spark/`](#3-big-data-pipeline--spark)
- [4. MLOps — training, tracking & serving — `ml/`](#4-mlops--training-tracking--serving--ml)
- [5. Real-time streaming & orchestration — `kafka/` + `n8n/`](#5-real-time-streaming--orchestration--kafka--n8n)
- [6. Dashboards — `grafana/`](#6-dashboards--grafana)
- [7. RAG Chatbot — `backend/app/` + `frontend/`](#7-rag-chatbot--backendapp--frontend)
- [8. Docker infrastructure](#8-docker-infrastructure)
- [9. What's not implemented yet](#9-whats-not-implemented-yet)
- [10. Quick start](#10-quick-start)
- [11. Repository layout](#11-repository-layout)
- [12. Further documentation](#12-further-documentation)

---

## 1. Overview

### 1.1 What this platform does

| Capability | Implemented by |
|---|---|
| 📊 Deep exploratory analysis & statistically-justified data cleaning | `notebooks/` |
| 🏗️ Batch Big Data pipeline → PostgreSQL Data Warehouse (star schema + Data Marts) | `spark/batch_ml_pipeline/` |
| ⚡ Near real-time transaction ingestion | `kafka/` + `spark/streaming_pipeline/` |
| 🤖 Model training, experiment tracking & registry | `ml/training/` + MLflow |
| 🚀 Inference API (single & batch prediction) | `ml/serving/` (FastAPI) |
| 📈 Drift monitoring | `ml/monitoring/` (Evidently AI) |
| 🕹️ Scheduling & orchestration of the whole cycle | `n8n/workflows/` |
| 📊 Business & ML dashboards | `grafana/` |
| 💬 Client-specific RAG chatbot (Ollama, tool-calling) + web UI | `backend/app/` + `frontend/` |
| ✅ CI/CD (lint, tests, image build, scheduled retraining) | `.github/workflows/mlops-ci.yml` |

### 1.2 End-to-end data flow

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
        │
        ▼
   grafana/ — business & ML dashboards (reads PostgreSQL)

In parallel, independently of this batch flow:
notebooks/01→07 — full EDA + ML pipeline on a CSV snapshot of the same data
kafka/ + spark/streaming_pipeline/ — near real-time transaction ingestion, merged nightly
n8n/workflows/ — schedules simulation, RFM recomputation, and weekly retraining
backend/app/ + frontend/ — RAG chatbot (Ollama) over PostgreSQL + ml-serving, web UI with Grafana
```

This diagram is deliberately shorter than what one might imagine for a full "retail intelligence"
platform: it only shows what actually runs today. Every arrow above corresponds to a section
below with the exact command to run it.

---

## 2. Analytics pipeline — `notebooks/`

**What it is**: a series of 7 Jupyter notebooks, already executed on the real Kaggle data
(results, charts, and scores already visible in the `.ipynb` files — nothing needs to be re-run to
view them).

**How it works**: each notebook reads the Kaggle CSVs (`data/raw/`) or the objects produced by the
previous notebook (`intermediate/` folder, generated at execution time, not versioned), applies
one pipeline step (cleaning, EDA, enrichment, feature engineering, modeling), then exports its
results for the next notebook. Notebooks 06 and 07 also export the selected models directly
(`joblib.dump`) to `ml/models/`.

| # | Notebook | Content |
|---|---|---|
| 01 | `01_EDA_Nettoyage_Clients.ipynb` | Cleaning of `customers.csv`, customer EDA |
| 02 | `02_EDA_Produits_Transactions.ipynb` | Products EDA, chunked pass over 33.7M transactions |
| 03 | `03_RFM_Enrichissement_Externe.ipynb` | RFM analysis, weather & public-holiday enrichment |
| 04 | `04_FeatureEngineering_Soldes_RAG.ipynb` | Customer feature table, RAG knowledge-base export |
| 05 | `05_ML_ReductionDim_Clustering_Rapide.ipynb` | PCA, t-SNE/UMAP, exploratory K-Means |
| 06 | `06_ML_Classification_Regression.ipynb` | Club-status classification, spend regression |
| 07 | `07_ML_Clustering_Approfondi_Synthese.ipynb` | In-depth clustering (k=6), ML summary |

📖 **Full detail**: [`notebooks/README.md`](./notebooks/README.md) (execution order, usage) and
[`notebooks/DETAILS.md`](./notebooks/DETAILS.md) (statistical methodology, formulas, results).

---

## 3. Big Data pipeline — `spark/`

**What it is**: a batch Spark job that turns the 3 raw Kaggle CSVs into a ready-to-use PostgreSQL
Data Warehouse.

**How it works**: `spark/jobs/pipeline_hm.py` reads `data/raw/*.csv`, applies cleaning
(`spark/utils/cleaning.py`: median/mode imputation, age buckets), computes RFM customer features
(`spark/utils/features.py`: recency, frequency, monetary value, purchase diversity), and writes
everything via JDBC into PostgreSQL as a star schema and Data Marts — including the
`customers_features_train` table, which is **the single source of truth** consumed downstream by
`ml/`.

**Run it**:
```bash
docker exec shop-spark-worker \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
  /opt/spark/work-dir/jobs/pipeline_hm.py
```

📖 **Full detail**: [`spark/README.md`](./spark/README.md) (batch pipeline, streaming pipeline,
n8n orchestration overview).

---

## 4. MLOps — training, tracking & serving — `ml/`

**What it is**: the 3 models validated in notebooks 06-07 (club-status classification, total-spend
regression, customer segmentation), replayed in a scripted, industrialized way.

**How it works**, step by step:

| Step | Component | Role |
|---|---|---|
| 1 | `ml/training/train_*.py` | Loads `customers_features_train` from PostgreSQL (with a synthetic fallback for CI), reproduces the exact recipe validated in the notebooks, trains, and logs to MLflow |
| 2 | MLflow (`--register`) | Experiment tracking (params, metrics, artifacts) + Model Registry, promotion via the `champion` alias |
| 3 | `ml/serving/app.py` (FastAPI) | Loads the `champion` model (Registry, or local fallback in `ml/models/`), exposes `/predict/club-status`, `/predict/segment`, `/predict/spend`, `/predict/batch`, `/health` |
| 4 | `ml/monitoring/drift_report.py` | Compares a reference and a current window of `customers_features_train` (Evidently AI), generates an HTML drift report |
| 5 | `.github/workflows/mlops-ci.yml` | Lint + tests on every push, Docker image build on `main`, weekly retrain/monitor cron |

**Models & scores** (from notebooks 06-07, reproduced exactly by the training scripts):

| Task | Model | Metric |
|---|---|---:|
| `club_member_status` classification | Random Forest (tuned) | F1-macro = 0.3889 |
| `total_spend` regression | XGBoost | R² (test) = 0.943 |
| Customer segmentation | K-Means (k=6) | Silhouette = 0.2537 |

📖 **Full detail, with all commands**: [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) — the most
detailed document in the repo, read this first for anything ML-related.

---

## 5. Real-time streaming & orchestration — `kafka/` + `n8n/`

**What it is**: a second flow, independent of the batch flow described in §3, that ingests
transactions in near real time via Kafka, plus 3 n8n workflows that schedule the whole pipeline
(batch + streaming + retraining).

**How it works**:

1. `kafka/producers/transactions_producer.py` (exposed via `kafka/producers/producer_api.py`, port
   `8090`) reads a daily CSV (`data/raw/daily/`) and publishes each transaction to the Kafka topic
   `transactions.raw`.
2. `spark/streaming_pipeline/jobs/streaming_job.py` continuously consumes this topic, validates
   each message, and writes valid/rejected rows into PostgreSQL (`stream_transactions_ingested` /
   `stream_transactions_rejected`).
3. `spark/batch_ml_pipeline/jobs/merge_stream_to_warehouse.py` merges this streaming data into the
   warehouse (`fact_transaction`, `dim_date`), using a watermark to process only new rows.
4. Three n8n workflows orchestrate all of this, split into independent files in
   [`n8n/workflows/`](./n8n/workflows/):

| Workflow | Trigger | Role |
|---|---|---|
| [`hm-simulation-quotidienne-kafka.json`](./n8n/workflows/hm-simulation-quotidienne-kafka.json) | Daily 06:00 | Generates the day's transactions, triggers the Kafka producer |
| [`hm-rfm-nocturne-notifications.json`](./n8n/workflows/hm-rfm-nocturne-notifications.json) | Daily 02:00 | Merges streaming into the warehouse, recomputes RFM, generates a summary via Ollama, broadcasts it |
| [`hm-reentrainement-hebdomadaire.json`](./n8n/workflows/hm-reentrainement-hebdomadaire.json) | Monday 06:00 | Retrains the 3 ML models, promotes the champion, reloads `ml-serving` |

> ⚠️ **Known limitation**: the `hm-rfm-nocturne-notifications` workflow calls endpoints (`Push
> SSE → Django`, `Envoyer au Chatbot`, `Envoyer FCM`) that point to a Django backend, a chatbot,
> and an FCM service **absent from this repository** — planned integrations for another project
> (`ShopAnalytics`), not code that exists here.

📖 **Full detail of every node**: [`n8n/workflows/README.md`](./n8n/workflows/README.md).

---

## 6. Dashboards — `grafana/`

**What it is**: 5 Grafana dashboards (25 panels total), reading directly from the PostgreSQL Data
Warehouse and Data Marts — sales overview, product analytics, customer analytics, segmentation,
and daily performance.

**How it works**: `grafana/provisioning/datasources/postgres.yml` auto-configures the PostgreSQL
connection on startup — no manual setup needed in the UI. Every panel is a plain SQL query against
`fact_transaction`, `dim_customer`, `dim_article`, `daily_sales`, `products_performance`, or
`customer_segments_summary`.

```bash
docker compose up -d grafana
# → http://localhost:3001  (admin / hm_admin)
```

📖 **Full detail**: [`grafana/README.md`](./grafana/README.md) (setup) and
[`grafana/README_GRAFANA.md`](./grafana/README_GRAFANA.md) (all 25 panels with their SQL queries).

---

## 7. RAG Chatbot — `backend/app/` + `frontend/`

**What it is**: a chatbot that answers questions about a specific H&M customer (profile, purchase
history, behavioral segment) or general platform questions, using a local Ollama LLM with
tool-calling — plus a web frontend combining the Grafana dashboards (§6) with a resizable chat
panel.

**Model**: chosen via [`backend/benchmark/`](./backend/benchmark/README.md), which scores several
Ollama models on tool-calling accuracy and resistance to hallucination. Winner:
`qwen2.5:3b-instruct-q4_K_M`.

**How it works**: two Ollama calls per question (`backend/app/rag_pipeline.py`) — first the LLM
picks a tool from a fixed list (customer profile, purchase history, behavioral-cluster prediction,
hypothetical spend/status prediction, or semantic search over a small knowledge base), the backend
runs that tool in Python (Postgres first, CSV fallback), then a second Ollama call turns the tool's
result into a natural-language answer. If a tool has nothing to return, it signals that explicitly
(`backend/app/tool_signals.py`) instead of leaving the LLM to guess.

```bash
docker compose up -d ollama chatbot-app     # → http://localhost:8601 (see CHATBOT_APP_PORT in .env)
cd frontend && npm install && npm run dev   # → http://localhost:5173
```

📖 **Full detail**: [`backend/app/README.md`](./backend/app/README.md) (all tools, data sources,
API contract) and [`frontend/README.md`](./frontend/README.md) (dashboard + chat panel UI).

---

## 8. Docker infrastructure

**What it is**: the orchestration of all containers needed for the implemented parts above (plus a
few infrastructure pieces that are ready but not yet wired to application code, see §9).

**Services supporting an implemented, functional part**:

| Service | Actual role today |
|---|---|
| `postgres` | Stores the Data Warehouse produced by `spark/jobs/pipeline_hm.py`, including `customers_features_train` |
| `adminer` | Web interface to browse PostgreSQL (`http://localhost:8081`) |
| `spark-master` / `spark-worker` | Run the batch and streaming Spark jobs |
| `mlflow` | Tracking server + Model Registry for `ml/training/` and `ml/serving/` |
| `ml-serving` | Runs the FastAPI API from `ml/serving/app.py` in a container |
| `grafana` | Business & ML dashboards (§6) |
| `n8n` | Orchestrates the batch/streaming/retraining cycle (§5) |
| `kafka` | Event broker for near real-time ingestion (§5) |
| `ollama` | Local LLM used by the chatbot (§7) and by the nightly n8n summary node (§5) |
| `chatbot-app` | Runs the FastAPI RAG chatbot from `backend/app/` (§7) |
| `qdrant` | Started for experimentation only — production `semantic_search` (§7) uses in-memory cosine similarity, not Qdrant (see `backend/app/experiments/qdrant_poc.py`) |
| `ml-training-trigger` | Retraining/promotion API (`ml/training/training_api.py`), triggered by the weekly n8n workflow (§5) |

**Minimal startup for the implemented flow** (without the services not yet wired to code):
```bash
cp .env.example .env        # fill in real values
docker compose up -d postgres adminer spark-master spark-worker mlflow ml-serving
```

**Full startup of the repo's infrastructure**:
```bash
./run.sh all                # or run.bat all on Windows
./run.sh status              # check that the containers are running
```

---

## 9. What's not implemented yet

These elements exist in the repo as folders/ready Docker images, but **contain no functional
logic** — they are placeholders (`.gitkeep`), not operational features:

| Folder / service | Actual state |
|---|---|
| `kafka/consumers/` | Empty folder (the real "consumer" is the Spark job `spark/streaming_pipeline/jobs/streaming_job.py`, see §5) — nothing to add here unless a standalone Kafka consumer is needed. |
| n8n nodes `Push SSE → Django`, `Envoyer au Chatbot`, `Envoyer FCM` | Present in `hm-rfm-nocturne-notifications.json`, but still point to the old Django backend and Ionic chatbot (not `backend/app/` + `frontend/`, see §7) and an FCM service, none of which exist in this repo. |
| `data/processed/`, `data/features/` | Folders inherited from an earlier pipeline version, not fed by the current code. |
| DVC/DagsHub remote | `.dvc/config` contains a URL template, not yet pointed to a real DagsHub repo. |

**Why document them anyway?** So that no one wastes time looking for code that doesn't exist, and
so the next person picking up the project knows exactly where to start if they want to build out
one of these pieces.

---

## 10. Quick start

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

# 6. (optional) Dashboards
docker compose up -d grafana                        # http://localhost:3001

# 7. (optional) RAG chatbot + web UI
docker compose up -d ollama chatbot-app             # http://localhost:8601
cd frontend && npm install && npm run dev           # http://localhost:5173
```

📖 Full detail of every command: [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) §9.

**View notebook results without running anything**: opening any `.ipynb` in
[`notebooks/`](./notebooks/) directly shows its already computed results (charts, tables,
scores) — no execution needed to view them.

---

## 11. Repository layout

```
hm-retail-intelligence-platform/
├── README.md / README.fr.md      # this file (EN / FR)
├── ARCHITECTURE.md               # detailed technical diagram, Docker services
├── docker-compose.yml            # orchestration of all services
├── .env.example                   # environment variables to copy into .env
├── run.sh / run.bat               # startup scripts
│
├── notebooks/                     # ✅ implemented — EDA → ML pipeline (§2)
├── data/raw/                      # ✅ used — raw Kaggle CSVs
├── data/processed/, data/features/  # ❌ not used by current code
├── spark/                         # ✅ implemented — batch pipeline → PostgreSQL (§3)
│                                   #    + streaming pipeline (§5)
├── ml/                             # ✅ implemented — training, MLflow, API, monitoring (§4)
├── kafka/                          # ✅ implemented — producer + API (§5); consumers/ empty (§9)
├── n8n/workflows/                  # ✅ implemented — 3 separate workflows (§5)
│   ├── hm-simulation-quotidienne-kafka.json
│   ├── hm-rfm-nocturne-notifications.json
│   └── hm-reentrainement-hebdomadaire.json
├── grafana/                        # ✅ implemented — 5 dashboards, 25 panels (§6)
├── backend/app/                    # ✅ implemented — RAG chatbot API (§7)
├── backend/benchmark/               # ✅ implemented — LLM benchmark used to pick the chatbot model (§7)
└── frontend/                        # ✅ implemented — dashboard + chat panel web UI (§7)
```

---

## 12. Further documentation

| Document | Content |
|---|---|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Full technical diagram, exact role of each Docker service, implemented / not implemented distinction |
| [`spark/README.md`](./spark/README.md) | Spark → PostgreSQL pipeline in detail (star schema, Data Marts, running the job, n8n orchestration overview) |
| [`spark/batch_ml_pipeline/README.md`](./spark/batch_ml_pipeline/README.md) | Batch pipeline internals: JDBC write, star schema, Data Marts, troubleshooting |
| [`spark/streaming_pipeline/README.md`](./spark/streaming_pipeline/README.md) | Streaming pipeline internals: Kafka ingestion, validation, checkpointing |
| [`n8n/workflows/README.md`](./n8n/workflows/README.md) | Detail of the 3 n8n workflows (nodes, triggers, services called, known limitations) |
| [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) | Full ML/MLOps guide: training, MLflow, serving API, monitoring, CI/CD, DVC |
| [`grafana/README.md`](./grafana/README.md) | Grafana setup, provisioning, troubleshooting |
| [`grafana/README_GRAFANA.md`](./grafana/README_GRAFANA.md) | All 25 dashboard panels with their SQL queries |
| [`kafka/README.md`](./kafka/README.md) | Kafka producer & API detail |
| [`backend/app/README.md`](./backend/app/README.md) | RAG chatbot: tools, data sources, API contract |
| [`backend/benchmark/README.md`](./backend/benchmark/README.md) | LLM benchmark methodology and results (model selection for the chatbot) |
| [`frontend/README.md`](./frontend/README.md) | Dashboard + chat panel web UI |
| [`notebooks/README.md`](./notebooks/README.md) | Notebook execution order, usage |
| [`notebooks/DETAILS.md`](./notebooks/DETAILS.md) | Detailed statistical methodology, formulas, full results |