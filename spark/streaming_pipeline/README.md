# Streaming Pipeline — H&M

Ce README explique en détail le pipeline **temps réel** : ce que fait chaque fichier, comment il s'articule avec Docker, et pourquoi il fonctionne différemment du pipeline batch.

Si vous n'avez jamais touché à ce dossier, lisez d'abord la section 1 (Batch vs Streaming) avant le reste — c'est la clé pour comprendre pourquoi ce code est écrit ainsi.

Ce fichier couvre uniquement l'ingestion temps réel, jusqu'à l'écriture dans `stream_transactions_ingested`. Ce qui se passe **après** (fusion périodique dans le Data Warehouse, recalcul RFM nocturne, appel du modèle) est orchestré par n8n et détaillé dans le [README principal, section 7](../../README.md#7-orchestration-n8n--cycle-complet) — voir aussi la section 9 ci-dessous pour le lien entre les deux.

---

## 1. Batch vs Streaming — deux fonctionnements totalement différents

Un pipeline batch et un pipeline streaming ne fonctionnent pas de la même manière.

### 1.1 Pipeline Batch (`spark/batch_ml_pipeline/`)

Le pipeline batch traite les données **par lots**.

Exemple :
- Jour 1 → un nouveau fichier CSV arrive → n8n lance `spark-submit`.
- Spark traite le fichier puis **s'arrête**.
- Jour 2 → un autre fichier arrive → n8n **relance** `spark-submit`.
- Spark traite le nouveau fichier puis s'arrête à nouveau.

À chaque nouveau lot de données, **n8n doit redémarrer le job Spark**.

### 1.2 Pipeline Streaming (`spark/streaming_pipeline/`)

Le pipeline streaming fonctionne différemment.

Au démarrage :
- n8n (ou Docker) lance **une seule fois** le job Spark Structured Streaming.
- Ensuite, ce job **reste toujours en fonctionnement**.

Pendant qu'il tourne, Spark écoute en permanence le topic Kafka. Dès que Kafka reçoit de nouveaux messages :
- Spark les détecte automatiquement.
- Il les traite dans un micro-batch (par exemple toutes les 30 secondes).
- Puis il attend les prochains messages.
- Il ne s'arrête jamais.

Il n'est donc **pas nécessaire que n8n relance Spark** à chaque arrivée de nouvelles données — contrairement au batch.

### 1.3 En résumé

| | Batch | Streaming |
|---|---|---|
| Déclenchement | n8n relance `spark-submit` à chaque nouveau fichier | Lancé une seule fois par Docker Compose (`restart: unless-stopped`) |
| Durée de vie du job | Se termine après chaque exécution | Ne se termine jamais |
| Détection de nouvelles données | Attend d'être relancé | Écoute Kafka en continu, réagit automatiquement |
| Écriture PostgreSQL | `mode("overwrite")` — recrée la table | `mode("append")` — ajoute sans jamais effacer |
| Rôle de n8n | Orchestrateur actif (relance le job) | Simple notificateur au démarrage (le job tourne déjà seul) — n8n reprend ensuite la main en aval, à intervalles réguliers, pour fusionner et exploiter les données produites (voir section 9) |

---

## 2. Le Dockerfile

Le pipeline streaming utilise la **même image Docker Spark** que le pipeline batch (un seul `Dockerfile`, à la racine du projet) — pas de duplication d'image. La seule différence est la **commande** lancée au démarrage du conteneur (voir docker-compose ci-dessous) et un package Spark supplémentaire nécessaire pour lire Kafka :

```
--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1
```

Ce package n'est pas installé dans l'image au moment du build : il est téléchargé par Spark au lancement du job, via l'option `--packages` de `spark-submit`. C'est le connecteur qui permet à `spark.readStream.format("kafka")` de fonctionner.

---

## 3. Le service dans `docker-compose.yml`

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

**Points clés de cette configuration :**

