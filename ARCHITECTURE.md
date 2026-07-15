# Architecture technique — H&M Retail Intelligence Platform

Ce document décrit l'architecture cible de la plateforme, l'état d'avancement de chaque brique,
et la manière dont les dossiers du dépôt s'articulent entre eux. Il complète `README.md` (vue
d'ensemble) et `notebooks/README.md` (détail du pipeline data science).

---

## 1. Vue d'ensemble

Le projet a deux volets qui partagent le même dataset (H&M Personalized Fashion Recommendations)
mais des objectifs différents :

1. **Volet analytique (implémenté)** — la série de 7 notebooks (`notebooks/`) : nettoyage, EDA,
   enrichissement externe, feature engineering RFM, et modélisation ML (classification, régression,
   clustering). C'est la partie la plus avancée du projet à ce jour.
2. **Volet plateforme temps réel** — l'infrastructure définie dans `docker-compose.yml` (Kafka,
   Spark, PostgreSQL, Adminer, n8n, Ollama, Qdrant, MLflow, ml-serving) et les dossiers de code
   associés. **`spark/`** (pipeline batch Kaggle → Data Warehouse PostgreSQL, voir §2 et
   `spark/README.md`) et **`ml/`** (entraînement + service des modèles, voir §2 et
   `ml/MLOPS_GUIDE.md`) sont désormais implémentés. `kafka/producers`, `kafka/consumers`,
   `n8n/workflows`, `backend/app`, `frontend/src` restent des emplacements réservés (`.gitkeep`).
   **Point d'architecture important** : `spark/jobs/pipeline_hm.py` écrit exclusivement dans
   PostgreSQL (schéma en étoile + Data Marts, dont `customers_features_train`) — les dossiers
   `data/processed/` et `data/features/` ne sont **plus alimentés** par le pipeline actif ; seul
   `data/raw/` (CSV Kaggle bruts, entrée du job Spark) reste utilisé.

```
                         ┌─────────────────────────┐
   Données Kaggle  ───▶  │   Notebooks (batch)      │  ───▶  insights_summary.md + CSV agrégés
  (customers, articles,  │   01 → 07                │        (base de connaissances RAG)
   transactions)         └─────────────────────────┘        + ml/models/ (cellules d'export 06-07)
          │
          │ data/raw/*.csv
          ▼
   ┌────────────┐   topics   ┌─────────────┐   JDBC   ┌────────────────────┐        ┌──────────────┐
   │   Kafka     │ ─────────▶ │   Spark     │ ───────▶ │ PostgreSQL          │        │  ml/serving   │
   │ (producers/ │  (à venir) │ (jobs/,     │          │ (schéma étoile +    │◀──────▶│  (API infér.) │
   │ consumers/) │            │  utils/)    │          │  customers_features_│  SQL   └──────┬───────┘
   └────────────┘            └─────────────┘          │  train, voir §2.3)  │               │
                                                        └────────────────────┘        ml/training/ +
                                                                                       ml/monitoring/

   ┌────────────┐        ┌────────────┐        ┌───────────┐        ┌─────────────────────┐
   │    n8n      │ ─────▶ │  Ollama     │ ─────▶ │  Qdrant   │ ─────▶ │  frontend (dashboard  │
   │ (workflows) │        │ (LLM local) │        │ (vecteurs)│        │  + chatbot RAG)       │
   └────────────┘        └────────────┘        └───────────┘        └─────────────────────┘
                                                                                        ▲
                                                                            backend/ (API applicative)
```

---

## 2. Rôle détaillé de chaque dossier

