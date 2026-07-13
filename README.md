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
│   ├── raw/                     # CSV bruts Kaggle (customers, articles, transactions)
│   ├── processed/               # Données nettoyées / jointes (sorties notebooks 01-02)
│   └── features/                # Tables de features prêtes pour le ML (sortie notebook 04)
│
├── spark/                       # Traitement batch/streaming à grande échelle
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── jobs/                    # Jobs Spark (ex. agrégations, feature pipelines)
│   └── utils/                   # Fonctions partagées entre jobs
│
├── kafka/                       # Ingestion temps réel des transactions
│   ├── producers/                # Simulateurs / connecteurs qui publient sur les topics
│   └── consumers/                # Consommateurs (ex. écriture vers Postgres/Spark)
│
├── n8n/                          # Orchestration de workflows
│   └── workflows/                # Exports JSON des workflows n8n
│
├── ml/                            # Entraînement et service des modèles
│   ├── training/                  # Scripts d'entraînement (classification, régression, clustering)
│   ├── models/                    # Modèles sérialisés (gitignored, gérés via MLflow Registry)
│   └── serving/                   # Code de service des modèles (API d'inférence)
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
| **`data/`** | Emplacement standard des données du projet, jamais versionné directement dans Git (voir stratégie DVC dans `ARCHITECTURE.md`) : `raw/` pour les CSV Kaggle bruts, `processed/` pour les données nettoyées/jointes issues des notebooks 01-02, `features/` pour la table de features RFM prête pour le ML (notebook 04). | 📂 Emplacement réservé |
| **`spark/`** | Traitement batch/streaming à grande échelle : lecture des topics Kafka, agrégations, écriture vers PostgreSQL. `Dockerfile` et `requirements.txt` (PySpark, confluent-kafka, psycopg2) sont prêts ; `jobs/` (jobs Spark) et `utils/` (fonctions partagées) sont à écrire, en s'inspirant des agrégations déjà validées dans les notebooks. | 🚧 Image Docker prête, jobs à développer |
| **`kafka/`** | Ingestion temps réel des transactions/événements clients : `producers/` publie sur les topics (simulateurs ou connecteurs vers une source réelle), `consumers/` les lit pour alimenter Spark/PostgreSQL. | 📂 Emplacement réservé |
| **`n8n/workflows/`** | Orchestration des workflows métier (déclenchement des jobs Spark, rafraîchissement périodique de la base de connaissances RAG, alertes) via des exports JSON n8n. | 📂 Emplacement réservé |
| **`ml/`** | Passage des modèles validés en notebooks (05-07) à un usage servable : `training/` pour les scripts d'entraînement réutilisables, `models/` pour les modèles sérialisés (gitignoré, géré via MLflow Registry), `serving/` pour l'API d'inférence exposée au backend. | 📂 Emplacement réservé |
| **`backend/app/`** | API applicative (FastAPI/Node, à définir) qui relie le frontend aux données PostgreSQL, aux modèles ML (`ml/serving/`) et au chatbot RAG (Ollama + Qdrant). | 📂 Emplacement réservé |
| **`frontend/src/`** | Interface utilisateur : dashboard analytique (segments clients, KPIs, tendances issus des notebooks) et interface du chatbot RAG. | 📂 Emplacement réservé |
| **`docker-compose.yml`** | Orchestration de tous les services d'infrastructure : Zookeeper, Kafka, PostgreSQL, Spark (master + worker), n8n, Ollama, Qdrant — voir le détail de chaque service dans `ARCHITECTURE.md`. | ✅ Implémenté |
| **`.env.example`** | Modèle des variables d'environnement (ports, identifiants PostgreSQL) à copier en `.env` avant de lancer `run.sh`/`run.bat`. `.env` ne doit jamais être commité. | ✅ Implémenté |
| **`run.sh` / `run.bat`** | Scripts de démarrage/arrêt des conteneurs, avec des sous-commandes ciblées (`all`, `infra`, `kafka`, `spark`, `logs`, `status`, `down`, `clean`). | ✅ Implémenté |
| **`ARCHITECTURE.md`** | Architecture technique complète : schéma de flux de données, rôle de chaque service Docker, les 7 cas d'usage couverts par les notebooks, et la pile MLOps cible (Git, DVC, DagsHub, MLflow, GitHub Actions, Evidently AI). | ✅ Implémenté |

## Démarrage rapide

```bash
cp .env.example .env        # renseigner de vraies valeurs
./run.sh all                # ou run.bat all sous Windows
./run.sh status              # vérifier que les conteneurs tournent
```

Services démarrés : Zookeeper, Kafka, PostgreSQL, Spark (master + worker), n8n, Ollama, Qdrant.

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
- [`notebooks/README.md`](./notebooks/README.md) — ordre d'exécution de la série de notebooks,
  points méthodologiques, mode d'emploi sur Google Colab.
- [`notebooks/DETAILS.md`](./notebooks/DETAILS.md) — documentation méthodologique complète (choix
  statistiques, bibliothèques, structure détaillée du notebook original).