- `restart: unless-stopped` : si le conteneur crashe ou si la machine redémarre, Docker le relance automatiquement — indispensable pour un processus censé tourner en permanence.
- `depends_on: kafka, spark-master` : le job a besoin que Kafka et le cluster Spark soient déjà démarrés.
- Le volume `streaming_checkpoint` (à déclarer aussi dans la section `volumes:` racine du `docker-compose.yml`) est **essentiel** : c'est là que Spark enregistre sa progression (quels messages Kafka ont déjà été traités). Sans ce volume persistant, un redémarrage du conteneur ferait perdre cette progression et retraiterait ou sauterait des données.
- C'est un conteneur **séparé** de `spark-master`/`spark-worker` : ces derniers restent dédiés au batch, pour ne pas mélanger les deux charges de travail.

---

## 4. `spark/common/config.py` — configuration partagée

| Fonction | Rôle |
|---|---|
| `get_spark_session(app_name)` | Crée la `SparkSession`, connectée au cluster (`spark://spark-master:7077`), avec le driver JDBC PostgreSQL chargé. |
| `get_jdbc_config()` | Retourne l'URL JDBC (`jdbc:postgresql://postgres:5432/...`) et les identifiants de connexion. |
| `get_kafka_config()` | Retourne l'adresse interne Docker de Kafka (`kafka:29092` — **pas** `localhost:9092`, qui n'est valide que depuis la machine hôte) et le nom du topic (`transactions.raw`, lu depuis `.env`). |

---

## 5. `spark/streaming_pipeline/utils/validation.py`

C'est la porte d'entrée des données : tout message Kafka passe par ce fichier avant d'être considéré comme exploitable.

### Schéma global du fichier

```
Kafka
   │
   ▼
Message JSON brut
   │
   ▼
parse_kafka_messages()
   │
   ▼
DataFrame avec colonnes Spark
   │
   ▼
split_valid_invalid()
      │
      ├──────────────► valid_df
      │                  │
      │                  ▼
      │        Pipeline Streaming
      │        (jointure + écriture)
      │
      ▼
rejected_df
      │
      ▼
Dead Letter Queue / Table des rejets
```

### Les deux fonctions

**`parse_kafka_messages(raw_stream_df)`**
Kafka livre toujours son contenu (`value`) sous forme binaire brute — Spark ne sait pas encore que ce binaire est du JSON représentant une transaction. Cette fonction :
1. Convertit `value` en chaîne de caractères (`CAST(value AS STRING)`).
2. Parse cette chaîne JSON selon `kafka_message_schema` (défini en haut du fichier) via `from_json()`.
3. "Éclate" le résultat en colonnes Spark normales (`t_dat`, `customer_id`, `article_id`, `price`, `sales_channel_id`), en conservant aussi `kafka_timestamp` (l'heure d'arrivée du message, utile pour du débogage ou de la traçabilité).

**`split_valid_invalid(parsed_df)`**
Un flux temps réel n'est jamais garanti propre — contrairement au dataset Kaggle figé du batch, un message Kafka peut être corrompu, incomplet, ou envoyé par un producteur buggé. Cette fonction :
1. Définit une condition `is_valid` (aucun champ obligatoire manquant, prix strictement positif, date présente).
2. Retourne **deux** DataFrames séparés : `valid_df` (transactions exploitables, avec la date déjà convertie en type `Date`) et `rejected_df` (tout le reste, avec une colonne `rejection_reason` ajoutée).