| Dossier | Rôle | État |
|---|---|---|
| `notebooks/` | Pipeline complet EDA → feature engineering → ML sur les 3 fichiers Kaggle. Sept notebooks numérotés, déjà exécutés (sorties/graphiques embarqués), exécutables à nouveau dans l'ordre (voir `notebooks/README.md`). Les notebooks 06 et 07 contiennent désormais des cellules d'export (`joblib.dump`) qui déposent directement les modèles retenus dans `ml/models/` (voir `ml/MLOPS_GUIDE.md` §3.0). Le sous-dossier `intermediate/` (`.pkl`/`.csv`/`.md` passés d'un notebook à l'autre) est généré localement à l'exécution sur les données Kaggle réelles et n'est pas versionné dans ce dépôt. | ✅ Implémenté |
| `data/raw/` | CSV bruts Kaggle (`customers.csv`, `articles.csv`, `transactions_train.csv`) — entrée du job Spark (`spark/jobs/pipeline_hm.py`). Non versionnés dans Git (poids trop important) — voir §5 DVC. | ⚠️ Utilisé, non versionné (DVC à activer) |
| `data/processed/`, `data/features/` | **Non alimentés par le pipeline actif** : le job Spark écrit exclusivement dans PostgreSQL (voir `spark/jobs/pipeline_hm.py`, section "STOCKAGE"), pas de sortie Parquet/CSV dans ces dossiers malgré leur présence dans l'arborescence (héritage d'une version antérieure du pipeline, code correspondant laissé en commentaire en tête du fichier). | ❌ Obsolète / non utilisé |
| `spark/` | Pipeline batch complet : `config.py` (SparkSession + config JDBC), `schemas.py` (schémas explicites des 3 CSV), `cleaning.py` (nettoyage : imputation médiane/mode, `age_group`), `features.py` (RFM + Data Marts), `jobs/pipeline_hm.py` (orchestration ingestion → nettoyage → jointures → feature engineering → écriture JDBC du schéma en étoile + Data Marts, dont `customers_features_train`). Voir `spark/README.md` pour le détail complet (schéma étoile, Data Marts, `approxQuantile`). | ✅ Implémenté |
| `kafka/producers/`, `kafka/consumers/` | Simulateurs/connecteurs qui publieraient les événements de transactions/comportement client sur les topics Kafka, et les consommateurs qui les liraient pour alimenter Spark/PostgreSQL en continu. `Dockerfile` et `requirements.txt` (confluent-kafka) prêts ; le pipeline Spark actuel lit directement les CSV de `data/raw/`, sans passer par Kafka. | 📂 Emplacement réservé |
| `n8n/workflows/` | Exports JSON des workflows n8n orchestrant le pipeline (déclenchement des jobs Spark, rafraîchissement du RAG, alertes). | 📂 Emplacement réservé |
| `ml/config.yaml`, `ml/common.py` | Configuration centrale (features, hyperparamètres des modèles retenus) et connexion à PostgreSQL (`SELECT * FROM customers_features_train`), avec repli sur des données synthétiques si la table est vide/inaccessible. | ✅ Implémenté |
| `ml/training/` | Scripts d'entraînement (classification `club_member_status`, régression `total_spend`, clustering), reproduisant exactement les modèles retenus dans les notebooks 06–07, avec tracking MLflow (`--register`). | ✅ Implémenté |
| `ml/models/` | Modèles sérialisés (gitignorés) : déposés soit par les cellules d'export des notebooks 06-07, soit par `ml/training/train_*.py` — source de vérité alternative au MLflow Model Registry. | ✅ Implémenté (généré à l'entraînement) |
| `ml/serving/` | API FastAPI d'inférence qui expose les modèles entraînés au backend : `models:/<nom>@champion` (MLflow Model Registry) avec repli automatique sur `ml/models/`. | ✅ Implémenté |
| `ml/monitoring/` | Détection de dérive des données (Evidently AI) sur `customers_features_train` : comparaison référence vs données courantes, rapport HTML + alerte si seuil dépassé. | ✅ Implémenté |
| `backend/app/` | API applicative (FastAPI/Node, à définir) qui relie le frontend aux résultats ML, aux données PostgreSQL et au chatbot RAG. | 📂 Emplacement réservé |
| `frontend/src/` | Interface utilisateur : dashboard analytique (segments clients, KPIs, tendances) et interface du chatbot RAG. | 📂 Emplacement réservé |
| `docker-compose.yml` | Orchestration de l'ensemble des services d'infrastructure (racine du dépôt, requis par Docker Compose), y compris `mlflow` et `ml-serving` (voir §3). | ✅ Implémenté |
| `.env.example` | Variables d'environnement (ports, identifiants PostgreSQL, MLflow, DagsHub) à copier en `.env` avant `run.sh`. | ✅ Implémenté |
| `run.sh` / `run.bat` | Scripts de démarrage/arrêt des conteneurs (`all`, `infra`, `ml`, `kafka`, `spark`, `logs`, `status`, `down`, `clean`). | ✅ Implémenté |

---

## 3. Services d'infrastructure (`docker-compose.yml`)

| Service | Image | Rôle |
|---|---|---|
| `zookeeper` | `confluentinc/cp-zookeeper` | Coordination du cluster Kafka |
| `kafka` | `confluentinc/cp-kafka` | Bus d'événements pour les transactions/comportements clients en temps réel |
| `postgres` | `postgres:15-alpine` | Data Warehouse (schéma étoile + Data Marts, dont `customers_features_train`) — voir `spark/README.md` |
| `adminer` | `adminer` | Interface web légère de consultation de PostgreSQL (`http://localhost:8081`) |
| `spark-master` / `spark-worker` | build local (`spark/Dockerfile`) | Pipeline batch : lecture des CSV Kaggle, nettoyage, feature engineering RFM, écriture PostgreSQL via JDBC |
| `n8n` | `n8nio/n8n` | Orchestration des workflows (déclenchement de jobs, alertes, rafraîchissement RAG) |
| `ollama` | `ollama/ollama` | LLM local servant le chatbot RAG |
| `qdrant` | `qdrant/qdrant` | Base vectorielle contenant les embeddings de la base de connaissances RAG (issue du notebook 04) |
| `mlflow` | `ghcr.io/mlflow/mlflow` | Tracking d'expériences ML et Model Registry (voir `ml/MLOPS_GUIDE.md` §4) |
| `ml-serving` | build local (`ml/Dockerfile`) | API FastAPI d'inférence exposant les modèles entraînés (voir `ml/MLOPS_GUIDE.md` §5) |

