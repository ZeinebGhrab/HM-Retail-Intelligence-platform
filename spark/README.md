# HM Retail Intelligence Platform

Plateforme de données pour le projet H&M : ingestion, nettoyage, feature engineering et stockage, avec deux modes de traitement complémentaires — **batch** (historique) et **streaming** (temps réel simulé) — réunis dans un seul Data Warehouse et exploités par une API de prédiction.

Vue d'ensemble du cycle complet, orchestré par n8n :

```
Kafka (temps réel) ──► Spark Streaming ──► stream_transactions_ingested
                                                     │
                                    toutes les 15 min │ merge_stream_to_warehouse.py
                                                     ▼
                                            fact_transaction (Data Warehouse)
                                                     │
                                     chaque nuit 02h00 │ pipeline_hm.py --source=warehouse
                                                     ▼
                                        Data Marts (RFM, popularité produit, ...)
                                                     │
                                                     ▼
                                              API modèle (prédiction)
```

Ce README donne la vue d'ensemble du projet. Pour le détail technique du pipeline streaming (Dockerfile, docker-compose, méthodes de chaque fichier), voir [`spark/streaming_pipeline/README.md`](./spark/streaming_pipeline/README.md). Pour le détail de l'orchestration n8n (fusion périodique, recalcul RFM nocturne, appel du modèle), voir la [section 7](#7-orchestration-n8n--cycle-complet).

---

## Arborescence du projet

```
HM-Retail-Intelligence-Platform/
├── data/
│   └── raw/
│       ├── customers.csv
│       ├── articles.csv
│       ├── transactions_train.csv          ← historique (batch)
│       └── daily/                          ← simulateur de flux réel
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
│   │   │   └── merge_stream_to_warehouse.py   ← fusion streaming → Data Warehouse (nouveau)
│   │   └── utils/
│   │       ├── cleaning.py
│   │       └── features.py
│   ├── streaming_pipeline/
│   │   ├── jobs/
│   │   │   └── streaming_job.py
│   │   └── utils/
│   │       ├── cleaning.py
│   │       └── validation.py
│   ├── job_trigger_api.py                     ← déclenche les jobs Spark pour n8n (nouveau)
│   └── job_trigger.Dockerfile
├── model_api/                                  ← API de prédiction (nouveau)
│   └── app.py
├── Dockerfile
├── docker-compose.yml
└── .env
```

---

## 1. Le dossier `data/`

Contient toutes les données du projet, en deux catégories bien séparées :

| Sous-dossier | Contenu | Utilisé par |
|---|---|---|
| `data/raw/` (fichiers racine) | Le dataset Kaggle H&M complet et figé (`customers.csv`, `articles.csv`, `transactions_train.csv`, 33,7M lignes) | `batch_ml_pipeline` |
| `data/raw/daily/` | Des fichiers CSV **générés artificiellement**, un par jour (`transactions_2026-07-08.csv`, etc.), pour simuler l'arrivée réelle de nouvelles transactions | `kafka/producers` (rejoués vers Kafka) |

`daily/` n'est pas une copie du dataset historique : c'est un **simulateur**. Chaque fichier représente ce qu'un jour de production enverrait réellement, rejoué message par message vers Kafka par le producer — voir plus bas.

---

## 2. Le dossier `kafka/`

| Fichier | Rôle |
|---|---|
| `producers/transactions_producer.py` | Lit un fichier `daily/transactions_<date>.csv` et publie chaque ligne comme message JSON sur le topic Kafka `transactions.raw`, avec un léger délai entre chaque message pour simuler un flux réel (pas un déversement instantané). |
| `producers/producer_api.py` | Petit serveur HTTP (FastAPI) qui expose `POST /produce?date=...` — c'est le point d'entrée que n8n appelle pour déclencher le producer, car n8n ne peut pas exécuter un script Python directement. |


---

## 3. Le dossier `spark/`

Contient trois sous-dossiers (une responsabilité distincte chacun) et un service d'orchestration :

### 3.1 `spark/common/`

Code **partagé** entre le pipeline batch et le pipeline streaming, pour éviter la duplication :

| Fichier | Rôle |
|---|---|
| `config.py` | Crée la `SparkSession` (`get_spark_session()`), la configuration JDBC vers PostgreSQL (`get_jdbc_config()`), et la configuration Kafka (`get_kafka_config()`). |
| `schemas.py` | Définit les schémas Spark (`StructType`) des 3 fichiers sources : `transactions_schema`, `customers_schema`, `articles_schema`. Identiques pour le batch et le streaming — un seul endroit à modifier si le format des données change. |

### 3.2 `spark/batch_ml_pipeline/`

Le pipeline historique, avec **deux jobs** distincts :

| Fichier | Rôle | Déclenché |
|---|---|---|
| `jobs/pipeline_hm.py` | Nettoie, joint, calcule les features RFM et écrit les Data Marts. Accepte un argument `--source` : `csv` (comportement d'origine, lit les fichiers bruts — chargement initial) ou `warehouse` (relit `fact_transaction` déjà en base, donc CSV **et** streaming fusionnés — voir 3.2.1). | À la demande (chargement initial) puis chaque nuit à 02h00 en mode `warehouse` |
| `jobs/merge_stream_to_warehouse.py` | **Nouveau.** Fusionne les transactions déjà validées par le streaming (`stream_transactions_ingested`) dans `fact_transaction`, en `append` uniquement, sans jamais retraiter deux fois la même donnée grâce à un **watermark** (table `merge_watermark`, une ligne par pipeline de fusion, mise à jour à chaque exécution réussie). | Toutes les 15 minutes |

#### 3.2.1 Pourquoi fusionner streaming et batch dans `fact_transaction` ?

Sans fusion, `stream_transactions_ingested` (alimentée en continu) et `fact_transaction` (chargée une fois depuis les CSV) restent deux tables isolées : les Data Marts, recalculés uniquement à partir des CSV, ne voient jamais les transactions temps réel. `fact_transaction` devient donc la source de vérité unique, alimentée par deux canaux — un chargement initial depuis les CSV, puis des ajouts périodiques depuis le streaming — et `pipeline_hm.py --source=warehouse` recalcule ensuite les Data Marts sur cet ensemble combiné plutôt que sur les seuls CSV bruts.

### 3.3 `spark/streaming_pipeline/`

Le pipeline temps réel : lit en continu le topic Kafka `transactions.raw`, valide et enrichit chaque message, écrit en ajout (`append`) dans PostgreSQL (`stream_transactions_ingested`). Se lance une fois et ne s'arrête jamais.

**Détail complet de ce pipeline (Dockerfile, docker-compose, méthodes de chaque fichier) : voir [`spark/streaming_pipeline/README.md`](./spark/streaming_pipeline/README.md).**

### 3.4 `spark/job_trigger_api.py`

**Nouveau.** n8n ne peut pas exécuter `spark-submit` directement (ce n'est pas un script Python qu'il sait lancer nativement) — ce petit serveur FastAPI joue exactement le même rôle que `producer_api.py` côté Kafka, mais pour les jobs Spark batch. Il expose `POST /jobs/{job_name}` (`job_name` = `merge-stream` ou `compute-rfm`) et lance, via `docker exec`, le `spark-submit` correspondant sur le conteneur `spark-worker`.

Il tourne dans son propre conteneur (`spark-job-trigger`, voir docker-compose ci-dessous) et est le **seul** service à monter le socket Docker (`/var/run/docker.sock`) — jamais n8n lui-même, pour limiter la surface d'attaque.

---

## 4. Le dossier `model_api/`

**Nouveau.** API de prédiction (FastAPI) qui charge le dernier modèle entraîné et expose un endpoint de prédiction, à partir des features calculées dans les Data Marts (`customers_features_train`, etc.). C'est le dernier maillon du cycle nocturne : une fois les Data Marts recalculés, n8n appelle cette API pour rafraîchir les prédictions consommées en aval (churn, recommandation, etc.).

---

## 5. Fichiers à la racine

| Fichier | Rôle |
|---|---|
| `Dockerfile` | Image Spark commune (batch + streaming), avec le driver JDBC PostgreSQL. |
| `docker-compose.yml` | Orchestration de tous les services : Kafka, Zookeeper, PostgreSQL, Spark (master/worker/streaming), **`spark-job-trigger`** (nouveau), **`model-api`** (nouveau), n8n, le producer API, Adminer. |
| `.env` | Configuration partagée (identifiants PostgreSQL, ports, nom du topic Kafka) — lue par tous les services. |



## 6. Orchestration n8n — cycle complet

Quatre workflows n8n couvrent l'ensemble du cycle, du message Kafka jusqu'à la prédiction :

| # | Étape | Déclencheur n8n | Fréquence | Appelle |
|---|---|---|---|---|
| 1 | Simulation d'arrivée de transactions | Manuel ou schedule | Ponctuel (test/démo) | `POST /produce?date=...` sur `kafka-producer-api` |
| 2 | Ingestion streaming | Aucun (le job tourne déjà en continu, voir [`spark/streaming_pipeline/README.md`](./spark/streaming_pipeline/README.md)) | — | — |
| 3 | Fusion streaming → Data Warehouse | Schedule Trigger | Toutes les 15 min | `POST /jobs/merge-stream` sur `spark-job-trigger` |
| 4 | Recalcul des Data Marts (RFM, popularité produit, ...) | Schedule Trigger | Chaque nuit à 02h00 | `POST /jobs/compute-rfm?source=warehouse` sur `spark-job-trigger` |
| 5 | Rafraîchissement des prédictions | Enchaîné après l'étape 4 (même workflow) | Chaque nuit à 02h00, juste après l'étape 4 | `model-api` |

```
                n8n
                 │
                 │ POST /produce?date=2026-07-08     (étape 1, ponctuel)
                 ▼
        kafka-producer-api (FastAPI) ──► transactions_producer.py ──► Kafka topic: transactions.raw
                                                                              │
                                                                              ▼
                                                          Spark Structured Streaming (étape 2, continu)
                                                          
                                                                              │
                                                                              ▼
                                                          stream_transactions_ingested (PostgreSQL)


                n8n  ── toutes les 15 min ──►  POST /jobs/merge-stream  ──► spark-job-trigger
                                                                                    │
                                                                                    ▼
                                                          merge_stream_to_warehouse.py (spark-submit)
                                                                                    │
                                                                                    ▼
                                                              fact_transaction (Data Warehouse)


                n8n  ── chaque nuit 02h00 ──►  POST /jobs/compute-rfm?source=warehouse  ──► spark-job-trigger
                                                                                                    │
                                                                                                    ▼
                                                                  pipeline_hm.py --source=warehouse (spark-submit)
                                                                                                    │
                                                                                                    ▼
                                                                       Data Marts (customers_features_train, ...)
                                                                                                    │
                                                                                                    ▼
                                                                              model-api (rafraîchit les prédictions)
```

**Pourquoi `spark-job-trigger` et pas n8n directement ?** n8n n'a pas de nœud natif pour lancer `spark-submit` (ce n'est pas un binaire HTTP). Comme pour le producer Kafka (`producer_api.py`, section 2), on passe donc par un petit serveur FastAPI intermédiaire qui, lui, sait exécuter la commande — voir 3.4 pour son fonctionnement et son placement Docker.

**Pourquoi deux fréquences aussi différentes (15 min vs nocturne) ?** `merge_stream_to_warehouse.py` est un simple `append` incrémental sur les nouvelles lignes uniquement (léger, peut tourner souvent). `pipeline_hm.py --source=warehouse` recalcule en revanche tous les agrégats (RFM, popularité produit) sur l'ensemble du Data Warehouse — coûteux, donc réservé à un run quotidien, la nuit, quand la charge est faible.
---

## 7. API

- **`streaming_api.py`** (à côté de `spark/streaming_pipeline/`) : expose `POST /streaming`, appelé par n8n pour démarrer le job Spark Streaming en continu via `spark-submit` s'il ne tourne pas déjà (ou simplement renvoyer son statut s'il tourne), avec des endpoints optionnels `/stop`, `/status` et `/logs` pour le piloter et le surveiller manuellement.
- **`job_trigger_api.py`** (`spark/job_trigger_api.py`) : expose `POST /jobs/{job_name}`, appelé par n8n chaque nuit à 02:00, d'abord pour `merge-stream` (fusion `stream_transactions_ingested` → `fact_transaction`) puis, juste après dans le même workflow, pour `compute-rfm --source=warehouse` (recalcul des Data Marts sur le warehouse fraîchement fusionné), en lançant le `spark-submit` correspondant via `docker exec` sur `shop-spark-worker`, avec un timeout de sécurité de 30 minutes. 
## 8. Commandes utiles (tests manuels)

```bash
# Lancer le job streaming à la main (hors n8n), pour vérifier qu'il tourne correctement :
docker exec -it shop-spark-master bash
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
  /opt/spark/work-dir/spark/streaming_pipeline/jobs/streaming_job.py

# Vérifier que le topic Kafka existe et reçoit des messages :
docker exec -it shop-kafka bash
kafka-topics --bootstrap-server kafka:29092 --list
```
Invoke-WebRequest `                                               
>> -Method POST `                  
>> "http://localhost:8090/produce?date=2026-07-09"                      
