# `kafka/`

Ce dossier gère l'entrée dans le flux temps réel : il simule l'arrivée de transactions et les publie sur Kafka. Il ne contient **pas** de consumer Kafka classique — la consommation du topic est assurée par le job **Spark Structured Streaming** (`spark/streaming_pipeline/jobs/streaming_job.py`), pas par du code ici.

```
kafka/
├── consumers/              ← vide (voir note ci-dessous)
├── producers/
│   ├── producer_api.py     ← API FastAPI, point d'entrée appelé par n8n
│   └── transactions_producer.py   ← logique du producer (lit un CSV, publie sur Kafka)
├── Dockerfile
└── requirements.txt
```

---

## `producers/`

| Fichier | Rôle |
|---|---|
| `transactions_producer.py` | Lit `/data/daily/transactions_<date>.csv` et publie chaque ligne comme message JSON sur le topic `transactions.raw`, avec un délai (`delay_ms`, 50 ms par défaut) entre chaque envoi pour simuler un flux réel plutôt qu'un déversement instantané. |
| `producer_api.py` | Petit serveur FastAPI qui expose `POST /produce?date=YYYY-MM-DD` : c'est le point d'entrée que **n8n** appelle pour déclencher `produce_day()`, puisque n8n ne peut pas exécuter un script Python directement. Renvoie `404` si le fichier du jour demandé n'existe pas. |

Exemple d'appel :

```bash
curl -X POST "http://localhost:8090/produce?date=2026-07-09"
```

---

## `consumers/`

Dossier volontairement vide (`.gitkeep` uniquement). Le rôle de "consumer" n'est pas rempli par un script Kafka classique ici : c'est le job **Spark Structured Streaming** (`spark/streaming_pipeline/jobs/streaming_job.py`) qui consomme directement le topic `transactions.raw` en continu — voir [`spark/streaming_pipeline/README.md`](../spark/streaming_pipeline/README.md).

---

## `Dockerfile`

Image Python 3.11 slim contenant les dépendances système nécessaires à `confluent-kafka` (`gcc`, `librdkafka-dev`), les dépendances Python du `requirements.txt`, et qui lance par défaut :

```bash
uvicorn producers.producer_api:app --host 0.0.0.0 --port 8090
```

## `requirements.txt`

- `fastapi`, `uvicorn` : servir `producer_api.py`.
- `confluent-kafka==2.5.3` : client Kafka utilisé par `transactions_producer.py`.
- `pandas` : lecture des CSV `daily/`.
- `python-dotenv` : chargement des variables d'environnement partagées (`.env`).

---

## Test manuel (hors n8n)

```bash
docker exec -it shop-kafka-producer bash
python producers/transactions_producer.py --date 2026-07-08 --delay-ms 50
```
