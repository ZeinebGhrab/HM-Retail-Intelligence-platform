# H&M Retail Intelligence Platform

Plateforme data & IA autour du dataset Kaggle **H&M Personalized Fashion Recommendations** :
EDA/feature engineering/ML dans des notebooks, et une infrastructure temps réel (Kafka → Spark →
Postgres), orchestrée par n8n, avec un chatbot RAG (Ollama + Qdrant).

## Arborescence

```
hm-retail-intelligence-platform/
├── README.md                  # ce fichier
├── ARCHITECTURE.md            # architecture technique détaillée, cas d'usage, pile MLOps
├── docker-compose.yml         # orchestration de tous les services (racine, requis par Compose)
├── .env.example                # variables d'environnement à copier en .env
├── run.sh / run.bat            # scripts de démarrage (Linux/Mac / Windows)
│
├── notebooks/                  # Pipeline EDA -> feature engineering -> ML (7 notebooks, voir notebooks/README.md)
│   ├── 01...07_*.ipynb          # Notebooks source, déjà exécutés (sorties/graphiques embarqués)
│   ├── intermediate/              # (généré à l'exécution, non versionné) .pkl/.csv/.md entre notebooks
│   ├── README.md                 # Guide d'exécution de la série (ordre, dépendances, Colab)
│   └── DETAILS.md                # Documentation méthodologique détaillée (statistiques, choix ML)
│
├── data/                        # Données (non versionnées avec git, voir DVC dans ARCHITECTURE.md)
│   ├── raw/                     # CSV bruts Kaggle (customers, articles, transactions) — entrée du pipeline Spark
│   ├── processed/               # Non alimenté par le pipeline actif (voir ml/MLOPS_GUIDE.md §2)
│   └── features/                # Non alimenté par le pipeline actif — features désormais dans PostgreSQL
│
├── spark/                       # Pipeline batch Kaggle CSV -> Data Warehouse PostgreSQL (voir spark/README.md)
│   ├── Dockerfile, requirements.txt
│   ├── jobs/pipeline_hm.py       # Orchestration complète (ingestion -> nettoyage -> features -> écriture JDBC)
│   └── utils/                    # config.py, schemas.py, cleaning.py, features.py
│
├── kafka/                       # Ingestion temps réel des transactions
│   ├── Dockerfile, requirements.txt
│   ├── producers/                # Simulateurs / connecteurs qui publient sur les topics (à développer)
│   └── consumers/                # Consommateurs (ex. écriture vers Postgres/Spark) (à développer)
│
├── n8n/                          # Orchestration de workflows
│   └── workflows/                # Exports JSON des workflows n8n
│
├── ml/                            # Entraînement et service des modèles (branché sur PostgreSQL)
│   ├── config.yaml, common.py       # Config + connexion PostgreSQL (table customers_features_train)
│   ├── training/                    # Scripts d'entraînement (classification, régression, clustering)
│   ├── models/                      # Modèles sérialisés (gitignored), repli local hors MLflow Registry
│   ├── serving/                     # API FastAPI d'inférence
│   ├── monitoring/                  # Détection de dérive (Evidently AI)
│   ├── tests/                       # Tests pytest (smoke tests entraînement + API)
│   └── MLOPS_GUIDE.md               # Guide complet de cette partie
│
├── backend/                        # API applicative (FastAPI/Node, à définir)
│   └── app/
│
└── frontend/                        # Interface utilisateur (dashboard, chatbot RAG)
    └── src/
```

## Rôle détaillé de chaque dossier

Le projet a deux volets : un **volet analytique déjà implémenté** (les notebooks) et un **volet
plateforme temps réel encore au stade de scaffolding** (infrastructure Docker + dossiers de code
réservés). Le tableau ci-dessous précise le rôle et l'état de chacun ; voir `ARCHITECTURE.md`
pour le détail technique et les schémas de flux de données.

