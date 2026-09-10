# `kafka/`

<p align="center">
  <a href="./README.md"><strong>🇬🇧 English</strong></a> ·
  <a href="./README.fr.md">🇫🇷 Français</a>
</p>

This folder handles the entry point into the real-time flow: it simulates incoming transactions
and publishes them to Kafka. It does **not** contain a classic Kafka consumer — the topic is
consumed by the **Spark Structured Streaming** job (`spark/streaming_pipeline/jobs/streaming_job.py`),
not by any code here.

```
kafka/
├── consumers/              ← empty (see note below)
├── producers/
│   ├── producer_api.py     ← FastAPI API, entry point called by n8n
│   └── transactions_producer.py   ← producer logic (reads a CSV, publishes to Kafka)
├── Dockerfile
└── requirements.txt
```

---

## `producers/`

| File | Role |
|---|---|
| `transactions_producer.py` | Reads `/data/daily/transactions_<date>.csv` and publishes each row as a JSON message to the `transactions.raw` topic, with a delay (`delay_ms`, 50 ms by default) between each send to simulate a real stream rather than an instant dump. |
| `producer_api.py` | A small FastAPI server exposing `POST /produce?date=YYYY-MM-DD`: this is the entry point that **n8n** calls to trigger `produce_day()`, since n8n can't run a Python script directly. Returns `404` if the requested day's file doesn't exist. |

Example call:

```bash
curl -X POST "http://localhost:8090/produce?date=2026-07-09"
```

---

## `consumers/`

Deliberately empty folder (`.gitkeep` only). The "consumer" role isn't filled by a classic Kafka
script here: it's the **Spark Structured Streaming** job
(`spark/streaming_pipeline/jobs/streaming_job.py`) that directly consumes the `transactions.raw`
topic continuously — see [`spark/streaming_pipeline/README.md`](../spark/streaming_pipeline/README.md).

---

## `Dockerfile`

Python 3.11 slim image containing the system dependencies required by `confluent-kafka` (`gcc`,
`librdkafka-dev`), the Python dependencies from `requirements.txt`, and which starts, by default:

```bash
uvicorn producers.producer_api:app --host 0.0.0.0 --port 8090
```

## `requirements.txt`

- `fastapi`, `uvicorn`: serve `producer_api.py`.
- `confluent-kafka==2.5.3`: Kafka client used by `transactions_producer.py`.
- `pandas`: reads the `daily/` CSVs.
- `python-dotenv`: loads shared environment variables (`.env`).

---

## Manual test (outside n8n)

```bash
docker exec -it shop-kafka-producer bash
python producers/transactions_producer.py --date 2026-07-08 --delay-ms 50
```