# Pipeline Big Data H&M — Spark, PostgreSQL & Data Warehouse

Pipeline de données batch qui transforme les fichiers CSV bruts du dataset **H&M (Kaggle)** en un **Data Warehouse PostgreSQL** structuré (schéma en étoile) et en **Data Marts** prêts à l'emploi pour le Machine Learning, un dashboard et un système RAG / LLM.

Le tout tourne dans **Docker Compose**, avec **Apache Spark** comme moteur de traitement et **PostgreSQL** comme base de stockage finale, reliés via le protocole **JDBC**.

---

## 1. Vue d'ensemble du flux

```
CSV (Kaggle H&M)
      │
      ▼
Apache Spark  ──────►  Driver JDBC PostgreSQL
      │                        │
      ▼                        ▼
Nettoyage + Features   ──►  PostgreSQL (Data Warehouse)
      │                        │
      ▼                        ▼
Star Schema            Data Marts (ML · Dashboard · RAG)
```

---

## 2. Pourquoi Spark écrit dans PostgreSQL via JDBC (et pas psycopg2) ?

- `psycopg2` (présent dans `requirements.txt`) n'est utilisé que par du code **Python pur**.
- **Spark tourne sur la JVM (Java)** — il ne connaît pas `psycopg2`.
- Quand le code appelle `df.write.jdbc(...)`, c'est **Spark (Java)** qui écrit dans PostgreSQL, pas Python. Il lui faut donc un **driver Java JDBC**.

```
Script PySpark → Spark DataFrame API → Spark Engine (Java) → Driver JDBC PostgreSQL → PostgreSQL
```

---

## 3. Configuration partagée : le fichier `.env`

```
POSTGRES_PORT=5432
POSTGRES_DB=hm_retail
POSTGRES_USER=hm_admin
POSTGRES_PASSWORD=change_me
```

Le conteneur Spark ne connaît ces variables que si `.env` est monté ou déclaré en `env_file` sur **tous** les services Spark (`spark-master` **et** `spark-worker`) — pas seulement sur `postgres`.

---

## 4. Structure du projet et rôle de chaque fichier

| Fichier | Rôle |
|---|---|
| `config.py` | Centralise la création de la `SparkSession` (`get_spark_session()`) et la configuration de connexion JDBC (`get_jdbc_config()`). |
| `schemas.py` | Définit explicitement le schéma (types de colonnes) des fichiers CSV `transactions`, `customers`, `articles` — pas de nettoyage ici. |
| `cleaning.py` | Reproduit le nettoyage réalisé dans le notebook d'EDA : imputation, conversion de dates, création de tranches d'âge. |
| `features.py` | Calcule les features RFM et enrichies par client, construit les tables d'agrégation métier, puis le Data Warehouse (dimensions + faits) et les Data Marts. |

### 4.1 `config.py`

`get_spark_session()` crée la `SparkSession`, la nomme (`appName("hm_pipeline")`), pointe vers le cluster (`master("spark://spark-master:7077")`) et charge le driver JDBC. `get_jdbc_config()` retourne l'URL JDBC et les identifiants, pour éviter de les répéter dans chaque script.

> **Spark Master vs Spark Worker, en bref** : le **Master** coordonne le cluster (il reçoit les jobs soumis, connaît la liste des workers disponibles, répartit le travail) — il n'exécute aucun calcul lui-même. Le **Worker** exécute réellement les tâches (lecture des CSV, jointures, agrégations) avec les ressources qu'il a déclarées au Master. `spark-submit` peut être lancé depuis n'importe quel conteneur ayant accès réseau au Master et aux fichiers du job — y compris depuis le conteneur `spark-worker` lui-même (voir section 9).

### 4.2 `schemas.py`

Définit un schéma explicite (`StructType`) plutôt que `inferSchema=True`, pour des raisons de performance, de fiabilité des types et de reproductibilité. Toutes les colonnes du fichier `customers.csv` sont lues, **y compris `FN` et `Active`**, avec leur type d'origine.

### 4.3 `cleaning.py`

| Fonction | Traitement |
|---|---|
| `clean_customers()` | Supprime explicitement `FN` et `Active` (`.drop("FN", "Active")`) — un `NaN` sur ces colonnes signifie une absence réelle d'abonnement selon l'EDA, pas une valeur à imputer. Âge imputé par la **médiane** (`approxQuantile`) ; statut club et fréquence newsletter imputés par le **mode** ; création de tranches d'âge (`age_group`). |
| `clean_articles()` | Aucune imputation (0,4 % de valeurs manquantes sur `detail_desc`, jugé négligeable). |
| `clean_transactions()` | Conversion de `t_dat` en type `Date`, aucun filtre ni dédoublonnage. |

Faire ce tri dans `cleaning.py` plutôt qu'à la lecture (`schemas.py`) rend la décision de nettoyage explicite et traçable, au bon endroit du pipeline.

### 4.4 `features.py`

**Features RFM par client** : `total_spend` (Monetary), `n_transactions` (Frequency), `recency_days` depuis `DATASET_END = "2020-09-22"` (date fixe, dataset historique) (Recency), `tenure_days`, `avg_basket_value`, `purchase_frequency_per_month`, `n_distinct_categories`.

`segment_valeur` : segmentation en quartiles de `total_spend` via **`approxQuantile`**  — voir section 12 pour le détail du changement par rapport à `ntile()`.

---

## 5. Le Data Warehouse — schéma en étoile

```
              Dim Customer
                    │
Dim Date ─── Fact Transaction ─── Dim Article
```

