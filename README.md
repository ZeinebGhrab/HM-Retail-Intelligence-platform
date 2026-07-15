# H&M Retail Intelligence Platform

Plateforme data & IA construite autour du dataset Kaggle **H&M Personalized Fashion
Recommendations**. Ce README ne décrit **que ce qui est réellement implémenté et fonctionnel
aujourd'hui**, avec une explication claire de son fonctionnement. Les briques non implémentées sont
listées séparément à la fin, sans être présentées comme opérationnelles.

---

## 1. Ce qui est implémenté, et comment ça fonctionne

### 1.1 Vue d'ensemble du flux de données réel

```
data/raw/*.csv (Kaggle : customers, articles, transactions)
        │
        ▼  spark-submit pipeline_hm.py
   PostgreSQL — schéma en étoile + Data Marts
   (table clé : customers_features_train)
        │
        ▼  ml/training/train_*.py --register
   MLflow — tracking d'expériences + Model Registry (alias "champion")
        │
        ▼  models:/<nom>@champion  (ou repli local ml/models/*.joblib)
   ml/serving/app.py — API FastAPI d'inférence (/predict/*)
        │
        ▼
   ml/monitoring/drift_report.py — rapport de dérive (Evidently AI)

En parallèle, indépendamment de ce flux temps réel :
notebooks/01→07 — pipeline EDA + ML complet sur un instantané CSV des mêmes données
```

Ce schéma est volontairement plus court que celui qu'on pourrait imaginer pour une plateforme
« retail intelligence » complète : il ne montre que ce qui tourne réellement aujourd'hui.

### 1.2 Le pipeline analytique — `notebooks/`

**Ce que c'est** : une série de 7 notebooks Jupyter, déjà exécutés sur les données Kaggle réelles
(résultats, graphiques et scores déjà visibles dans les fichiers `.ipynb`, sans rien relancer).