| Dossier | Rôle | État |
|---|---|---|
| **`notebooks/`** | Cœur analytique du projet : 7 notebooks Jupyter exécutés dans l'ordre couvrant nettoyage, EDA, enrichissement externe (météo/jours fériés), feature engineering RFM, export pour le chatbot RAG, et modélisation ML (réduction de dimension, classification, régression, clustering). Les `.ipynb` contiennent déjà les sorties de leur dernière exécution (graphiques, tableaux, scores). Le sous-dossier `intermediate/` (`.pkl`, `.csv`, `.md` passés d'un notebook à l'autre) est **généré localement à l'exécution** sur les données Kaggle réelles — il n'est pas versionné ici (voir l'encart en tête de `notebooks/README.md`). | ✅ Implémenté |
| **`data/`** | `raw/` : CSV Kaggle bruts, entrée du pipeline Spark (`spark/jobs/pipeline_hm.py`) — à versionner via DVC (voir `ARCHITECTURE.md` §4/`ml/MLOPS_GUIDE.md` §8). `processed/` et `features/` ne sont **plus alimentés par le pipeline actif** : les features clients vivent désormais dans la table PostgreSQL `customers_features_train` (voir `spark/README.md` et `ml/MLOPS_GUIDE.md` §2), pas dans ces dossiers. | ⚠️ `raw/` utilisé, `processed/`/`features/` obsolètes |
| **`spark/`** | Pipeline batch complet : lecture des CSV Kaggle (`data/raw/`), nettoyage (`utils/cleaning.py`), feature engineering RFM (`utils/features.py`), écriture d'un Data Warehouse en schéma étoile + Data Marts dans PostgreSQL via JDBC (`jobs/pipeline_hm.py`). Voir [`spark/README.md`](./spark/README.md) pour le détail complet. | ✅ Implémenté |
| **`kafka/`** | Ingestion temps réel des transactions/événements clients : `producers/` publie sur les topics (simulateurs ou connecteurs vers une source réelle), `consumers/` les lit pour alimenter Spark/PostgreSQL. `Dockerfile`/`requirements.txt` (confluent-kafka) prêts. | 🚧 Image Docker prête, producers/consumers à développer |
| **`n8n/workflows/`** | Orchestration des workflows métier (déclenchement des jobs Spark, rafraîchissement périodique de la base de connaissances RAG, alertes) via des exports JSON n8n. | 📂 Emplacement réservé |
| **`ml/`** | Passage des modèles validés en notebooks (05-07) à un usage servable, branché sur `customers_features_train` (PostgreSQL) : `training/` pour les scripts d'entraînement (avec tracking MLflow), `models/` pour le repli local des modèles, `serving/` pour l'API FastAPI d'inférence, `monitoring/` pour la détection de dérive (Evidently AI). Voir [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) pour le guide complet. | ✅ Implémenté |
| **`backend/app/`** | API applicative (FastAPI/Node, à définir) qui relie le frontend aux données PostgreSQL, aux modèles ML (`ml/serving/`) et au chatbot RAG (Ollama + Qdrant). | 📂 Emplacement réservé |
| **`frontend/src/`** | Interface utilisateur : dashboard analytique (segments clients, KPIs, tendances issus des notebooks) et interface du chatbot RAG. | 📂 Emplacement réservé |
| **`docker-compose.yml`** | Orchestration de tous les services d'infrastructure : Zookeeper, Kafka, PostgreSQL, Adminer, Spark (master + worker), n8n, Ollama, Qdrant, **MLflow** (tracking + registry) et **ml-serving** (API d'inférence) — voir le détail de chaque service dans `ARCHITECTURE.md`. | ✅ Implémenté |
| **`.env.example`** | Modèle des variables d'environnement (ports, identifiants PostgreSQL) à copier en `.env` avant de lancer `run.sh`/`run.bat`. `.env` ne doit jamais être commité. | ✅ Implémenté |
| **`run.sh` / `run.bat`** | Scripts de démarrage/arrêt des conteneurs, avec des sous-commandes ciblées (`all`, `infra`, `ml`, `kafka`, `spark`, `logs`, `status`, `down`, `clean`). | ✅ Implémenté |
| **`ARCHITECTURE.md`** | Architecture technique complète : schéma de flux de données, rôle de chaque service Docker, les 7 cas d'usage couverts par les notebooks, et la pile MLOps cible (Git, DVC, DagsHub, MLflow, GitHub Actions, Evidently AI). | ✅ Implémenté |

## Démarrage rapide

```bash
cp .env.example .env        # renseigner de vraies valeurs
./run.sh all                # ou run.bat all sous Windows
./run.sh status              # vérifier que les conteneurs tournent
```

Services démarrés : Zookeeper, Kafka, PostgreSQL, Adminer, Spark (master + worker), n8n, Ollama, Qdrant, MLflow, ml-serving.

Pour entraîner et servir les modèles ML sur les vraies données, exécuter ensuite le pipeline Spark
(voir [`spark/README.md`](./spark/README.md) §9) puis suivre [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md).

## Consulter les résultats sans rien exécuter

Le pipeline data science (notebooks 01 à 07) a déjà été exécuté de bout en bout : ouvrir
n'importe quel `.ipynb` du dossier [`notebooks/`](./notebooks/) dans Jupyter (ou sur GitHub, qui
les rend directement) affiche ses résultats — graphiques, tableaux, scores de modèles — sans rien
relancer. Les fichiers intermédiaires (`intermediate/*.pkl`, `customers_features.csv`,
`insights_summary.md`) ne sont en revanche **pas inclus dans ce dépôt** : ils dépendent des
données brutes Kaggle et sont régénérés à chaque exécution locale (voir l'encart en tête de
[`notebooks/README.md`](./notebooks/README.md)).

## Documentation complémentaire

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — architecture technique détaillée, rôle de chaque service
  Docker, cas d'usage couverts, pile MLOps cible.
- [`spark/README.md`](./spark/README.md) — pipeline Big Data Spark → PostgreSQL : schéma en étoile,
  Data Marts, lancement du job, cohérence avec l'EDA.
- [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) — guide complet de la partie MLOps : source de données
  (PostgreSQL), tracking et registre de modèles (MLflow), API de service (FastAPI), monitoring de
  dérive (Evidently AI), CI/CD (GitHub Actions).
- [`notebooks/README.md`](./notebooks/README.md) — ordre d'exécution de la série de notebooks,
  points méthodologiques, mode d'emploi sur Google Colab.
- [`notebooks/DETAILS.md`](./notebooks/DETAILS.md) — documentation méthodologique complète (choix
  statistiques, bibliothèques, structure détaillée du notebook original).