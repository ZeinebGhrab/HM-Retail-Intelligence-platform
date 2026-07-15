# Architecture technique — H&M Retail Intelligence Platform

Ce document décrit **uniquement l'architecture réellement en place aujourd'hui** : le flux de
données qui fonctionne de bout en bout, le rôle exact de chaque service Docker qui le supporte, et
comment chaque brique s'articule avec les autres. Une section finale (§5) liste, séparément et sans
les présenter comme fonctionnelles, les briques encore à l'état d'emplacement réservé.

---

## 1. Le flux de données implémenté, schématisé

```
                         ┌──────────────────────────┐
   CSV Kaggle       ───▶ │   Notebooks (01 → 07)     │ ───▶ résultats déjà calculés dans les .ipynb
  (data/raw/)            │   nettoyage → EDA → ML    │      + ml/models/ (export direct des modèles 06-07)
                         └──────────────────────────┘

                         ┌──────────────────────────┐
   CSV Kaggle       ───▶ │   Spark (spark/jobs/,     │
  (data/raw/)            │   spark/utils/)           │
                         └───────────┬──────────────┘
                                     │ JDBC (écriture)
                                     ▼
                    ┌─────────────────────────────────┐
                    │   PostgreSQL                      │
                    │   schéma étoile + Data Marts       │
                    │   dont customers_features_train    │
                    └───────────┬─────────────────────┘
                                 │ SELECT (ml/common.py)
                                 ▼
                    ┌─────────────────────────────────┐
                    │   ml/training/train_*.py           │──▶ MLflow (tracking + Model Registry,
                    │   (classification, régression,     │    alias "champion")
                    │    clustering)                      │
                    └───────────┬─────────────────────┘
                                 │ models:/<nom>@champion (ou repli local ml/models/)
                                 ▼
                    ┌─────────────────────────────────┐
                    │   ml/serving/app.py                │──▶ /predict/club-status
                    │   (API FastAPI)                    │    /predict/segment
                    └─────────────────────────────────┘    /predict/spend

                    ┌─────────────────────────────────┐
                    │   ml/monitoring/drift_report.py     │──▶ rapport HTML de dérive (Evidently AI)
                    └─────────────────────────────────┘

CI/CD : .github/workflows/mlops-ci.yml (lint, tests, build image, ré-entraînement planifié)
```

**Point important à ne pas manquer** : les notebooks et le pipeline Spark partent des **mêmes CSV
bruts**, mais ce sont **deux chemins indépendants** qui ne s'exécutent pas l'un après l'autre :
- les notebooks produisent des résultats déjà visibles (analyse, modèles exportés directement) sur
  un instantané figé des données ;
- le pipeline Spark → PostgreSQL → `ml/` est le chemin « live », rejouable à volonté, qui alimente
  l'API de service.

Les deux appliquent le même nettoyage et les mêmes recettes de modèle, sans garantie stricte de
tourner sur exactement le même instantané de données au même instant (voir
`ml/MLOPS_GUIDE.md` §10).

---

## 2. Rôle détaillé de chaque brique implémentée

| Brique | Rôle | Comment ça fonctionne concrètement |
|---|---|---|
| `notebooks/` | Analyse complète EDA → feature engineering → ML | 7 notebooks exécutés dans l'ordre, chacun consommant la sortie du précédent (dossier `intermediate/`, généré à l'exécution). Les notebooks 06-07 exportent directement les modèles retenus vers `ml/models/`. |
| `data/raw/` | Entrée du pipeline Spark | CSV Kaggle bruts (`customers.csv`, `articles.csv`, `transactions_train.csv`), non versionnés dans Git pour l'instant (DVC configuré mais remote à finaliser, voir §5). |
| `spark/` | Transforme les CSV bruts en Data Warehouse PostgreSQL | `jobs/pipeline_hm.py` orchestre lecture (`utils/schemas.py`) → nettoyage (`utils/cleaning.py`) → feature engineering RFM (`utils/features.py`) → écriture JDBC. Détail complet : `spark/README.md`. |
| `ml/training/` | Entraîne les 3 modèles validés en notebook, de façon scriptée | Charge `customers_features_train` (PostgreSQL, avec repli synthétique), reproduit la recette exacte des notebooks 06-07, logge dans MLflow, `--register` pour le Model Registry. |
| `ml/serving/` | Expose les modèles via une API | FastAPI, charge `models:/<nom>@champion` (MLflow Registry) avec repli automatique sur `ml/models/*.joblib`. Ne se connecte jamais à PostgreSQL à l'inférence — les features arrivent dans la requête HTTP. |
| `ml/monitoring/` | Détecte la dérive des données | Compare une fenêtre de référence et une fenêtre courante de `customers_features_train` avec Evidently AI, génère un rapport HTML. |
| `.github/workflows/mlops-ci.yml` | CI/CD | Lint + tests à chaque push/PR touchant `ml/` ; build de l'image `ml-serving` sur `main` ; ré-entraînement + monitoring sur cron hebdomadaire (nécessite un runner avec accès réseau à PostgreSQL/MLflow, voir `ml/MLOPS_GUIDE.md` §7). |
| `docker-compose.yml` | Fait tourner les conteneurs des briques ci-dessus | Voir §3 pour le détail service par service. |

