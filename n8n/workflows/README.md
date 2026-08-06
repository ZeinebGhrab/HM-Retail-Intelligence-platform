# n8n workflows — H&M Retail Intelligence Platform

<p align="center">
  <a href="./README.md"><strong>🇬🇧 English</strong></a> ·
  <a href="./README.fr.md">🇫🇷 Français</a>
</p>

Orchestration of the H&M data pipeline: synthetic transaction generation, Kafka/Spark ingestion,
nightly RFM computation, LLM report generation (Ollama), **weekly ML model retraining**, and
multi-channel broadcasting (SSE, chatbot, push notifications).

> Note: node names shown below (e.g. `Déclencheur - Simulation quotidienne`) are kept exactly as
> they appear inside the n8n JSON files, since they are literal node identifiers, not prose.

## Files

These three loops were originally a single workflow (`HM Streaming Pipeline.json`). They are now
**split into 3 independent files**, importable separately into n8n, since they have no execution
dependency on each other (independent triggers, schedules, and failure modes):

| File | Loop | Trigger | Role |
|---|---|---|---|
| [`hm-simulation-quotidienne-kafka.json`](./hm-simulation-quotidienne-kafka.json) | **Daily streaming** | Every day at **06:00** | Generates synthetic transactions, publishes them to Kafka, triggers the Spark streaming job |
| [`hm-rfm-nocturne-notifications.json`](./hm-rfm-nocturne-notifications.json) | **Nightly RFM** | Every day at **02:00** | Merges streaming data into the warehouse, recomputes RFM scores, generates an AI report and broadcasts it to customers (dashboard, chatbot, notifications) |
| [`hm-reentrainement-hebdomadaire.json`](./hm-reentrainement-hebdomadaire.json) | **Weekly ML retraining** | Every **Monday at 06:00** (same cadence as `mlops-ci.yml`) | Retrains the 3 models (`ml/training/train_*.py`), automatically promotes the new MLflow champion if it's better, reloads `ml-serving`'s cache, and notifies |

Each file is a valid, self-contained n8n export (clean `nodes` + `connections`), to be imported
individually via *Import from File* in n8n.

## Workflow architecture

```
06:00 ─┬─ Daily simulation trigger
       │
       ├─ Compute simulated date (Code)
       │
       ├─ Generate the day's transactions (HTTP → generator_api:8089)
       │
       ├─ Trigger the Kafka producer (HTTP → kafka-producer-api:8090)
       │
       └─ spark_pipeline_streaming


02:00 ─┬─ Nightly RFM trigger
       │
       ├─ Run merge_stream_to_warehouse.py (HTTP → spark-job-trigger:8091)
       │
       ├─ Run pipeline_hm.py --source=warehouse (HTTP → spark-job-trigger:8091)
       │
       ├─ Wait for the RFM recomputation to finish (Wait)
       │
       ├─ Call the prediction model API (HTTP → ml-model-api:8000)
       │
       ├─ Prepare Ollama prompt (Code)
       │
       ├─ Basic LLM Chain (Ollama Model: llama3.2:3b-instruct-q4_K_M)
       │
       ├─ Format SSE payload (Code)
       │
       └─┬─ Push SSE → Django (real-time dashboard)
         ├─ Send to Chatbot (RAG Django)
         └─ Send FCM (mobile push notification)


Monday 06:00 ─┬─ Weekly retraining trigger
              │
              ├─ Trigger retraining of the 3 models (HTTP → ml-training-trigger:8600/train/all)
              │
              ├─ Analyze training results (Code — compares against thresholds/current champion)
              │
              ├─ Reload models (HTTP → ml-serving:8500/admin/reload-models)
              │
              └─ Notify FCM - retraining finished (HTTP → shopanalytics-django-api:8000)
```

## Triggers

| Node | Type | Cron | Description |
|---|---|---|---|
| `Déclencheur - Simulation quotidienne` | Schedule Trigger | `0 6 * * *` | Starts the generation/streaming loop every day at 6am |
| `Déclencheur - RFM nocturne (02:00)` | Schedule Trigger | `0 2 * * *` | Starts the merge + RFM computation + AI report loop every night at 2am |
| `Déclencheur - Ré-entraînement hebdomadaire (lundi 06:00)` | Schedule Trigger | `0 6 * * 1` | Starts the ML retraining loop every Monday at 6am (same cadence as the `scheduled-retrain` cron in `.github/workflows/mlops-ci.yml`, but here for the local Docker stack) |

## ML retraining loop (new)

1. **Trigger retraining of the 3 models** — `POST http://ml-training-trigger:8600/train/all?register=true&promote=true`.
   Internally calls `ml/training/train_classification.py`, `train_regression.py`, and
   `train_clustering.py` (no duplicated logic), logs each run to MLflow, then compares the new
   run's key metric (`f1_macro`, `rmse`, `silhouette_score` depending on the task) against the
   current `champion` alias. The new model is only promoted to `champion` if it's better than or
   equal to the current one — this is the anti-regression safeguard described as missing in
   `ml/MLOPS_GUIDE.md` §10.