| Table | Contenu |
|---|---|
| `dim_customer` | Infos descriptives client ; `customer_key` généré par hash `crc32`. |
| `dim_article` | Infos descriptives produit ; `article_key = article_id` (déjà un entier unique). |
| `dim_date` | Une ligne par date distincte, avec `date_key` lisible (`2020-09-22 → 20200922`). |
| `fact_transaction` | Une ligne par achat : clés vers les dimensions + mesures (`price`, `sales_channel_id`). |

---

## 6. Position des Data Marts dans le schéma en étoile

Le schéma en étoile classique a deux niveaux : les dimensions et le fait, au grain le plus fin. Les Data Marts forment un **troisième niveau** : des agrégats précalculés, un cran au-dessus du fait.

**Cœur classique — grain fin (1 ligne = 1 transaction)** : `dim_customer`, `dim_article`, `dim_date`, `fact_transaction`.

**Data Marts — grain agrégé** :
- `customers_features_train` — 1 ligne = 1 client
- `products_performance` — 1 ligne = 1 article
- `daily_sales` — 1 ligne = 1 jour
- `customer_segments_summary` — 1 ligne = 1 segment

Les marts sont calculés à partir de `fact_transaction`, puis stockés à côté, dans la même base — ils ne remplacent ni les dimensions ni le fait.

### À quoi servent vraiment les Data Marts ?

Sans mart, chaque question métier obligerait à scanner et recalculer sur 33,7 millions de lignes à chaque appel.

| Sans Data Mart | Avec Data Mart |
|---|---|
| Scanner 33,7M lignes à chaque requête | Lire 1 ligne déjà prête dans le mart |
| Refaire un `groupBy` + agrégation à chaque appel | Aucun recalcul, donnée déjà résumée |
| Chaque équipe réécrit sa propre requête | Une seule table de référence, partagée |

Au lieu que Django ou l'équipe ML recalcule le RFM en scannant 33,7M lignes à chaque appel, ils lisent directement `customers_features_train` — une ligne par client, déjà prête, à jour à chaque exécution (`mode("overwrite")`).

---

## 7. Écriture finale dans PostgreSQL

```python
for name, df in tables.items():
    df.write.mode("overwrite").jdbc(
        url=jdbc_url,
        table=name,
        properties=jdbc_props
    )
```

Le mode `overwrite` recrée entièrement chaque table à chaque exécution du pipeline batch.

---

## 8. Stack technique

- **Docker / Docker Compose** — orchestration des services.
- **Apache Spark (PySpark)** — traitement distribué, nettoyage, feature engineering.
- **PostgreSQL** — stockage final du Data Warehouse et des Data Marts.
- **JDBC** (`postgresql-42.7.3.jar`) — pont de communication entre Spark (JVM) et PostgreSQL.
- **Adminer** — interface web de consultation de la base (voir section 10).

---

## 9. Lancer le pipeline

```bash
# 1. Démarrer l'infrastructure
docker compose up -d

# 2. Exécuter le job Spark — lancé depuis le conteneur worker,
#    connecté au master via son URL réseau interne
docker exec shop-spark-worker \
  /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  /opt/spark/work-dir/jobs/pipeline_hm.py
```

À la fin de l'exécution, les 8 tables sont disponibles dans PostgreSQL : `dim_customer`, `dim_article`, `dim_date`, `fact_transaction`, `customers_features_train`, `products_performance`, `daily_sales`, `customer_segments_summary`.

---

## 10. Visualiser le Data Warehouse via Adminer

**Adminer** est une interface web légère (l'équivalent de phpMyAdmin, mais compatible PostgreSQL nativement) pour consulter les tables sans terminal.

Ajout dans `docker-compose.yml`, **à l'intérieur** de `services:` :

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

Lancement :
```bash
docker compose up -d adminer
```

Accès : `http://localhost:8081`, puis connexion avec :

| Champ | Valeur |
|---|---|
| Système | PostgreSQL |
| Serveur | `postgres` (nom du service Docker, pas `localhost`) |
| Utilisateur | `hm_admin` |
| Mot de passe | celui de `POSTGRES_PASSWORD` |
| Base de données | `hm_retail` |

---

## 11. Cohérence avec l'EDA

| Partie | Compatibilité |
|---|---|
| Schemas | ✅ 100 % |
| Nettoyage customers | ✅ 100 % |
| Nettoyage articles | ✅ 100 % |
| Nettoyage transactions | ✅ 100 % |
| Features RFM | ✅ 100 % |
| Quartiles (`approxQuantile`) | ✅ Équivalent fonctionnel — remplace `ntile()` pour éviter un tri global sur une seule partition (voir ci-dessous) |
| Tables Dashboard / RAG | ✅ 100 % |

### 12. Pourquoi `ntile()` a été remplacé par `approxQuantile`

`Window.orderBy("total_spend")` + `ntile(4)` nécessite un tri global de toute la colonne sur **une seule partition** (`WARN WindowExec: No Partition Defined`), ce qui a fait passer le job de quelques secondes à plus de 30 minutes sur 1,36M clients. `approxQuantile` calcule les seuils (25e/50e/75e percentile) de façon distribuée, sans ce goulot d'étranglement. Conséquence : les 4 segments ne sont plus garantis à effectifs strictement égaux (ce que faisait `ntile`), mais reflètent des **seuils de dépense réels** — plus cohérent pour une segmentation marketing, et plus rapide.

---

## 13. Pour aller plus loin

Une documentation détaillée est disponible dans le PDF joint : **`Pipeline_HM_Spark_PostgreSQL_DataWarehouse.pdf`**.