**Comment ça fonctionne** : chaque notebook lit les CSV Kaggle (`data/raw/`) ou les objets produits
par le notebook précédent (dossier `intermediate/`, généré à l'exécution, non versionné), applique
une étape du pipeline (nettoyage, EDA, enrichissement, feature engineering, modélisation), puis
exporte ses résultats pour le notebook suivant. Les notebooks 06 et 07 exportent en plus,
directement, les modèles retenus (`joblib.dump`) vers `ml/models/`.

**Détail complet** : [`notebooks/README.md`](./notebooks/README.md) (ordre d'exécution, mode
d'emploi) et [`notebooks/DETAILS.md`](./notebooks/DETAILS.md) (méthodologie).

### 1.3 Le pipeline Big Data — `spark/`

**Ce que c'est** : un job Spark batch qui transforme les 3 CSV Kaggle bruts en un Data Warehouse
PostgreSQL prêt à l'emploi.

**Comment ça fonctionne** : `spark/jobs/pipeline_hm.py` lit `data/raw/*.csv`, applique le nettoyage
(`spark/utils/cleaning.py` : imputation médiane/mode, tranches d'âge), calcule les features clients
RFM (`spark/utils/features.py` : récence, fréquence, montant, diversité d'achat) et écrit le tout
via JDBC dans PostgreSQL sous forme d'un schéma en étoile et de Data Marts — dont la table
`customers_features_train`, qui est **la seule source de vérité** consommée ensuite par `ml/`.

**Lancement** :
```bash
docker exec shop-spark-worker \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
  /opt/spark/work-dir/jobs/pipeline_hm.py
```

**Détail complet** : [`spark/README.md`](./spark/README.md).

### 1.4 Entraînement, tracking et service des modèles — `ml/`

**Ce que c'est** : les 3 modèles validés dans les notebooks 06-07 (classification du statut club,
régression de la dépense totale, segmentation client), rejoués de façon scriptée et industrialisée.

**Comment ça fonctionne**, étape par étape :
1. `ml/training/train_classification.py`, `train_regression.py`, `train_clustering.py` chargent
   `customers_features_train` depuis PostgreSQL (`ml/common.py`), ou basculent automatiquement sur
   un jeu de données synthétique de même schéma si la table est vide/inaccessible (utile en CI).
2. Chaque script reproduit exactement la recette validée dans les notebooks (mêmes hyperparamètres,
   même sélection de features), entraîne le modèle, et logge dans **MLflow** (paramètres, métriques,
   modèle) — avec `--register` pour l'enregistrer en plus dans le **Model Registry**.
3. `ml/serving/app.py` (API FastAPI) charge le modèle marqué avec l'alias `champion` dans le
   Registry, ou à défaut une copie locale dans `ml/models/`, et expose 3 routes de prédiction
   (`/predict/club-status`, `/predict/segment`, `/predict/spend`) plus `/health`.
4. `ml/monitoring/drift_report.py` compare une fenêtre de référence et une fenêtre courante de
   `customers_features_train` (Evidently AI) et génère un rapport HTML de dérive.
5. `.github/workflows/mlops-ci.yml` fait tourner lint + tests à chaque push, construit l'image
   Docker du service d'inférence sur `main`, et peut ré-entraîner/surveiller la dérive sur un cron
   hebdomadaire.

**Détail complet, avec toutes les commandes** : [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) — c'est
le document le plus détaillé du dépôt, à lire en premier pour tout ce qui concerne le ML.

### 1.5 Infrastructure Docker — `docker-compose.yml`

**Ce que c'est** : l'orchestration de tous les conteneurs nécessaires aux parties implémentées
ci-dessus (et de quelques briques d'infrastructure prêtes mais pas encore connectées à du code
applicatif, voir §2).

**Services qui supportent une partie implémentée et fonctionnelle** :

| Service | Rôle concret aujourd'hui |
|---|---|
| `postgres` | Stocke le Data Warehouse produit par `spark/jobs/pipeline_hm.py`, dont `customers_features_train` |
| `adminer` | Interface web pour consulter PostgreSQL (`http://localhost:8081`) |
| `spark-master` / `spark-worker` | Exécutent `spark/jobs/pipeline_hm.py` |
| `mlflow` | Serveur de tracking + Model Registry pour `ml/training/` et `ml/serving/` |
| `ml-serving` | Fait tourner l'API FastAPI de `ml/serving/app.py` en conteneur |

**Démarrage minimal pour le flux implémenté** (sans les services non encore branchés à du code) :
```bash
cp .env.example .env        # renseigner de vraies valeurs
docker compose up -d postgres adminer spark-master spark-worker mlflow ml-serving
```

**Démarrage complet de l'infrastructure du dépôt** (inclut aussi les services listés au §2,
présents dans `docker-compose.yml` mais pas encore consommés par du code applicatif) :
```bash
./run.sh all                # ou run.bat all sous Windows
./run.sh status              # vérifier que les conteneurs tournent
```

### 1.6 Résumé : démarrage rapide du flux réellement implémenté

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

# 4. Démarrer/consulter l'API d'inférence
uvicorn ml.serving.app:app --reload --port 8500   # http://localhost:8500/docs

# 5. Générer un rapport de dérive
python ml/monitoring/drift_report.py
```

Détail complet de chaque commande : [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) §9.

**Consulter les résultats des notebooks sans rien exécuter** : ouvrir n'importe quel `.ipynb` de
[`notebooks/`](./notebooks/) affiche directement ses résultats déjà calculés (graphiques, tableaux,
scores) — aucune exécution nécessaire pour les consulter.

---

## 2. Ce qui N'EST PAS implémenté aujourd'hui

Ces éléments existent dans le dépôt sous forme de dossiers/images Docker prêts, mais **ne
contiennent aucune logique fonctionnelle** — ce sont des emplacements réservés (`.gitkeep`), pas des
fonctionnalités opérationnelles :

| Dossier / service | État réel |
|---|---|
| `kafka/producers/`, `kafka/consumers/` | Dossiers vides. Le service Docker `kafka` démarre, mais rien ne publie ni ne consomme de messages : le pipeline Spark actuel lit directement les CSV, pas de flux Kafka. |
| `n8n/workflows/` | Dossier vide. Le service `n8n` démarre, mais aucun workflow n'y est défini. |
| `backend/app/` | Dossier vide. Aucune API applicative n'existe entre un frontend et les données/modèles. |
| `frontend/src/` | Dossier vide. Aucune interface utilisateur (dashboard, chatbot) n'existe. |
| Chatbot RAG (`ollama` + `qdrant`) | Les services Docker démarrent, mais rien ne les connecte à une base de connaissances ni à un frontend — le notebook 04 prépare des données qui *pourraient* servir à ce RAG, mais aucun code ne les y branche actuellement. |
| `data/processed/`, `data/features/` | Dossiers hérités d'une version antérieure du pipeline, non alimentés par le code actuel. |
| Remote DVC/DagsHub | `.dvc/config` contient un gabarit d'URL, pas encore pointé vers un vrai dépôt DagsHub. |

**Pourquoi les documenter quand même ?** Pour que personne ne perde de temps à chercher du code
qui n'existe pas, et pour que la prochaine personne qui reprend le projet sache exactement par où
commencer si elle veut développer l'une de ces briques.

---

## 3. Arborescence du dépôt

```
hm-retail-intelligence-platform/
├── README.md                   # ce fichier
├── ARCHITECTURE.md             # schéma technique détaillé, services Docker
├── docker-compose.yml          # orchestration de tous les services
├── .env.example                 # variables d'environnement à copier en .env
├── run.sh / run.bat             # scripts de démarrage
│
├── notebooks/                   # ✅ implémenté — pipeline EDA → ML (voir §1.2)
├── data/raw/                    # ✅ utilisé — CSV Kaggle bruts
├── data/processed/, data/features/  # ❌ non utilisés par le code actuel
├── spark/                       # ✅ implémenté — pipeline batch → PostgreSQL (voir §1.3)
├── ml/                           # ✅ implémenté — entraînement, MLflow, API, monitoring (voir §1.4)
├── kafka/                        # 📂 réservé — Dockerfile prêt, producers/consumers vides
├── n8n/workflows/                # 📂 réservé — vide
├── backend/app/                  # 📂 réservé — vide
└── frontend/src/                 # 📂 réservé — vide
```

---

## 4. Documentation complémentaire

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — schéma technique complet, rôle exact de chaque service
  Docker, distinction implémenté / non implémenté.
- [`spark/README.md`](./spark/README.md) — pipeline Spark → PostgreSQL en détail (schéma en étoile,
  Data Marts, lancement du job).
- [`ml/MLOPS_GUIDE.md`](./ml/MLOPS_GUIDE.md) — guide complet de la partie ML/MLOps : entraînement,
  MLflow, API de service, monitoring, CI/CD, DVC.
- [`notebooks/README.md`](./notebooks/README.md) — ordre d'exécution des notebooks, mode d'emploi.
- [`notebooks/DETAILS.md`](./notebooks/DETAILS.md) — méthodologie statistique détaillée.