# H&M Big Data Pipeline — Spark, PostgreSQL & Data Warehouse

<p align="center">
  <a href="./README.md"><strong>🇬🇧 English</strong></a> ·
  <a href="./README.fr.md">🇫🇷 Français</a>
</p>

Batch data pipeline that transforms the raw CSV files from the **H&M (Kaggle)** dataset into a
structured **PostgreSQL Data Warehouse** (star schema) and ready-to-use **Data Marts** for Machine
Learning, a dashboard, and a RAG / LLM system.

Everything runs in **Docker Compose**, with **Apache Spark** as the processing engine and
**PostgreSQL** as the final storage database, connected via the **JDBC** protocol.

---

## 1. Flow overview

```
CSV (Kaggle H&M)
      │
      ▼
Apache Spark  ──────►  PostgreSQL JDBC Driver
      │                        │
      ▼                        ▼
Cleaning + Features    ──►  PostgreSQL (Data Warehouse)
      │                        │
      ▼                        ▼
Star Schema            Data Marts (ML · Dashboard · RAG)
```

---

## 2. Why Spark writes to PostgreSQL via JDBC (and not psycopg2)

- `psycopg2` (present in `requirements.txt`) is only used by pure **Python** code.
- **Spark runs on the JVM (Java)** — it doesn't know `psycopg2`.
- When the code calls `df.write.jdbc(...)`, it's **Spark (Java)** that writes to PostgreSQL, not
  Python. It therefore needs a **Java JDBC driver**.

```
PySpark script → Spark DataFrame API → Spark Engine (Java) → PostgreSQL JDBC Driver → PostgreSQL
```

---

## 3. Shared configuration: the `.env` file

```
POSTGRES_PORT=5432
POSTGRES_DB=hm_retail
POSTGRES_USER=hm_admin
POSTGRES_PASSWORD=change_me
```

The Spark container only sees these variables if `.env` is mounted or declared as `env_file` on
**all** Spark services (`spark-master` **and** `spark-worker`) — not just on `postgres`.

---

## 4. Project structure and role of each file

| File | Role |
|---|---|
| `config.py` | Centralizes the creation of the `SparkSession` (`get_spark_session()`) and the JDBC connection configuration (`get_jdbc_config()`). |
| `schemas.py` | Explicitly defines the schema (column types) of the `transactions`, `customers`, `articles` CSV files — no cleaning here. |
| `cleaning.py` | Reproduces the cleaning done in the EDA notebook: imputation, date conversion, age-bin creation. |
| `features.py` | Computes the RFM and enriched per-customer features, builds the business aggregation tables, then the Data Warehouse (dimensions + facts) and the Data Marts. |

### 4.1 `config.py`

`get_spark_session()` creates the `SparkSession`, names it (`appName("hm_pipeline")`), points it
to the cluster (`master("spark://spark-master:7077")`), and loads the JDBC driver.
`get_jdbc_config()` returns the JDBC URL and credentials, avoiding repeating them in every script.

> **Spark Master vs Spark Worker, in short**: the **Master** coordinates the cluster (receives
> submitted jobs, knows the list of available workers, distributes the work) — it doesn't run any
> computation itself. The **Worker** actually executes the tasks (reading CSVs, joins,
> aggregations) with the resources it has declared to the Master. `spark-submit` can be launched
> from any container with network access to the Master and the job's files — including from the
> `spark-worker` container itself (see section 9).

### 4.2 `schemas.py`

Defines an explicit schema (`StructType`) rather than `inferSchema=True`, for performance,
type-reliability, and reproducibility reasons. Every column of `customers.csv` is read,
**including `FN` and `Active`**, with its original type.

### 4.3 `cleaning.py`