2. **Analyze training results** (Code) — builds a readable summary (which model was promoted, with
   which metric) and an `any_promoted` flag.
3. **Reload models** — `POST http://ml-serving:8500/admin/reload-models`. Required because the
   inference API caches models in memory on first call; without this cache flush, a new champion
   would only be picked up after the `ml-serving` container restarts.
4. **Notify FCM** — reuses the `shopanalytics-django-api:8000/api/send-fcm/` endpoint already used
   by the nightly RFM loop, with a `type: "model_retrain"` payload.

If one of the 3 trainings fails, `ml-training-trigger` returns an HTTP 500 status with per-task
detail: the corresponding n8n HTTP Request node then fails, and the workflow stops before reloading
`ml-serving` or sending a notification (intended behavior — no partial/incorrect reload).

## External services called

| Service | Port | Role |
|---|---|---|
| `generator_api` | 8089 | Generates the day's synthetic transactions |
| `kafka-producer-api` | 8090 | Publishes transactions to Kafka |
| `shop-streaming-api` | 8000 | Spark Structured Streaming job |
| `spark-job-trigger` | 8091 | Triggers batch jobs (warehouse merge, RFM computation) |
| `ml-serving` | 8500 | Inference API (`ml/serving/app.py`); exposes `/predict/club-status`, `/predict/segment`, `/predict/spend`, **`/predict/batch`**, and `POST /admin/reload-models` |
| `ml-training-trigger` | 8600 | Triggers retraining and MLflow champion auto-promotion (`ml/training/training_api.py`) |
| `shopanalytics-django-api` | 8000 | Django backend: SSE, RAG chatbot, FCM notifications |

## Batch scoring for the AI report — `POST /predict/batch`

The `Appeler l'API modèle (prédiction batch)` node (nightly RFM loop) now calls
`POST http://ml-serving:8500/predict/batch` (`ml/serving/app.py`), **implemented and tested**
(`ml/tests/test_serving.py::test_predict_batch_*`), which didn't exist before (the previous
version pointed to a nonexistent `ml-model-api:8000` service and stayed disabled).

Request body (`source_table` and `limit` optional):
```json
{"source_table": "customers_features_train"}
```

Response: an aggregated summary (`BatchPredictionSummary`), not row-by-row predictions — designed
to be fed directly into the following Ollama prompt (`Préparer Prompt Ollama`, updated accordingly
to consume these fields instead of the foot-traffic forecast fields from another project):

```json
{
  "generated_at": "2026-08-05T02:03:11.123Z",
  "source_table": "customers_features_train",
  "n_customers_scored": 5000,
  "club_status_distribution": {"ACTIVE": 3421, "PRE-CREATE": 1102, "LEFT CLUB": 477},
  "dominant_club_status": "ACTIVE",
  "segment_distribution": {"0": 812, "1": 950, "2": 703, "3": 890, "4": 845, "5": 800},
  "dominant_segment": 1,
  "predicted_spend_mean": 187.42,
  "predicted_spend_median": 152.10,
  "predicted_spend_total": 937100.0,
  "model_versions": {"classification": "registry:champion", "clustering": "local", "regression": "local"}
}
```

**Remaining known limitation (out of scope for this fix)**: the following node `Push SSE →
Django` (as well as `Envoyer au Chatbot`, `Envoyer FCM`) still points to a Django backend absent
from this repository (see `README.md` §2, the `ShopAnalytics` project). `Formater Payload SSE`
therefore produces a correctly formed payload from real H&M data, but the HTTP call consuming it
will fail until a Django backend is deployed at the configured URL.

## Quality gate for automatic champion promotion

Contrary to what an earlier version of this page stated, automatic promotion of the `champion`
alias **is not** a simple comparison against the previous champion: `ml/training/training_api.py`
first applies an **absolute, per-task quality threshold** (`QUALITY_GATES`), which blocks any
promotion if the new model falls below it — including when there is no champion yet, or when the
current champion is worse (two cases a purely relative comparison would miss):

| Task | Metric | Minimum threshold |
|---|---|---|
| `classification` | `f1_macro` | 0.20 |
| `regression` | `r2_log_target` | 0.50 |
| `clustering` | `silhouette_score` | 0.10 |

Only once this threshold is cleared is the metric compared against the current champion (read via
the MLflow API), and promotion only happens if the new version is better than or equal to it. This
behavior is covered by `ml/tests/test_training_api.py` (the safeguard is tested independently of
any real training run or network access to MLflow/PostgreSQL, using fake training functions).