Tous les services communiquent sur le réseau bridge `shop_data_net`. Les volumes nommés
(`postgres_data`, `n8n_data`, `ollama_data`, `qdrant_data`, `mlflow_data`) assurent la persistance des données
entre redémarrages.

---

## 4. Cas d'usage couverts

1. **Nettoyage & qualité des données clients** — imputation justifiée statistiquement (médiane/mode
   selon skewness, kurtosis, test D'Agostino-Pearson) — notebook 01.
2. **Exploration produits & transactions à grande échelle** — traitement par blocs de 33,7M lignes
   de transactions — notebook 02.
3. **Segmentation RFM enrichie** — analyse Fréquence x Montant, enrichissement météo (Open-Meteo)
   et jours fériés (Nager.Date) — notebook 03.
4. **Feature engineering & base de connaissances RAG** — table de features clients, impact des
   périodes de soldes, export pour le chatbot — notebook 04.
5. **Réduction de dimension & clustering exploratoire** — PCA, t-SNE/UMAP, K-Means rapide —
   notebook 05.
6. **Prédiction supervisée** — classification du statut club (`club_member_status`, Random Forest
   optimisé par GridSearchCV) et régression du montant dépensé (`total_spend`, XGBoost +
   `SelectKBest`) — notebook 06. Plusieurs stratégies de rééquilibrage (SMOTE + boosting) ont été
   comparées pour la classification mais écartées : le Random Forest sans SMOTE reste le meilleur
   sur ce jeu de données (voir `ml/MLOPS_GUIDE.md` §4).
7. **Segmentation client approfondie** — clustering K-Means/GMM/hiérarchique (k=6 validé par
   silhouette), interprétation par arbre de décision pour des équipes métier non-techniques —
   notebook 07.

Ces sept cas d'usage sont implémentés en mode notebook, **et** reproduits/automatisables via
`ml/training/` sur les données live de la plateforme (table PostgreSQL `customers_features_train`,
alimentée par `spark/jobs/pipeline_hm.py`) — voir `ml/MLOPS_GUIDE.md`. Restent au stade de
scaffolding : l'ingestion Kafka temps réel (`kafka/producers`, `kafka/consumers`), l'orchestration
n8n, et le backend/frontend applicatifs.

---

## 5. Pile MLOps

| Outil | Rôle | État |
|---|---|---|
| **Git** | Versioning du code (notebooks, jobs Spark, API, frontend) | ✅ |
| **DVC** | Versioning des CSV Kaggle bruts (`data/raw/`) sans les committer dans Git — pipeline déclaré dans `dvc.yaml`. Les features (`customers_features_train`) vivent dans PostgreSQL, pas dans un fichier : hors du périmètre de DVC (voir `ml/MLOPS_GUIDE.md` §8) | ✅ Configuré (`.dvc/`, `dvc.yaml`), portée volontairement réduite |
| **DagsHub** | Hébergement combiné Git + DVC + expériences, pour la collaboration data science | 🚧 Remote gabarit dans `.dvc/config`, à pointer vers le vrai dépôt DagsHub du projet |
| **MLflow** | Tracking des expériences ML (métriques, hyperparamètres) et registre de modèles, via alias `champion` | ✅ Implémenté (`ml/training/`, service `mlflow` du docker-compose) |
| **Docker / docker-compose** | Conteneurisation de tous les services d'infrastructure, y compris `mlflow` et `ml-serving` (voir §3) | ✅ |
| **GitHub Actions** | CI/CD : lint + tests (`ml/tests/`), build de l'image `ml-serving`, ré-entraînement planifié + monitoring | ✅ Implémenté (`.github/workflows/mlops-ci.yml`) |
| **Evidently AI** | Monitoring de la dérive des données sur `customers_features_train` | ✅ Implémenté (`ml/monitoring/drift_report.py`), mode exploratoire faute de flux Kafka temps réel |

> Guide détaillé de mise en œuvre et d'utilisation de cette pile : **[`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md)**.
> Voir aussi `notebooks/README.md` §3 pour les limites actuelles des modèles eux-mêmes (pas de
> split temporel) que cette pile ne corrige pas automatiquement — elle outille le ré-entraînement
> et le monitoring, la méthodologie de modélisation reste celle validée dans les notebooks 05-07.

---

## 6. Comment contribuer à un dossier scaffold

Pour implémenter une des briques marquées « 📂 Emplacement réservé » ci-dessus :

1. Retirer le `.gitkeep` du dossier concerné une fois du contenu réel ajouté.
2. Respecter le rôle du dossier tel que décrit au §2 (ex. ne pas mettre de logique métier dans
   `kafka/producers/`, qui ne doit que publier des événements).
3. Mettre à jour ce document (`ARCHITECTURE.md`) et `README.md` si le rôle ou l'état d'un dossier
   change.