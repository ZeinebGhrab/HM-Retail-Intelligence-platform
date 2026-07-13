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
2. **Volet plateforme temps réel (scaffolding / à implémenter)** — l'infrastructure définie dans
   `docker-compose.yml` (Kafka, Spark, PostgreSQL, n8n, Ollama, Qdrant) et les dossiers de code
   associés (`spark/`, `kafka/`, `ml/`, `n8n/`, `backend/`, `frontend/`). Ces dossiers contiennent
   pour l'instant essentiellement des `.gitkeep` (hors `spark/Dockerfile` et
   `spark/requirements.txt`) : ce sont des emplacements réservés dans l'arborescence, pas encore
   du code fonctionnel.

```
                         ┌─────────────────────────┐
   Données Kaggle  ───▶  │   Notebooks (batch)      │  ───▶  data/processed, data/features
  (customers, articles,  │   01 → 07                │        + intermediate/ (pickle inter-notebooks)
   transactions)         └─────────────────────────┘
                                     │
                                     ▼
                         insights_summary.md + CSV agrégés (base de connaissances RAG)
                                     │
                                     ▼
   ┌────────────┐   topics   ┌─────────────┐   jobs   ┌────────────┐        ┌──────────────┐
   │   Kafka     │ ─────────▶ │   Spark     │ ───────▶ │ PostgreSQL │        │  ml/serving   │
   │ (producers/ │            │ (jobs/,     │          │ (features, │◀──────▶│  (API infér.) │
   │ consumers/) │            │  utils/)    │          │  résultats)│        └──────────────┘
   └────────────┘            └─────────────┘          └────────────┘                │
                                                                                        ▼
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
| `notebooks/` | Pipeline complet EDA → feature engineering → ML sur les 3 fichiers Kaggle. Sept notebooks numérotés, déjà exécutés (sorties/graphiques embarqués), exécutables à nouveau dans l'ordre (voir `notebooks/README.md`). Le sous-dossier `intermediate/` (`.pkl`/`.csv`/`.md` passés d'un notebook à l'autre) est généré localement à l'exécution sur les données Kaggle réelles et n'est pas versionné dans ce dépôt. | ✅ Implémenté |
| `data/raw/` | CSV bruts Kaggle (`customers.csv`, `articles.csv`, `transactions_train.csv`). Non versionnés (poids trop important) — voir §4 DVC. | 📂 Emplacement réservé |
| `data/processed/` | Données nettoyées/jointes issues des notebooks 01–02 (ex. `customers_cleaned.csv`). | 📂 Emplacement réservé |
| `data/features/` | Tables de features prêtes pour le ML (ex. table RFM enrichie du notebook 04). | 📂 Emplacement réservé |
| `spark/` | Traitement batch/streaming à grande échelle : lecture des topics Kafka, agrégations, écriture vers PostgreSQL. `Dockerfile` et `requirements.txt` (PySpark 3.5.1, confluent-kafka, psycopg2) sont prêts ; `jobs/` (jobs Spark) et `utils/` (fonctions partagées) sont à écrire. | 🚧 Image Docker prête, jobs à développer |
| `kafka/producers/` | Simulateurs ou connecteurs qui publient les événements de transactions/comportement client sur les topics Kafka. | 📂 Emplacement réservé |
| `kafka/consumers/` | Consommateurs qui lisent les topics et écrivent vers Spark/PostgreSQL. | 📂 Emplacement réservé |
| `n8n/workflows/` | Exports JSON des workflows n8n orchestrant le pipeline (déclenchement des jobs Spark, rafraîchissement du RAG, alertes). | 📂 Emplacement réservé |
| `ml/training/` | Scripts d'entraînement (classification `club_member_status`, régression `total_spend`, clustering), reprenant la logique validée dans les notebooks 05–07 pour un usage en production/CI. | 📂 Emplacement réservé |
| `ml/models/` | Modèles sérialisés. Gitignorés : gérés via un registre de modèles (MLflow Registry), pas commités directement. | 📂 Emplacement réservé (gitignored) |
| `ml/serving/` | Code de l'API d'inférence qui expose les modèles entraînés (prédiction de statut club, de dépense, de segment) au backend. | 📂 Emplacement réservé |
| `backend/app/` | API applicative (FastAPI/Node, à définir) qui relie le frontend aux résultats ML, aux données PostgreSQL et au chatbot RAG. | 📂 Emplacement réservé |
| `frontend/src/` | Interface utilisateur : dashboard analytique (segments clients, KPIs, tendances) et interface du chatbot RAG. | 📂 Emplacement réservé |
| `docker-compose.yml` | Orchestration de l'ensemble des services d'infrastructure (racine du dépôt, requis par Docker Compose). | ✅ Implémenté |
| `.env.example` | Variables d'environnement (ports, identifiants PostgreSQL) à copier en `.env` avant `run.sh`. | ✅ Implémenté |
| `run.sh` / `run.bat` | Scripts de démarrage/arrêt des conteneurs (`all`, `infra`, `kafka`, `spark`, `logs`, `status`, `down`, `clean`). | ✅ Implémenté |

---

## 3. Services d'infrastructure (`docker-compose.yml`)

| Service | Image | Rôle |
|---|---|---|
| `zookeeper` | `confluentinc/cp-zookeeper` | Coordination du cluster Kafka |
| `kafka` | `confluentinc/cp-kafka` | Bus d'événements pour les transactions/comportements clients en temps réel |
| `postgres` | `postgres:15-alpine` | Stockage des données traitées, features, et résultats de prédiction |
| `spark-master` / `spark-worker` | build local (`spark/Dockerfile`) | Traitement batch/streaming (lecture Kafka, agrégations, écriture PostgreSQL) |
| `n8n` | `n8nio/n8n` | Orchestration des workflows (déclenchement de jobs, alertes, rafraîchissement RAG) |
| `ollama` | `ollama/ollama` | LLM local servant le chatbot RAG |
| `qdrant` | `qdrant/qdrant` | Base vectorielle contenant les embeddings de la base de connaissances RAG (issue du notebook 04) |

Tous les services communiquent sur le réseau bridge `shop_data_net`. Les volumes nommés
(`postgres_data`, `n8n_data`, `ollama_data`, `qdrant_data`) assurent la persistance des données
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
6. **Prédiction supervisée** — classification du statut club (`club_member_status`, avec SMOTE face
   au déséquilibre de classes) et régression du montant dépensé (`total_spend`) — notebook 06.
7. **Segmentation client approfondie** — clustering K-Means/GMM/hiérarchique (k=6 validé par
   BIC/AIC), interprétation par arbre de décision pour des équipes métier non-techniques —
   notebook 07.

Ces sept cas d'usage sont aujourd'hui implémentés en mode batch/notebook. Le passage à la
plateforme temps réel (Kafka → Spark → PostgreSQL, orchestrée par n8n, servie via `ml/serving/` et
`backend/`) est l'étape suivante de la feuille de route.

---

## 5. Pile MLOps (cible)

| Outil | Rôle prévu |
|---|---|
| **Git** | Versioning du code (notebooks, jobs Spark, API, frontend) |
| **DVC** | Versioning des données volumineuses (`data/raw/`, `data/processed/`, `data/features/`) sans les committer dans Git |
| **DagsHub** | Hébergement combiné Git + DVC + expériences, pour la collaboration data science |
| **MLflow** | Tracking des expériences ML (métriques, hyperparamètres) et registre de modèles (`ml/models/`) |
| **Docker / docker-compose** | Conteneurisation de tous les services d'infrastructure (déjà en place, voir §3) |
| **GitHub Actions** | CI/CD : tests, linting, ré-exécution automatisée des notebooks, build des images Docker |
| **Evidently AI** | Monitoring de la dérive des données et de la performance des modèles en production |

> Cette pile MLOps est la cible visée pour faire passer le projet de « pipeline notebook » à
> « plateforme production ». Voir `notebooks/README.md` §3 pour les limites actuelles des modèles
> (pas de split temporel, pas de versioning, échantillon plutôt que full-scale par défaut) que
> cette pile doit adresser.

---

## 6. Comment contribuer à un dossier scaffold

Pour implémenter une des briques marquées « 📂 Emplacement réservé » ci-dessus :

1. Retirer le `.gitkeep` du dossier concerné une fois du contenu réel ajouté.
2. Respecter le rôle du dossier tel que décrit au §2 (ex. ne pas mettre de logique métier dans
   `kafka/producers/`, qui ne doit que publier des événements).
3. Mettre à jour ce document (`ARCHITECTURE.md`) et `README.md` si le rôle ou l'état d'un dossier
   change.