| Function | Treatment |
|---|---|
| `clean_customers()` | Explicitly drops `FN` and `Active` (`.drop("FN", "Active")`) — a `NaN` in these columns means a genuine absence of subscription according to the EDA, not a value to impute. Age imputed with the **median** (`approxQuantile`); club status and newsletter frequency imputed with the **mode**; age-bin creation (`age_group`). |
| `clean_articles()` | No imputation (0.4% missing values on `detail_desc`, judged negligible). |
| `clean_transactions()` | Converts `t_dat` to `Date` type, no filtering or deduplication. |

Making this call in `cleaning.py` rather than at read time (`schemas.py`) makes the cleaning
decision explicit and traceable, at the right place in the pipeline.

### 4.4 `features.py`

**Per-customer RFM features**: `total_spend` (Monetary), `n_transactions` (Frequency),
`recency_days` from `DATASET_END = "2020-09-22"` (fixed date, historical dataset) (Recency),
`tenure_days`, `avg_basket_value`, `purchase_frequency_per_month`, `n_distinct_categories`.

`segment_valeur`: `total_spend` quartile segmentation via **`approxQuantile`** — see section 11
for the detail of the change from `ntile()`.

---

## 5. The Data Warehouse — star schema

```
              Dim Customer
                    │
Dim Date ─── Fact Transaction ─── Dim Article
```

| Table | Content |
|---|---|
| `dim_customer` | Descriptive customer info; `customer_key` generated via `crc32` hash. |
| `dim_article` | Descriptive product info; `article_key = article_id` (already a unique integer). |
| `dim_date` | One row per distinct date, with a readable `date_key` (`2020-09-22 → 20200922`). |
| `fact_transaction` | One row per purchase: keys to the dimensions + measures (`price`, `sales_channel_id`). |

---

## 6. Where the Data Marts sit in the star schema

The classic star schema has two levels: dimensions and the fact, at the finest grain. The Data
Marts form a **third level**: precomputed aggregates, one notch above the fact.

**Classic core — fine grain (1 row = 1 transaction)**: `dim_customer`, `dim_article`, `dim_date`,
`fact_transaction`.

**Data Marts — aggregated grain**:
- `customers_features_train` — 1 row = 1 customer
- `products_performance` — 1 row = 1 article
- `daily_sales` — 1 row = 1 day
- `customer_segments_summary` — 1 row = 1 segment

The marts are computed from `fact_transaction`, then stored alongside it, in the same database —
they replace neither the dimensions nor the fact.

### What are the Data Marts actually for?

Without a mart, every business question would require scanning and recomputing over 33.7 million
rows on every call.

| Without a Data Mart | With a Data Mart |
|---|---|
| Scan 33.7M rows on every query | Read 1 row already ready in the mart |
| Redo a `groupBy` + aggregation on every call | No recomputation, data already summarized |
| Every team rewrites its own query | A single shared reference table |

Instead of Django or the ML team recomputing RFM by scanning 33.7M rows on every call, they read
`customers_features_train` directly — one row per customer, already ready, up to date on every run
(`mode("overwrite")`).

---

## 7. Final write to PostgreSQL

```python
for name, df in tables.items():
    df.write.mode("overwrite").jdbc(
        url=jdbc_url,
        table=name,
        properties=jdbc_props
    )
```

`overwrite` mode entirely recreates each table on every run of the batch pipeline.

---

## 8. Technology stack

- **Docker / Docker Compose** — service orchestration.
- **Apache Spark (PySpark)** — distributed processing, cleaning, feature engineering.
- **PostgreSQL** — final storage for the Data Warehouse and Data Marts.
- **JDBC** (`postgresql-42.7.3.jar`) — communication bridge between Spark (JVM) and PostgreSQL.
- **Adminer** — web interface to browse the database (see section 10).

---

## 9. Running the pipeline

```bash
# 1. Start the infrastructure
docker compose up -d

# 2. Run the Spark job — launched from the worker container,
#    connected to the master via its internal network URL
docker exec shop-spark-worker `
  /opt/spark/bin/spark-submit `
  --master spark://spark-master:7077 `
  /opt/spark/work-dir/batch_ml_pipeline/jobs/pipeline_hm.py