**Pourquoi séparer plutôt que filtrer silencieusement ?** Si on se contentait de supprimer les messages invalides (`filter(is_valid)` sans garder l'autre branche), on perdrait toute visibilité sur les problèmes du producteur ou du flux — un bug qui invaliderait 30% des messages passerait inaperçu. En gardant `rejected_df` et en l'écrivant dans une table dédiée (`stream_transactions_rejected`, voir plus bas), on obtient une vraie **Dead Letter Queue** : les données rejetées restent consultables pour investigation, sans jamais bloquer le traitement du flux principal.

---

## 6. `spark/streaming_pipeline/utils/cleaning.py`

Une seule fonction : **`enrich_with_dimensions(valid_stream_df, customers_static_df, articles_static_df)`**.

Elle joint le flux de transactions validées avec deux DataFrames **statiques** (`customers`, `articles`), chargés une seule fois au démarrage du job (pas depuis un flux). C'est le pattern standard de Spark Structured Streaming appelé **stream-static join** : on enrichit un flux continu avec des données de référence qui changent rarement, via un `broadcast join` (les deux tables statiques sont petites comparées au flux, donc diffusées à tous les exécuteurs plutôt que shufflées).

---

## 7. `spark/streaming_pipeline/jobs/streaming_job.py` — le chef d'orchestre

C'est le script principal, celui lancé par `spark-submit` dans `docker-compose.yml`. Il enchaîne, dans l'ordre :

1. **Chargement des dimensions statiques** (`customers_static`, `articles_static`) — une seule fois, au démarrage.
2. **Lecture du flux Kafka** (`spark.readStream.format("kafka")...load()`), avec `startingOffsets: "latest"` — au (re)démarrage du job, on ne relit **pas** tout l'historique du topic (sinon chaque redémarrage réinjecterait des milliers de transactions déjà traitées).
3. **Validation** (`parse_kafka_messages` + `split_valid_invalid`, voir section 5).
4. **Enrichissement** (`enrich_with_dimensions`, voir section 6).
5. **Écriture en continu**, via deux fonctions appelées à chaque micro-batch (`foreachBatch`) :
   - `write_batch_to_postgres` → écrit les transactions valides et enrichies dans la table `stream_transactions_ingested` (mode `append`).
   - `write_rejected_to_postgres` → écrit les messages invalides dans `stream_transactions_rejected` (mode `append`).
6. **`spark.streams.awaitAnyTermination()`** : maintient le script en vie indéfiniment, tant qu'aucune des deux requêtes streaming ne s'arrête — c'est cette ligne qui fait que le job "ne s'arrête jamais" (section 1.2).

**Pourquoi une table `stream_transactions_ingested` séparée du Data Warehouse batch (`fact_transaction`) ?** Pour ne jamais faire courir de risque au Data Warehouse déjà validé par le pipeline batch. Un job streaming, par nature moins contrôlé qu'un batch sur données figées, écrit dans sa propre table d'atterrissage. La fusion entre les deux est traitée à part, par un job dédié (`merge_stream_to_warehouse.py`) hors de ce pipeline — voir section 9.

**Pourquoi un `checkpointLocation` différent pour `valid` et `rejected` ?** Chaque requête streaming (`writeStream`) a sa propre progression à suivre indépendamment — mélanger les checkpoints des deux flux dans le même dossier créerait des conflits de suivi d'offsets.

---

## 8. Emplacement des fichiers — résumé

```
spark/
├── common/
│   ├── config.py            ← section 4
│   └── schemas.py           ← schémas transactions/customers/articles
└── streaming_pipeline/
    ├── README.md             ← ce fichier
    ├── jobs/
    │   └── streaming_job.py  ← section 7
    └── utils/
        ├── cleaning.py       ← section 6
        └── validation.py     ← section 5
```

---

## 9. Et après ? La suite du cycle (hors de ce dossier)

`stream_transactions_ingested` n'est pas un point d'arrivée final — c'est une table d'atterrissage, consommée périodiquement par des jobs **batch** distincts, orchestrés par n8n :

| Job | Emplacement | Fréquence | Rôle |
|---|---|---|---|
| `merge_stream_to_warehouse.py` | `spark/batch_ml_pipeline/jobs/` | Toutes les 15 min | Fusionne (`append`, avec watermark) les transactions validées du streaming dans `fact_transaction`, le Data Warehouse commun au batch et au streaming |
| `pipeline_hm.py --source=warehouse` | `spark/batch_ml_pipeline/jobs/` | Chaque nuit à 02h00 | Recalcule les Data Marts (RFM, popularité produit, ...) sur `fact_transaction`, donc CSV **et** streaming combinés |

Ces deux jobs sont déclenchés par n8n via `spark/job_trigger_api.py` (le même principe que `producer_api.py` pour Kafka, mais pour `spark-submit`). Détail complet du cycle, diagramme et table des fréquences : [README principal, section 7](../../README.md#7-orchestration-n8n--cycle-complet).
