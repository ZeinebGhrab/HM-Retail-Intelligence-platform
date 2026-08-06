# HM Retail Intelligence Platform

<p align="center">
  <a href="./README.md"><strong>🇬🇧 English</strong></a> ·
  <a href="./README.fr.md">🇫🇷 Français</a>
</p>

Data platform for the H&M project: ingestion, cleaning, feature engineering, and storage, with two
complementary processing modes — **batch** (historical) and **streaming** (simulated real-time) —
brought together in a single Data Warehouse and consumed by a prediction API.

Overview of the full cycle, orchestrated by n8n:

```
Kafka (real-time) ──► Spark Streaming ──► stream_transactions_ingested
                                                     │
                                every 15 min │ merge_stream_to_warehouse.py
                                                     ▼
                                            fact_transaction (Data Warehouse)
                                                     │
                                     every night 02:00 │ pipeline_hm.py --source=warehouse
                                                     ▼
                                        Data Marts (RFM, product popularity, ...)
                                                     │
                                                     ▼
                                              Model API (prediction)
```

This README gives the project overview. For the technical detail of the streaming pipeline
(Dockerfile, docker-compose, each file's methods), see
[`spark/streaming_pipeline/README.md`](./streaming_pipeline/README.md). For the detail of the n8n
orchestration (periodic merge, nightly RFM recomputation, model call), see [section
6](#6-n8n-orchestration--full-cycle).

---

## Project tree

```
HM-Retail-Intelligence-Platform/
├── data/
│   └── raw/
│       ├── customers.csv
│       ├── articles.csv
│       ├── transactions_train.csv          ← historical data (batch)
│       └── daily/                          ← real-time stream simulator
│           ├── transactions_2026-07-08.csv
│           ├── transactions_2026-07-09.csv
│           └── transactions_2026-07-10.csv
├── kafka/
│   ├── producers/
│   │   ├── transactions_producer.py
│   │   └── producer_api.py
│   └── consumers/
├── spark/
│   ├── common/
│   │   ├── config.py
│   │   └── schemas.py
│   ├── batch_ml_pipeline/
│   │   ├── jobs/
│   │   │   ├── pipeline_hm.py
│   │   │   └── merge_stream_to_warehouse.py   ← streaming → Data Warehouse merge (new)
│   │   └── utils/
│   │       ├── cleaning.py
│   │       └── features.py
│   ├── streaming_pipeline/
│   │   ├── jobs/
│   │   │   └── streaming_job.py
│   │   └── utils/
│   │       ├── cleaning.py
│   │       └── validation.py
│   ├── job_trigger_api.py                     ← triggers Spark jobs for n8n (new)
│   └── job_trigger.Dockerfile
├── model_api/                                  ← prediction API (new)
│   └── app.py
├── Dockerfile
├── docker-compose.yml
└── .env
```

---

## 1. The `data/` folder

Holds all of the project's data, in two clearly separated categories:

| Subfolder | Content | Used by |
|---|---|---|
| `data/raw/` (root files) | The full, fixed Kaggle H&M dataset (`customers.csv`, `articles.csv`, `transactions_train.csv`, 33.7M rows) | `batch_ml_pipeline` |
| `data/raw/daily/` | **Artificially generated** CSV files, one per day (`transactions_2026-07-08.csv`, etc.), to simulate the real arrival of new transactions | `kafka/producers` (replayed to Kafka) |

`daily/` isn't a copy of the historical dataset: it's a **simulator**. Each file represents what a
real production day would actually send, replayed message by message to Kafka by the producer —
see below.

---

## 2. The `kafka/` folder

| File | Role |
|---|---|
| `producers/transactions_producer.py` | Reads a `daily/transactions_<date>.csv` file and publishes each row as a JSON message on the `transactions.raw` Kafka topic, with a slight delay between each message to simulate a real stream (not an instant dump). |
| `producers/producer_api.py` | Small HTTP server (FastAPI) exposing `POST /produce?date=...` — the entry point n8n calls to trigger the producer, since n8n can't run a Python script directly. |

---

## 3. The `spark/` folder

Contains three subfolders (each with a distinct responsibility) and an orchestration service:

### 3.1 `spark/common/`

Code **shared** between the batch pipeline and the streaming pipeline, to avoid duplication:

| File | Role |
|---|---|
| `config.py` | Creates the `SparkSession` (`get_spark_session()`), the JDBC configuration to PostgreSQL (`get_jdbc_config()`), and the Kafka configuration (`get_kafka_config()`). |
| `schemas.py` | Defines the Spark schemas (`StructType`) of the 3 source files: `transactions_schema`, `customers_schema`, `articles_schema`. Identical for batch and streaming — a single place to edit if the data format changes. |

### 3.2 `spark/batch_ml_pipeline/`

The historical pipeline, with **two distinct jobs**:

| File | Role | Triggered |
|---|---|---|
| `jobs/pipeline_hm.py` | Cleans, joins, computes RFM features, and writes the Data Marts. Accepts a `--source` argument: `csv` (original behavior, reads the raw files — initial load) or `warehouse` (rereads `fact_transaction` already in the database, i.e. CSV **and** streaming merged — see 3.2.1). | On demand (initial load) then every night at 02:00 in `warehouse` mode |
| `jobs/merge_stream_to_warehouse.py` | **New.** Merges transactions already validated by streaming (`stream_transactions_ingested`) into `fact_transaction`, in `append` mode only, never reprocessing the same data twice thanks to a **watermark** (`merge_watermark` table, one row per merge pipeline, updated on every successful run). | Every 15 minutes |

#### 3.2.1 Why merge streaming and batch into `fact_transaction`?

Without a merge, `stream_transactions_ingested` (fed continuously) and `fact_transaction` (loaded
once from the CSVs) stay two isolated tables: the Data Marts, recomputed only from the CSVs, never
see the real-time transactions. `fact_transaction` therefore becomes the single source of truth,
fed by two channels — an initial load from the CSVs, then periodic additions from streaming — and
`pipeline_hm.py --source=warehouse` then recomputes the Data Marts on this combined set rather
than on the raw CSVs alone.

### 3.3 `spark/streaming_pipeline/`

The real-time pipeline: continuously reads the `transactions.raw` Kafka topic, validates and
enriches each message, writes in append mode (`append`) to PostgreSQL
(`stream_transactions_ingested`). Starts once and never stops.

**Full detail of this pipeline (Dockerfile, docker-compose, each file's methods): see
[`spark/streaming_pipeline/README.md`](./streaming_pipeline/README.md).**

### 3.4 `spark/job_trigger_api.py`

**New.** n8n can't run `spark-submit` directly (it's not a Python script it knows how to launch
natively) — this small FastAPI server plays exactly the same role as `producer_api.py` on the
Kafka side, but for batch Spark jobs. It exposes `POST /jobs/{job_name}` (`job_name` =
`merge-stream` or `compute-rfm`) and launches, via `docker exec`, the corresponding `spark-submit`
on the `spark-worker` container.

It runs in its own container (`spark-job-trigger`, see docker-compose below) and is the **only**
service mounting the Docker socket (`/var/run/docker.sock`) — never n8n itself, to limit the
attack surface.

---

## 4. The `model_api/` folder

**New.** Prediction API (FastAPI) that loads the latest trained model and exposes a prediction
endpoint, based on the features computed in the Data Marts (`customers_features_train`, etc.).
It's the last link in the nightly cycle: once the Data Marts are recomputed, n8n calls this API to
refresh the predictions consumed downstream (churn, recommendation, etc.).

---

## 5. Root files

| File | Role |
|---|---|
| `Dockerfile` | Shared Spark image (batch + streaming), with the PostgreSQL JDBC driver. |
| `docker-compose.yml` | Orchestrates all services: Kafka, Zookeeper, PostgreSQL, Spark (master/worker/streaming), **`spark-job-trigger`** (new), **`model-api`** (new), n8n, the producer API, Adminer. |
| `.env` | Shared configuration (PostgreSQL credentials, ports, Kafka topic name) — read by every service. |

---

## 6. n8n orchestration — full cycle

Four n8n workflows cover the entire cycle, from the Kafka message to the prediction:

| # | Step | n8n trigger | Frequency | Calls |
|---|---|---|---|---|
| 1 | Simulate transaction arrivals | Manual or schedule | One-off (test/demo) | `POST /produce?date=...` on `kafka-producer-api` |
| 2 | Streaming ingestion | None (the job already runs continuously, see [`spark/streaming_pipeline/README.md`](./streaming_pipeline/README.md)) | — | — |
| 3 | Streaming → Data Warehouse merge | Schedule Trigger | Every 15 min | `POST /jobs/merge-stream` on `spark-job-trigger` |
| 4 | Recompute the Data Marts (RFM, product popularity, ...) | Schedule Trigger | Every night at 02:00 | `POST /jobs/compute-rfm?source=warehouse` on `spark-job-trigger` |
| 5 | Refresh predictions | Chained after step 4 (same workflow) | Every night at 02:00, right after step 4 | `model-api` |

```
                n8n
                 │
                 │ POST /produce?date=2026-07-08     (step 1, one-off)
                 ▼
        kafka-producer-api (FastAPI) ──► transactions_producer.py ──► Kafka topic: transactions.raw
                                                                              │
                                                                              ▼
                                                          Spark Structured Streaming (step 2, continuous)
                                                          
                                                                              │
                                                                              ▼
                                                          stream_transactions_ingested (PostgreSQL)


                n8n  ── every 15 min ──►  POST /jobs/merge-stream  ──► spark-job-trigger
                                                                                    │
                                                                                    ▼
                                                          merge_stream_to_warehouse.py (spark-submit)
                                                                                    │
                                                                                    ▼
                                                              fact_transaction (Data Warehouse)


                n8n  ── every night 02:00 ──►  POST /jobs/compute-rfm?source=warehouse  ──► spark-job-trigger
                                                                                                    │
                                                                                                    ▼
                                                                  pipeline_hm.py --source=warehouse (spark-submit)
                                                                                                    │
                                                                                                    ▼
                                                                       Data Marts (customers_features_train, ...)
                                                                                                    │
                                                                                                    ▼
                                                                              model-api (refreshes predictions)
```

**Why `spark-job-trigger` and not n8n directly?** n8n has no native node to launch `spark-submit`
(it's not an HTTP binary). As with the Kafka producer (`producer_api.py`, section 2), we go
through a small intermediate FastAPI server that knows how to run the command — see 3.4 for how it
works and where it lives in Docker.

**Why two such different frequencies (15 min vs nightly)?** `merge_stream_to_warehouse.py` is a
simple incremental `append` on new rows only (lightweight, can run often). `pipeline_hm.py
--source=warehouse`, on the other hand, recomputes all the aggregates (RFM, product popularity)
over the entire Data Warehouse — expensive, so it's reserved for a daily run, at night, when load
is low.

---

## 7. API

- **`streaming_api.py`** (next to `spark/streaming_pipeline/`): exposes `POST /streaming`, called
  by n8n to start the continuous Spark Streaming job via `spark-submit` if it isn't already
  running (or simply return its status if it is), with optional `/stop`, `/status`, and `/logs`
  endpoints to control and monitor it manually.
- **`job_trigger_api.py`** (`spark/job_trigger_api.py`): exposes `POST /jobs/{job_name}`, called by
  n8n every night at 02:00, first for `merge-stream` (merging `stream_transactions_ingested` →
  `fact_transaction`) then, right after in the same workflow, for `compute-rfm
  --source=warehouse` (recomputing the Data Marts on the freshly merged warehouse), launching the
  corresponding `spark-submit` via `docker exec` on `shop-spark-worker`, with a 30-minute safety
  timeout.

## 8. Useful commands (manual tests)

```bash
# Manually launch the streaming job (outside n8n), to check it's running correctly:
docker exec -it shop-spark-master bash
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
  /opt/spark/work-dir/spark/streaming_pipeline/jobs/streaming_job.py

# Check that the Kafka topic exists and is receiving messages:
docker exec -it shop-kafka bash
kafka-topics --bootstrap-server kafka:29092 --list
```

```powershell
Invoke-WebRequest `
  -Method POST `
  "http://localhost:8090/produce?date=2026-07-09"
```