---

## 3. Services Docker qui supportent une brique implémentée

| Service | Image | Ce qu'il fait réellement aujourd'hui |
|---|---|---|
| `postgres` | `postgres:15-alpine` | Stocke le schéma en étoile + Data Marts produits par `spark/jobs/pipeline_hm.py`, dont `customers_features_train` |
| `adminer` | `adminer:latest` | Interface web pour consulter le contenu de PostgreSQL (`http://localhost:8081`) |
| `spark-master` / `spark-worker` | build local (`spark/Dockerfile`) | Exécutent `spark/jobs/pipeline_hm.py` |
| `mlflow` | `ghcr.io/mlflow/mlflow` | Serveur de tracking + Model Registry, utilisé par `ml/training/` et `ml/serving/` |
| `ml-serving` | build local (`ml/serving/Dockerfile`) | Fait tourner l'API FastAPI de `ml/serving/app.py` |

Tous communiquent sur le réseau Docker `shop_data_net`, via leur **nom de service** (`postgres`,
`mlflow`) — pas `localhost` — quand ils s'appellent entre eux à l'intérieur de Docker. Les volumes
nommés (`postgres_data`, `mlflow_data`) assurent la persistance entre redémarrages.

**Démarrage minimal de ces 5 services** :
```bash
docker compose up -d postgres adminer spark-master spark-worker mlflow ml-serving
```

---

## 4. Cas d'usage couverts par le flux implémenté

1. **Nettoyage & qualité des données clients** (imputation médiane/mode justifiée statistiquement) —
   notebook 01, repris dans `spark/utils/cleaning.py`.
2. **Exploration produits & transactions à grande échelle** (33,7M lignes de transactions) —
   notebook 02.
3. **Segmentation RFM enrichie** (météo, jours fériés) — notebook 03.
4. **Feature engineering client** — notebook 04, repris industriellement dans
   `spark/utils/features.py` → table `customers_features_train`.
5. **Réduction de dimension & clustering exploratoire** — notebook 05.
6. **Classification du statut club** (`club_member_status`, Random Forest) et **régression de la
   dépense totale** (`total_spend`, XGBoost) — notebook 06, reproduits par
   `ml/training/train_classification.py` et `train_regression.py`, servis par `ml/serving/`.
7. **Segmentation client** (K-Means, k=6) — notebook 07, reproduite par
   `ml/training/train_clustering.py`, servie par `ml/serving/`.

---

## 5. Ce qui n'est pas implémenté (pour référence, sans ambiguïté)

Ces éléments sont présents dans le dépôt (dossier, Dockerfile, ou service Docker qui démarre) mais
**ne contiennent aucune logique fonctionnelle connectée au reste** :

| Élément | État réel |
|---|---|
| `kafka/producers/`, `kafka/consumers/` | Dossiers vides (`.gitkeep`). Le service `kafka` démarre mais rien ne publie/consomme de messages. |
| `n8n/workflows/` | Dossier vide. Le service `n8n` démarre mais aucun workflow n'est défini. |
| `backend/app/` | Dossier vide. Aucune API applicative. |
| `frontend/src/` | Dossier vide. Aucune interface utilisateur. |
| Chatbot RAG (`ollama`, `qdrant`) | Services Docker qui démarrent, mais non connectés à une base de connaissances ni à un frontend. |
| `data/processed/`, `data/features/` | Non alimentés par le pipeline actif (héritage d'une version antérieure). |
| Remote DVC/DagsHub | `.dvc/config` contient un gabarit d'URL, à remplacer par le vrai dépôt DagsHub. |
| Publication de l'image Docker (`build-serving-image` en CI) | Le build fonctionne, mais la publication vers un registre d'images est pré-écrite en commentaire, pas activée. |

---

## 6. Comment contribuer à une brique non implémentée

1. Retirer le `.gitkeep` du dossier concerné une fois du contenu réel ajouté.
2. Respecter le rôle prévu pour ce dossier (ex. `kafka/producers/` ne doit que publier des
   événements, pas contenir de logique métier).
3. Mettre à jour ce document et `README.md` pour refléter le nouvel état — la règle du dépôt est
   qu'un dossier n'est jamais documenté comme « implémenté » tant qu'il n'exécute pas réellement ce
   qui est décrit.