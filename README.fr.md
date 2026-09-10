<div align="center">

# 🛍️ H&M Retail Intelligence Platform

**Une plateforme data & IA construite autour du dataset Kaggle H&M Personalized Fashion
Recommendations — pipeline Big Data, MLOps, streaming temps réel et orchestration.**

<p align="center">
  <a href="./README.md">🇬🇧 English</a> ·
  <a href="./README.fr.md"><strong>🇫🇷 Français</strong></a>
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

> Ce README décrit **uniquement ce qui est réellement implémenté et fonctionnel aujourd'hui**,
> avec une explication claire du fonctionnement de chaque brique. Les éléments non implémentés
> sont listés séparément en [§8](#8-ce-qui-nest-pas-encore-implémenté), sans jamais être présentés
> comme opérationnels.

## 📑 Table des matières

- [1. Vue d'ensemble](#1-vue-densemble)
  - [1.1 Ce que fait la plateforme](#11-ce-que-fait-la-plateforme)
  - [1.2 Flux de données de bout en bout](#12-flux-de-données-de-bout-en-bout)
- [2. Pipeline analytique — `notebooks/`](#2-pipeline-analytique--notebooks)
- [3. Pipeline Big Data — `spark/`](#3-pipeline-big-data--spark)
- [4. MLOps — entraînement, tracking & serving — `ml/`](#4-mlops--entraînement-tracking--serving--ml)
- [5. Streaming temps réel & orchestration — `kafka/` + `n8n/`](#5-streaming-temps-réel--orchestration--kafka--n8n)
- [6. Dashboards — `grafana/`](#6-dashboards--grafana)
- [7. Infrastructure Docker](#7-infrastructure-docker)
- [8. Ce qui n'est pas encore implémenté](#8-ce-qui-nest-pas-encore-implémenté)
- [9. Démarrage rapide](#9-démarrage-rapide)
- [10. Structure du repository](#10-structure-du-repository)
- [11. Documentation complémentaire](#11-documentation-complémentaire)

---

## 1. Vue d'ensemble

### 1.1 Ce que fait la plateforme

| Capacité | Implémentée par |
|---|---|
| 📊 Analyse exploratoire approfondie & nettoyage statistiquement justifié | `notebooks/` |
| 🏗️ Pipeline Big Data batch → Data Warehouse PostgreSQL (star schema + Data Marts) | `spark/batch_ml_pipeline/` |
| ⚡ Ingestion de transactions quasi temps réel | `kafka/` + `spark/streaming_pipeline/` |
| 🤖 Entraînement de modèles, tracking d'expériences & registre | `ml/training/` + MLflow |
| 🚀 API d'inférence (prédiction unitaire & batch) | `ml/serving/` (FastAPI) |
| 📈 Surveillance de la dérive des données | `ml/monitoring/` (Evidently AI) |
| 🕹️ Ordonnancement & orchestration de tout le cycle | `n8n/workflows/` |
| 📊 Dashboards métier & ML | `grafana/` |
| ✅ CI/CD (lint, tests, build d'image, ré-entraînement planifié) | `.github/workflows/mlops-ci.yml` |

### 1.2 Flux de données de bout en bout

```
data/raw/*.csv (Kaggle : customers, articles, transactions)
        │
        ▼  spark-submit pipeline_hm.py
   PostgreSQL — star schema + Data Marts
   (table clé : customers_features_train)
        │
        ▼  ml/training/train_*.py --register
   MLflow — tracking d'expériences + Model Registry (alias "champion")
        │
        ▼  models:/<name>@champion  (ou repli local ml/models/*.joblib)
   ml/serving/app.py — API d'inférence FastAPI (/predict/*)
        │
        ▼
   ml/monitoring/drift_report.py — rapport de dérive (Evidently AI)
        │
        ▼
   grafana/ — dashboards métier & ML (lit PostgreSQL)

En parallèle, indépendamment de ce flux batch :
notebooks/01→07 — pipeline EDA + ML complet sur un instantané CSV des mêmes données
kafka/ + spark/streaming_pipeline/ — ingestion de transactions quasi temps réel, fusionnée chaque nuit
n8n/workflows/ — planifie la simulation, le recalcul RFM et le ré-entraînement hebdomadaire
```

Ce diagramme est volontairement plus court que ce qu'on pourrait imaginer pour une plateforme
"retail intelligence" complète : il ne montre que ce qui tourne réellement aujourd'hui. Chaque
flèche ci-dessus correspond à une section ci-dessous avec la commande exacte pour l'exécuter.

---

## 2. Pipeline analytique — `notebooks/`

**Ce que c'est** : une série de 7 notebooks Jupyter, déjà exécutés sur les vraies données Kaggle
(résultats, graphiques et scores déjà visibles dans les fichiers `.ipynb` — rien à ré-exécuter
pour les consulter).

**Comment ça marche** : chaque notebook lit les CSV Kaggle (`data/raw/`) ou les objets produits
par le notebook précédent (dossier `intermediate/`, généré à l'exécution, non versionné), applique
une étape du pipeline (nettoyage, EDA, enrichissement, feature engineering, modélisation), puis
exporte ses résultats pour le notebook suivant. Les notebooks 06 et 07 exportent aussi directement
les modèles sélectionnés (`joblib.dump`) vers `ml/models/`.

| # | Notebook | Contenu |
|---|---|---|
| 01 | `01_EDA_Nettoyage_Clients.ipynb` | Nettoyage de `customers.csv`, EDA clients |
| 02 | `02_EDA_Produits_Transactions.ipynb` | EDA produits, passe chunkée sur 33,7M transactions |
| 03 | `03_RFM_Enrichissement_Externe.ipynb` | Analyse RFM, enrichissement météo & jours fériés |
| 04 | `04_FeatureEngineering_Soldes_RAG.ipynb` | Table de features clients, export base de connaissances RAG |
| 05 | `05_ML_ReductionDim_Clustering_Rapide.ipynb` | PCA, t-SNE/UMAP, K-Means exploratoire |
| 06 | `06_ML_Classification_Regression.ipynb` | Classification statut club, régression des dépenses |
| 07 | `07_ML_Clustering_Approfondi_Synthese.ipynb` | Clustering approfondi (k=6), synthèse ML |

📖 **Détail complet** : [`notebooks/README.md`](./notebooks/README.md) (ordre d'exécution, usage)
et [`notebooks/DETAILS.md`](./notebooks/DETAILS.md) (méthodologie statistique, résultats).

---

## 3. Pipeline Big Data — `spark/`

**Ce que c'est** : un job Spark batch qui transforme les 3 CSV Kaggle bruts en un Data Warehouse
PostgreSQL prêt à l'emploi.

**Comment ça marche** : `spark/jobs/pipeline_hm.py` lit `data/raw/*.csv`, applique le nettoyage
(`spark/utils/cleaning.py` : imputation médiane/mode, tranches d'âge), calcule les features RFM
clients (`spark/utils/features.py` : récence, fréquence, valeur monétaire, diversité d'achat), et
écrit le tout via JDBC dans PostgreSQL sous forme de star schema et de Data Marts — dont la table
`customers_features_train`, qui est **la source de vérité unique** consommée en aval par `ml/`.

**Exécution** :
```bash
docker exec shop-spark-worker \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
  /opt/spark/work-dir/jobs/pipeline_hm.py
```

📖 **Détail complet** : [`spark/README.md`](./spark/README.md) (pipeline batch, pipeline
streaming, vue d'ensemble de l'orchestration n8n).

---

## 4. MLOps — entraînement, tracking & serving — `ml/`

**Ce que c'est** : les 3 modèles validés dans les notebooks 06-07 (classification du statut club,
régression des dépenses totales, segmentation clients), rejoués de façon scriptée et
industrialisée.

**Comment ça marche**, étape par étape :

| Étape | Composant | Rôle |
|---|---|---|
| 1 | `ml/training/train_*.py` | Charge `customers_features_train` depuis PostgreSQL (avec repli synthétique pour la CI), reproduit exactement la recette validée dans les notebooks, entraîne, et logue vers MLflow |
| 2 | MLflow (`--register`) | Tracking d'expériences (paramètres, métriques, artefacts) + Model Registry, promotion via l'alias `champion` |
| 3 | `ml/serving/app.py` (FastAPI) | Charge le modèle `champion` (Registry, ou repli local dans `ml/models/`), expose `/predict/club-status`, `/predict/segment`, `/predict/spend`, `/predict/batch`, `/health` |
| 4 | `ml/monitoring/drift_report.py` | Compare une fenêtre de référence et une fenêtre courante de `customers_features_train` (Evidently AI), génère un rapport HTML de dérive |
| 5 | `.github/workflows/mlops-ci.yml` | Lint + tests à chaque push, build de l'image Docker sur `main`, cron hebdomadaire de ré-entraînement/monitoring |

**Modèles & scores** (issus des notebooks 06-07, reproduits exactement par les scripts
d'entraînement) :

| Tâche | Modèle | Métrique |
|---|---|---:|
| Classification `club_member_status` | Random Forest (optimisé) | F1-macro = 0,3889 |
| Régression `total_spend` | XGBoost | R² (test) = 0,943 |
| Segmentation clients | K-Means (k=6) | Silhouette = 0,2537 |

📖 **Détail complet, avec toutes les commandes** : [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) — le
document le plus détaillé du repo, à lire en premier pour tout ce qui concerne le ML.

---

## 5. Streaming temps réel & orchestration — `kafka/` + `n8n/`

**Ce que c'est** : un second flux, indépendant du flux batch décrit en §3, qui ingère les
transactions quasi en temps réel via Kafka, plus 3 workflows n8n qui planifient l'ensemble du
pipeline (batch + streaming + ré-entraînement).

**Comment ça marche** :

1. `kafka/producers/transactions_producer.py` (exposé via `kafka/producers/producer_api.py`, port
   `8090`) lit un CSV journalier (`data/raw/daily/`) et publie chaque transaction sur le topic
   Kafka `transactions.raw`.
2. `spark/streaming_pipeline/jobs/streaming_job.py` consomme en continu ce topic, valide chaque
   message, et écrit les lignes valides/rejetées dans PostgreSQL (`stream_transactions_ingested` /
   `stream_transactions_rejected`).
3. `spark/batch_ml_pipeline/jobs/merge_stream_to_warehouse.py` fusionne ces données streaming dans
   le warehouse (`fact_transaction`, `dim_date`), avec un watermark pour ne traiter que les
   nouvelles lignes.
4. Trois workflows n8n orchestrent tout cela, répartis en fichiers indépendants dans
   [`n8n/workflows/`](./n8n/workflows/) :

| Workflow | Déclenchement | Rôle |
|---|---|---|
| [`hm-simulation-quotidienne-kafka.json`](./n8n/workflows/hm-simulation-quotidienne-kafka.json) | Tous les jours à 06h00 | Génère les transactions du jour, déclenche le producteur Kafka |
| [`hm-rfm-nocturne-notifications.json`](./n8n/workflows/hm-rfm-nocturne-notifications.json) | Tous les jours à 02h00 | Fusionne le streaming dans le warehouse, recalcule le RFM, génère une synthèse via Ollama, la diffuse |
| [`hm-reentrainement-hebdomadaire.json`](./n8n/workflows/hm-reentrainement-hebdomadaire.json) | Tous les lundis à 06h00 | Ré-entraîne les 3 modèles ML, promeut le champion, recharge `ml-serving` |

> ⚠️ **Limitation connue** : le workflow `hm-rfm-nocturne-notifications` appelle des endpoints
> (`Push SSE → Django`, `Envoyer au Chatbot`, `Envoyer FCM`) qui pointent vers un backend Django,
> un chatbot et un service FCM **absents de ce repository** — des intégrations prévues pour un
> autre projet (`ShopAnalytics`), pas du code présent ici.

📖 **Détail complet de chaque nœud** : [`n8n/workflows/README.md`](./n8n/workflows/README.md).

---

## 6. Dashboards — `grafana/`

**Ce que c'est** : 5 dashboards Grafana (25 panels au total), qui lisent directement le Data
Warehouse et les Data Marts PostgreSQL — vue d'ensemble des ventes, analytique produits,
analytique clients, segmentation et performance journalière.

**Comment ça marche** : `grafana/provisioning/datasources/postgres.yml` configure automatiquement
la connexion PostgreSQL au démarrage — aucune config manuelle nécessaire dans l'interface. Chaque
panel est une simple requête SQL sur `fact_transaction`, `dim_customer`, `dim_article`,
`daily_sales`, `products_performance`, ou `customer_segments_summary`.

```bash
docker compose up -d grafana
# → http://localhost:3001  (admin / hm_admin)
```

📖 **Détail complet** : [`grafana/README.md`](./grafana/README.md) (mise en place) et
[`grafana/README_GRAFANA.md`](./grafana/README_GRAFANA.md) (les 25 panels avec leurs requêtes
SQL).

---

## 7. Infrastructure Docker

**Ce que c'est** : l'orchestration de tous les conteneurs nécessaires aux parties implémentées
ci-dessus (plus quelques briques d'infrastructure prêtes mais pas encore reliées à du code
applicatif, voir §8).

**Services soutenant une partie implémentée et fonctionnelle** :

| Service | Rôle réel aujourd'hui |
|---|---|
| `postgres` | Stocke le Data Warehouse produit par `spark/jobs/pipeline_hm.py`, dont `customers_features_train` |
| `adminer` | Interface web pour parcourir PostgreSQL (`http://localhost:8081`) |
| `spark-master` / `spark-worker` | Exécutent les jobs Spark batch et streaming |
| `mlflow` | Serveur de tracking + Model Registry pour `ml/training/` et `ml/serving/` |
| `ml-serving` | Fait tourner l'API FastAPI de `ml/serving/app.py` dans un conteneur |
| `grafana` | Dashboards métier & ML (§6) |
| `n8n` | Orchestre le cycle batch/streaming/ré-entraînement (§5) |
| `kafka` | Broker d'événements pour l'ingestion quasi temps réel (§5) |

**Démarrage minimal pour le flux implémenté** (sans les services pas encore reliés à du code) :
```bash
cp .env.example .env        # renseigner les vraies valeurs
docker compose up -d postgres adminer spark-master spark-worker mlflow ml-serving
```

**Démarrage complet de l'infrastructure du repo** :
```bash
./run.sh all                # ou run.bat all sous Windows
./run.sh status              # vérifier que les conteneurs tournent
```

---

## 8. Ce qui n'est pas encore implémenté

Ces éléments existent dans le repo sous forme de dossiers/images Docker prêtes, mais **ne
contiennent aucune logique fonctionnelle** — ce sont des placeholders (`.gitkeep`), pas des
fonctionnalités opérationnelles :

| Dossier / service | État réel |
|---|---|
| `kafka/consumers/` | Dossier vide (le vrai "consumer" est le job Spark `spark/streaming_pipeline/jobs/streaming_job.py`, voir §5) — rien à y ajouter sauf besoin d'un consumer Kafka autonome. |
| `backend/app/` | Dossier vide. Aucune API applicative n'existe entre un frontend et les données/modèles. |
| `frontend/src/` | Dossier vide. Aucune interface utilisateur (dashboard) n'existe. |
| Chatbot RAG (`ollama` + `qdrant`) | Les services Docker démarrent. `ollama` est réellement appelé par le workflow n8n `hm-rfm-nocturne-notifications` (génération de synthèse), mais `qdrant` ne reçoit aucune donnée : pas d'ingestion, pas de collection créée, pas de recherche vectorielle reliée à un frontend. |
| Nœuds n8n `Push SSE → Django`, `Envoyer au Chatbot`, `Envoyer FCM` | Présents dans `hm-rfm-nocturne-notifications.json`, mais pointent vers un backend Django, un chatbot et un service FCM qui n'existent pas dans ce repo. |
| `.env.example` | Absent du repo, alors que `docker-compose.yml` et ce README s'y réfèrent (`cp .env.example .env`). À créer avant le premier démarrage. |
| `data/processed/`, `data/features/` | Dossiers hérités d'une version antérieure du pipeline, non alimentés par le code actuel. |
| Remote DVC/DagsHub | `.dvc/config` contient un template d'URL, pas encore pointé vers un vrai repo DagsHub. |

**Pourquoi les documenter quand même ?** Pour que personne ne perde de temps à chercher du code
qui n'existe pas, et pour que la prochaine personne qui reprend le projet sache exactement par où
commencer si elle veut construire l'une de ces briques.

---

## 9. Démarrage rapide

```bash
# 0. Configuration
cp .env.example .env

# 1. Infrastructure nécessaire au flux implémenté
docker compose up -d postgres adminer spark-master spark-worker mlflow ml-serving

# 2. Placer les 3 CSV Kaggle dans data/raw/, puis lancer le pipeline Spark
docker exec shop-spark-worker \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
  /opt/spark/work-dir/jobs/pipeline_hm.py

# 3. Entraîner et enregistrer les 3 modèles
python ml/training/train_classification.py --register
python ml/training/train_regression.py --register
python ml/training/train_clustering.py --register

# 4. Démarrer/vérifier l'API d'inférence
uvicorn ml.serving.app:app --reload --port 8500   # http://localhost:8500/docs

# 5. Générer un rapport de dérive
python ml/monitoring/drift_report.py

# 6. (optionnel) Dashboards
docker compose up -d grafana                        # http://localhost:3001
```

📖 Détail complet de chaque commande : [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) §9.

**Consulter les résultats des notebooks sans rien exécuter** : ouvrir n'importe quel `.ipynb` dans
[`notebooks/`](./notebooks/) affiche directement ses résultats déjà calculés (graphiques,
tableaux, scores) — aucune exécution nécessaire pour les consulter.

---

## 10. Structure du repository

```
hm-retail-intelligence-platform/
├── README.md / README.fr.md      # ce fichier (EN / FR)
├── ARCHITECTURE.md               # diagramme technique détaillé, services Docker
├── docker-compose.yml            # orchestration de tous les services
├── .env.example                   # variables d'environnement à copier dans .env
├── run.sh / run.bat               # scripts de démarrage
│
├── notebooks/                     # ✅ implémenté — pipeline EDA → ML (§2)
├── data/raw/                      # ✅ utilisé — CSV Kaggle bruts
├── data/processed/, data/features/  # ❌ non utilisé par le code actuel
├── spark/                         # ✅ implémenté — pipeline batch → PostgreSQL (§3)
│                                   #    + pipeline streaming (§5)
├── ml/                             # ✅ implémenté — entraînement, MLflow, API, monitoring (§4)
├── kafka/                          # ✅ implémenté — producteur + API (§5) ; consumers/ vide (§8)
├── n8n/workflows/                  # ✅ implémenté — 3 workflows séparés (§5)
│   ├── hm-simulation-quotidienne-kafka.json
│   ├── hm-rfm-nocturne-notifications.json
│   └── hm-reentrainement-hebdomadaire.json
├── grafana/                        # ✅ implémenté — 5 dashboards, 25 panels (§6)
├── backend/app/                    # 📂 réservé — vide
└── frontend/src/                   # 📂 réservé — vide
```

---

## 11. Documentation complémentaire

| Document | Contenu |
|---|---|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Diagramme technique complet, rôle exact de chaque service Docker, distinction implémenté / non implémenté |
| [`spark/README.md`](./spark/README.md) | Pipeline Spark → PostgreSQL en détail (star schema, Data Marts, exécution, vue d'ensemble de l'orchestration n8n) |
| [`spark/batch_ml_pipeline/README.md`](./spark/batch_ml_pipeline/README.md) | Détails internes du pipeline batch : écriture JDBC, star schema, Data Marts, dépannage |
| [`spark/streaming_pipeline/README.md`](./spark/streaming_pipeline/README.md) | Détails internes du pipeline streaming : ingestion Kafka, validation, checkpointing |
| [`n8n/workflows/README.md`](./n8n/workflows/README.md) | Détail des 3 workflows n8n (nœuds, déclencheurs, services appelés, limitations connues) |
| [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) | Guide ML/MLOps complet : entraînement, MLflow, API de serving, monitoring, CI/CD, DVC |
| [`grafana/README.md`](./grafana/README.md) | Mise en place de Grafana, provisioning, dépannage |
| [`grafana/README_GRAFANA.md`](./grafana/README_GRAFANA.md) | Les 25 panels des dashboards avec leurs requêtes SQL |
| [`kafka/README.md`](./kafka/README.md) | Détail du producteur Kafka & de l'API |
| [`notebooks/README.md`](./notebooks/README.md) | Ordre d'exécution des notebooks, usage |
| [`notebooks/DETAILS.md`](./notebooks/DETAILS.md) | Méthodologie statistique détaillée, formules, résultats complets |