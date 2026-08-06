# Streaming Pipeline — H&M

<p align="center">
  <a href="./README.md"><strong>🇬🇧 English</strong></a> ·
  <a href="./README.fr.md">🇫🇷 Français</a>
</p>

This README explains the **real-time** pipeline in detail: what each file does, how it fits
together with Docker, and why it works differently from the batch pipeline.

If you've never touched this folder before, read section 1 (Batch vs Streaming) first before the
rest — it's the key to understanding why this code is written the way it is.

This file covers only real-time ingestion, up to the write into `stream_transactions_ingested`.
What happens **after** that (periodic merge into the Data Warehouse, nightly RFM recomputation,
model call) is orchestrated by n8n and detailed in the [main README, section
6](../README.md#6-n8n-orchestration--full-cycle) — see also section 9 below for the link between
the two.

---

## 1. Batch vs Streaming — two entirely different ways of working

A batch pipeline and a streaming pipeline don't work the same way.

### 1.1 Batch pipeline (`spark/batch_ml_pipeline/`)

The batch pipeline processes data **in batches**.

Example:
- Day 1 → a new CSV file arrives → n8n launches `spark-submit`.
- Spark processes the file then **stops**.
- Day 2 → another file arrives → n8n **relaunches** `spark-submit`.
- Spark processes the new file then stops again.

For every new batch of data, **n8n has to restart the Spark job**.

### 1.2 Streaming pipeline (`spark/streaming_pipeline/`)

The streaming pipeline works differently.

At startup:
- n8n (or Docker) launches the Spark Structured Streaming job **once**.
- After that, this job **keeps running forever**.

While it runs, Spark continuously listens to the Kafka topic. As soon as Kafka receives new
messages:
- Spark detects them automatically.
- It processes them in a micro-batch (e.g. every 30 seconds).
- Then it waits for the next messages.
- It never stops.

So n8n **doesn't need to relaunch Spark** every time new data arrives — unlike batch.

### 1.3 Summary

| | Batch | Streaming |
|---|---|---|
| Trigger | n8n relaunches `spark-submit` for every new file | Launched once by Docker Compose (`restart: unless-stopped`) |
| Job lifetime | Ends after each run | Never ends |
| Detecting new data | Waits to be relaunched | Continuously listens to Kafka, reacts automatically |
| PostgreSQL write | `mode("overwrite")` — recreates the table | `mode("append")` — adds without ever erasing |
| n8n's role | Active orchestrator (relaunches the job) | Simple startup notifier (the job already runs on its own) — n8n then takes back over downstream, at regular intervals, to merge and use the produced data (see section 9) |

---

## 2. The Dockerfile

The streaming pipeline uses the **same Spark Docker image** as the batch pipeline (a single
`Dockerfile`, at the project root) — no image duplication. The only difference is the **command**
launched when the container starts (see docker-compose below) and one extra Spark package needed
to read Kafka:

```
--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1
```

This package isn't installed in the image at build time: it's downloaded by Spark when the job
launches, via `spark-submit`'s `--packages` option. It's the connector that lets
`spark.readStream.format("kafka")` work.

---

## 3. The service in `docker-compose.yml`

```yaml
  spark-streaming-job:
    build:
      context: ./spark
    container_name: shop-spark-streaming
    restart: unless-stopped
    depends_on:
      - kafka
      - spark-master
    command: >
      /opt/spark/bin/spark-submit
      --master spark://spark-master:7077
      --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1
      /opt/spark/work-dir/streaming_pipeline/jobs/streaming_job.py
    env_file:
      - .env
    volumes:
      - ./data:/opt/spark/work-dir/data
      - ./spark/common:/opt/spark/work-dir/common
      - ./spark/streaming_pipeline:/opt/spark/work-dir/streaming_pipeline
      - streaming_checkpoint:/opt/spark/work-dir/checkpoint
    networks:
      - shop_data_net
```

**Key points of this configuration:**

- `restart: unless-stopped`: if the container crashes or the machine reboots, Docker restarts it
  automatically — essential for a process meant to run permanently.
- `depends_on: kafka, spark-master`: the job needs Kafka and the Spark cluster to already be
  running.
- The `streaming_checkpoint` volume (also to be declared in the root `volumes:` section of
  `docker-compose.yml`) is **essential**: it's where Spark records its progress (which Kafka
  messages have already been processed). Without this persistent volume, a container restart
  would lose this progress and either reprocess or skip data.
- It's a container **separate** from `spark-master`/`spark-worker`: those stay dedicated to batch,
  so the two workloads don't mix.

---

## 4. `spark/common/config.py` — shared configuration

| Function | Role |
|---|---|
| `get_spark_session(app_name)` | Creates the `SparkSession`, connected to the cluster (`spark://spark-master:7077`), with the PostgreSQL JDBC driver loaded. |
| `get_jdbc_config()` | Returns the JDBC URL (`jdbc:postgresql://postgres:5432/...`) and connection credentials. |
| `get_kafka_config()` | Returns Kafka's internal Docker address (`kafka:29092` — **not** `localhost:9092`, which is only valid from the host machine) and the topic name (`transactions.raw`, read from `.env`). |

---

## 5. `spark/streaming_pipeline/utils/validation.py`

This is the data's entry gate: every Kafka message passes through this file before being
considered usable.

### File overview diagram

```
Kafka
   │
   ▼
Raw JSON message
   │
   ▼
parse_kafka_messages()
   │
   ▼
DataFrame with Spark columns
   │
   ▼
split_valid_invalid()
      │
      ├──────────────► valid_df
      │                  │
      │                  ▼
      │        Streaming Pipeline
      │        (join + write)
      │
      ▼
rejected_df
      │
      ▼
Dead Letter Queue / Rejects table
```