docker exec shop-spark-worker /opt/spark/bin/spark-submit --master spark://spark-master:7077 /opt/spark/work-dir/batch_ml_pipeline/jobs/pipeline_hm.py
```
At the end of the run, 8 tables are available in PostgreSQL: `dim_customer`, `dim_article`,
`dim_date`, `fact_transaction`, `customers_features_train`, `products_performance`,
`daily_sales`, `customer_segments_summary`.

### 9.1 Viewing the Spark Master UI

| URL | Description |
|---|---|
| `http://localhost:8080` | Spark Master web UI (`SPARK_MASTER_WEBUI_PORT`, see `.env`) — list of connected workers, running (`Running Applications`) and completed jobs, per-executor logs. |
| `spark://spark-master:7077` | The Spark protocol port itself (`SPARK_MASTER_PORT`) — **not** a browser URL, used only by `spark-submit` and the workers to connect to the cluster. |

The submitted job appears in the UI's `Running Applications` list as soon as it starts, then moves
to `Completed Applications` once done.

### 9.2 Common troubleshooting (Docker Desktop / Windows)

| Symptom | Cause | Fix |
|---|---|---|
| `container ... is not running` on `docker exec shop-spark-worker ...` | `spark-worker` (and/or `spark-master`) stopped between two Docker Desktop sessions | `docker compose up -d spark-master spark-worker` (or `docker compose up -d` to restart everything at once) |
| `Bind for 0.0.0.0:XXXX failed: port is already allocated` | A project port (e.g. `6333`, `8080`) is already used by **another** active Docker project on the machine | `docker ps` to identify the conflicting container, then `docker stop <name>` — or change the conflicting port in `.env` |
| `UnknownHostException: spark-master: ... Temporary failure in name resolution` in `docker logs shop-spark-master` | Docker's internal DNS (service-name resolution, e.g. `spark-master`) is in an inconsistent state — common after many containers/networks have been active simultaneously | `docker compose down` (removes the `shop_data_net` network) → `wsl --shutdown` (admin PowerShell) → reopen Docker Desktop → `docker compose up -d` |
| `localhost:8080` unreachable even though `docker ps` shows `shop-spark-master` as `Up` | **Another** Docker project is already using port 8080 (e.g. another project's phpMyAdmin) | Check `docker ps` to spot the container actually holding the port, stop it, then restart `spark-master` |

---

## 10. Viewing the Data Warehouse via Adminer

**Adminer** is a lightweight web interface (the phpMyAdmin equivalent, but natively
PostgreSQL-compatible) to browse the tables without a terminal.

Add to `docker-compose.yml`, **inside** `services:`:

```yaml
  adminer:
    image: adminer:latest
    container_name: shop-adminer
    restart: unless-stopped
    ports:
      - "8081:8080"
    networks:
      - shop_data_net
```

Start it:
```bash
docker compose up -d adminer
```

Access: `http://localhost:8081`, then log in with:

| Field | Value |
|---|---|
| System | PostgreSQL |
| Server | `postgres` (Docker service name, not `localhost`) |
| Username | `hm_admin` |
| Password | `POSTGRES_PASSWORD`'s value |
| Database | `hm_retail` |

---

## 11. Why `ntile()` was replaced with `approxQuantile`

`Window.orderBy("total_spend")` + `ntile(4)` requires a global sort of the whole column on **a
single partition** (`WARN WindowExec: No Partition Defined`), which pushed the job from a few
seconds to over 30 minutes on 1.36M customers. `approxQuantile` computes the thresholds
(25th/50th/75th percentile) in a distributed way, without this bottleneck. Consequence: the 4
segments are no longer guaranteed to have strictly equal counts (which `ntile` did), but instead
reflect **real spend thresholds** — more consistent for marketing segmentation, and faster.