### The two functions

**`parse_kafka_messages(raw_stream_df)`**
Kafka always delivers its content (`value`) as raw binary — Spark doesn't yet know that this
binary is JSON representing a transaction. This function:
1. Converts `value` into a string (`CAST(value AS STRING)`).
2. Parses this JSON string against `kafka_message_schema` (defined at the top of the file) via
   `from_json()`.
3. "Explodes" the result into normal Spark columns (`t_dat`, `customer_id`, `article_id`, `price`,
   `sales_channel_id`), also keeping `kafka_timestamp` (the message's arrival time, useful for
   debugging or traceability).

**`split_valid_invalid(parsed_df)`**
A real-time stream is never guaranteed to be clean — unlike the batch's fixed Kaggle dataset, a
Kafka message can be corrupted, incomplete, or sent by a buggy producer. This function:
1. Defines an `is_valid` condition (no required field missing, strictly positive price, date
   present).
2. Returns **two** separate DataFrames: `valid_df` (usable transactions, with the date already
   converted to `Date` type) and `rejected_df` (everything else, with a `rejection_reason` column
   added).

**Why split instead of silently filtering?** If we just dropped invalid messages
(`filter(is_valid)` without keeping the other branch), we'd lose all visibility into producer or
stream problems — a bug invalidating 30% of messages would go unnoticed. By keeping `rejected_df`
and writing it to a dedicated table (`stream_transactions_rejected`, see below), we get a true
**Dead Letter Queue**: rejected data stays available for investigation, without ever blocking the
main stream's processing.

---

## 6. `spark/streaming_pipeline/jobs/streaming_job.py` — the conductor

This is the main script, the one launched by `spark-submit` in `docker-compose.yml`. It chains, in
order:

1. **Loading the static dimensions** (`customers_static`, `articles_static`) — once, at startup.
2. **Reading the Kafka stream** (`spark.readStream.format("kafka")...load()`), with
   `startingOffsets: "latest"` — when the job (re)starts, it does **not** reread the topic's whole
   history (otherwise every restart would reinject thousands of already-processed transactions).
3. **Validation** (`parse_kafka_messages` + `split_valid_invalid`, see section 5).
4. **Continuous writing**, via two functions called on every micro-batch (`foreachBatch`):
   - `write_batch_to_postgres` → writes the valid transactions
   - to `stream_transactions_ingested` (`append` mode).
   - `write_rejected_to_postgres` → writes invalid messages to
     `stream_transactions_rejected` (`append` mode).
5. **`spark.streams.awaitAnyTermination()`**: keeps the script alive indefinitely, as long as
   neither streaming query stops — this is the line that makes the job "never stop" (section 1.2).

**Why a `stream_transactions_ingested` table separate from the batch Data Warehouse
(`fact_transaction`)?** To never put the Data Warehouse already validated by the batch pipeline at
risk. A streaming job, by nature less controlled than a batch run on fixed data, writes to its own
landing table. Merging the two is handled separately, by a dedicated job
(`merge_stream_to_warehouse.py`) outside this pipeline — see section 9.

**Why a different `checkpointLocation` for `valid` and `rejected`?** Each streaming query
(`writeStream`) has its own progress to track independently — mixing the two streams' checkpoints
in the same folder would create offset-tracking conflicts.

---

## 7. File locations — summary

```
spark/
├── common/
│   ├── config.py            ← section 4
│   └── schemas.py           ← transactions/customers/articles schemas
└── streaming_pipeline/
    ├── README.md             ← this file
    ├── jobs/
    │   └── streaming_job.py  ← section 6
    └── utils/
        └── validation.py     ← section 5
```

---

## 9. What happens next? The rest of the cycle (outside this folder)

`stream_transactions_ingested` isn't a final destination — it's a landing table, consumed
periodically by separate **batch** jobs, orchestrated by n8n:

### Daily batch pipeline run

Every night at **02:00**, two batch processes run in a precise order to synchronize the data and
update the Data Marts.

- **`merge_stream_to_warehouse.py`** (`spark/batch_ml_pipeline/jobs/`):
  This job fetches the transactions validated by the streaming pipeline and merges them into the
  Data Warehouse's central `fact_transaction` table. The merge is done in **append** mode with a
  **watermark** mechanism to avoid duplicates and only process new transactions since the last
  run.

- **`pipeline_hm.py --source=warehouse`** (`spark/batch_ml_pipeline/jobs/`):
  After the Data Warehouse update, this job recomputes the various **Data Marts** (customer RFM,
  product popularity, business statistics, etc.) from the `fact_transaction` table. The
  computations take into account all available data, including the historical transactions from
  the CSV files as well as the new transactions merged in from streaming.

The execution order is therefore:

1. **02:00:** run `merge_stream_to_warehouse.py` to merge new streaming transactions into
   `fact_transaction`.
2. **After the merge:** run `pipeline_hm.py --source=warehouse` to recompute the aggregates and
   update the Data Marts.

The streaming pipeline runs continuously throughout the day (Kafka → Spark Structured Streaming →
storage of validated transactions), while the consolidation/analysis batch jobs run once per
night.

These two jobs are triggered by n8n via `spark/job_trigger_api.py` (the same principle as
`producer_api.py` for Kafka, but for `spark-submit`). Full detail of the cycle, diagram, and
frequency table: [main README, section 6](../README.md#6-n8n-orchestration--full-cycle).