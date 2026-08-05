# Guide MLOps — H&M Retail Intelligence Platform

Ce guide documente la mise en œuvre concrète de la pile MLOps annoncée dans `ARCHITECTURE.md` §5
(Git, DVC, DagsHub, MLflow, GitHub Actions, Evidently AI). Il fait passer le dossier `ml/` de
« emplacement réservé » à un pipeline exécutable de bout en bout : entraînement versionné et
tracké, service d'inférence, monitoring de dérive, CI/CD — **branché sur la vraie source de
données de la plateforme : la table PostgreSQL `customers_features_train`, produite par
`spark/jobs/pipeline_hm.py`** (pas un CSV).

> **À qui s'adresse ce guide ?** À toute personne qui reprend le projet après la mise en place du
> pipeline Spark → PostgreSQL et doit soit relancer les entraînements, soit brancher le
> backend/frontend sur les modèles, soit surveiller leur dérive en production.

---

## 1. Vue d'ensemble de la partie ML

```
data/raw/*.csv (Kaggle)
        │
        ▼  spark-submit pipeline_hm.py (voir spark/README.md)
┌─────────────────────────┐
│  PostgreSQL              │
│  customers_features_train│  ◀── table produite par compute_customer_features()
│  (+ dim_*, fact_*, marts)│      (spark/utils/features.py)
└──────────┬───────────────┘
           │  SELECT * FROM customers_features_train  (ml/common.py::load_customer_features)
           ▼
┌───────────────────────┐
│   ml/training/          │   train_classification.py  -> club_member_status
│   (scripts, --register) │   train_regression.py      -> total_spend
│                         │   train_clustering.py      -> segment (K-Means, k=6)
└───────────┬─────────────┘
           │  tracking (params, métriques, artefacts)
           ▼
┌───────────────────────┐
│   MLflow Tracking       │──▶ Model Registry (alias "champion")
│   Server (Docker)       │
└───────────┬─────────────┘
           │  models:/<nom>@champion
           ▼
┌───────────────────────┐        ┌──────────────────────────┐
│   ml/serving/app.py     │◀──────▶│  ml/models/*/*.joblib      │
│   (API FastAPI)          │       │  (repli local hors MLflow) │
└───────────┬─────────────┘        └──────────────────────────┘
           │ /predict/*
           ▼
       backend/app/  (API applicative, consomme ml/serving/)

┌───────────────────────┐
│   ml/monitoring/         │  Evidently AI : rapport de dérive
│   drift_report.py         │  (référence vs données courantes de customers_features_train)
└───────────────────────┘

Orchestration CI/CD : .github/workflows/mlops-ci.yml
```

Chaque script du dossier `ml/` reprend une logique déjà validée dans les notebooks (features,
prétraitement, choix des algorithmes) : voir `ml/config.yaml` pour la correspondance exacte avec
les notebooks 05-07, et les commentaires en tête de chaque script pour la section de notebook dont
il s'inspire.

**Ce que ce guide couvre :** la mise en place de l'outillage (accès Postgres, MLflow, CI/CD,
monitoring) et son usage. **Ce qu'il ne couvre pas :** la qualité prédictive des modèles eux-mêmes,
qui dépend des vraies données Kaggle et est discutée dans `notebooks/README.md` §3 et
`notebooks/DETAILS.md`.

---

## 2. La source des features : PostgreSQL, pas un CSV

**Point d'architecture important, à ne pas manquer** : le dossier `data/features/` du dépôt
**n'est plus alimenté par le pipeline actif**. `spark/jobs/pipeline_hm.py` lit les CSV Kaggle
depuis `data/raw/`, mais écrit exclusivement dans PostgreSQL (voir `spark/README.md` §5-7) — la
table `customers_features_train` (et les autres tables du schéma en étoile) sont donc **la seule
source de vérité** pour les features clients.

`ml/common.py::load_customer_features()` fait `SELECT * FROM customers_features_train` via
SQLAlchemy/psycopg2, avec ces colonnes (issues de `spark/utils/features.py::compute_customer_features`) :

| Colonne | Rôle |
|---|---|
| `customer_key` | Identifiant client (hash `crc32`, remplace `customer_id` dans l'entrepôt) — jamais utilisé comme feature |
| `age`, `age_group`, `club_member_status`, `fashion_news_frequency`, `postal_code` | Attributs démographiques (jointure avec `customers_clean`) |
| `total_spend`, `n_transactions`, `first_purchase`, `last_purchase` | RFM de base |
| `recency_days`, `tenure_days`, `avg_basket_value`, `purchase_frequency_per_month` | RFM dérivé |
| `n_distinct_categories` | Diversité d'achat |
| `segment_valeur` | Segment de valeur par quartile (`Bas (Q1)` → `Haut (Q4 - VIP)`), calculé par `approxQuantile` |

### Pré-requis avant d'entraîner sur les vraies données

1. Placer les 3 CSV Kaggle (`customers.csv`, `articles.csv`, `transactions_train.csv`) dans
   `data/raw/`.
2. Démarrer l'infrastructure : `./run.sh infra` (ou `./run.sh all`).
3. Exécuter le job Spark (voir `spark/README.md` §9) :
   ```bash
   docker exec shop-spark-worker \
     /opt/spark/bin/spark-submit \
     --master spark://spark-master:7077 \
     /opt/spark/work-dir/jobs/pipeline_hm.py
   ```
4. Vérifier que la table existe (via Adminer sur `http://localhost:8081`, ou `psql`) :
   ```sql
   SELECT count(*) FROM customers_features_train;
   ```
5. Seulement à partir de là, `ml/training/train_*.py` et `ml/serving/app.py` liront les vraies
   données. **Tant que cette table n'existe pas ou est vide**, `ml/common.py` bascule
   automatiquement sur un jeu de données synthétique de même schéma (avec un `WARNING` explicite en
   console) — pratique pour développer/tester sans dépendre du pipeline complet, mais à ne jamais
   confondre avec un entraînement réel.

### Variables de connexion (`.env`)

`ml/common.py` réutilise les variables PostgreSQL déjà définies pour le reste de la plateforme
(`POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`), plus une nouvelle variable
propre à `ml/` :

```bash
# .env
POSTGRES_HOST=localhost   # scripts ml/ lancés hors Docker (port publié sur l'hôte)
```

Le service `ml-serving` du `docker-compose.yml` (voir §5) force automatiquement
`POSTGRES_HOST=postgres` (nom du service Docker) — cette variable n'a besoin d'être positionnée
dans `.env` que pour une exécution des scripts `ml/training/`/`ml/serving/` **hors Docker**, sur un
poste de dev.

---

## 3. Deux façons d'obtenir les modèles entraînés

### 3.0 Voie directe (recommandée) : export depuis les notebooks

Les notebooks 06 et 07 contiennent, juste après la conclusion de chaque comparaison de modèles,
une cellule `joblib.dump(...)` qui exporte **le modèle effectivement retenu** (celui documenté
dans la synthèse §17.8) directement dans `ml/models/<tâche>/` du dépôt :

| Notebook | Cellule d'export (après…) | Fichiers produits |
|---|---|---|
| `06_ML_Classification_Regression.ipynb` | §17.5.1 (Random Forest optimisé), avant la section boosting/SMOTE 17.5.2 | `ml/models/classification/model.joblib`, `scaler.joblib` |
| `06_ML_Classification_Regression.ipynb` | §17.6.5 (analyse résiduelle), avant le nettoyage mémoire de fin de section | `ml/models/regression/model.joblib`, `scaler.joblib`, `selector.joblib`, `feature_columns.joblib` |
| `07_ML_Clustering_Approfondi_Synthese.ipynb` | §17.7.5 (synthèse du clustering), avant la synthèse générale 17.8 | `ml/models/clustering/model.joblib`, `scaler.joblib` |

**Marche à suivre :**
1. Exécuter la série 01 → 07 dans l'ordre sur les vraies données Kaggle (voir `notebooks/README.md`).
   Ces notebooks lisent encore les CSV Kaggle directement (`customers.csv`, etc. placés à côté du
   notebook ou sur Drive) — ils sont **indépendants** du pipeline Spark/PostgreSQL, qui est le
   chemin utilisé par `ml/training/` et le reste de la plateforme temps réel. Les deux chemins
   partent des mêmes CSV bruts et appliquent le même nettoyage, mais restent deux exécutions
   séparées (voir §7 "Limites").
2. Si les notebooks sont ouverts/exécutés **depuis le dossier `notebooks/`** (cas standard en local),
   les cellules d'export détectent automatiquement `../ml/models/` et y écrivent directement — rien
   d'autre à faire, `ml/serving/app.py` utilisera ces fichiers dès le prochain démarrage de l'API.
3. Sur Google Colab (ou toute exécution où `ml/` du dépôt n'est pas visible depuis le répertoire
   courant), les cellules détectent l'absence du dossier et exportent dans
   `<BASE_PATH>/ml_models_export/<tâche>/` à la place, avec un message explicite — il faut alors
   copier manuellement ce dossier vers `ml/models/` du dépôt.

Ces cellules exportent **exactement** l'objet modèle qui a servi à produire les métriques déjà
affichées dans le notebook (`gs_rf.best_estimator_`, `fitted_reg_v2[best_reg_v2_name][0]`,
`kmeans_v2`) — pas une réimplémentation. Aucun `label_encoder.joblib` n'est exporté pour la
classification : le `RandomForestClassifier` est entraîné directement sur les labels texte
(`club_member_status`), et `ml/serving/app.py` gère nativement ce cas (utilise `model.classes_`).

> **Pourquoi ces cellules n'existaient pas dès l'origine ?** Un notebook Jupyter (`.ipynb`) ne
> conserve que le code et les sorties déjà affichées (texte, graphiques) — jamais les objets Python
> entraînés en mémoire. Sans cellule d'export explicite, un modèle entraîné dans un notebook est
> irrécupérable une fois la session fermée.

### 3.1 Voie alternative : scripts `ml/training/` (CI, ré-entraînement automatisé, données Postgres)

Pour un ré-entraînement scriptable (CI/CD, cron, sans repasser par Jupyter) **et branché sur les
données à jour de la plateforme temps réel** (table `customers_features_train`, rafraîchie à
chaque exécution du pipeline Spark), les scripts `ml/training/train_*.py` reproduisent la même
recette exacte (mêmes hyperparamètres, même sélection de features) que les notebooks — voir tableau
récapitulatif au §4. Contrairement aux notebooks, ces scripts lisent PostgreSQL et non des CSV : ils
reflètent donc les données les plus récentes traitées par Spark, pas nécessairement celles vues au
moment de l'exécution des notebooks 01-07.

Les deux voies produisent des artefacts compatibles avec `ml/serving/app.py` (mêmes noms de
fichiers), donc interchangeables selon le contexte : notebooks pour une revue humaine avec
visualisations sur un instantané CSV, scripts pour l'automatisation sur les données live de
l'entrepôt.

---

## 4. Tracking d'expériences & Model Registry — MLflow

### Démarrer un serveur MLflow

En local avec Docker Compose (service `mlflow` ajouté à `docker-compose.yml`) :
```bash
cp .env.example .env      # si pas déjà fait — définit MLFLOW_PORT (5000 par défaut)
./run.sh ml                # démarre mlflow + ml-serving (ou ./run.sh all pour toute la stack)
```
L'UI est disponible sur `http://localhost:5000` : expériences, comparaison de runs, courbes de
métriques, registre de modèles.

En local sans Docker (poste de dev) :
```bash
pip install -r ml/requirements.txt
mlflow server --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlruns_artifacts --port 5000
export MLFLOW_TRACKING_URI=http://localhost:5000   # ou le mettre dans .env
```

> **Pourquoi SQLite/Postgres et pas le backend fichier (`./mlruns`) ?** Les versions récentes de
> MLflow ont mis le backend fichier en maintenance : le Model Registry (nécessaire pour `--register`)
> exige un backend base de données. `sqlite:///mlflow.db` suffit pour un usage local ; en production,
> pointer vers la base PostgreSQL déjà présente dans `docker-compose.yml` (créer un schéma/une base
> dédiée à MLflow, distincte de `hm_retail`, pour ne pas mélanger tracking ML et données métier).

### Lancer un entraînement (avec tracking, données PostgreSQL si disponibles)
```bash
python ml/training/train_classification.py            # tracke le run, sans enregistrer le modèle
python ml/training/train_classification.py --register  # + enregistre dans le Model Registry
python ml/training/train_regression.py --register
python ml/training/train_clustering.py --register
```
Chaque script :
1. charge la table `customers_features_train` depuis PostgreSQL (ou génère un jeu synthétique de
   même schéma si la connexion échoue ou si la table est vide — pratique en CI/démo, voir
   avertissement affiché dans la console) ;
2. reproduit le prétraitement du notebook correspondant (standardisation, one-hot, sélection de
   features pour la régression) ;
3. entraîne **exactement le modèle retenu dans le notebook** (voir tableau ci-dessous), pas une
   réimplémentation approximative — les hyperparamètres viennent directement des résultats déjà
   exécutés dans les notebooks 06-07 ;
4. logge dans MLflow : hyperparamètres, métriques (F1-macro/accuracy, RMSE/MAE/R², silhouette),
   et le modèle lui-même (flavor MLflow adapté à l'algorithme) ;
5. sauvegarde aussi une copie locale dans `ml/models/<tâche>/` pour le repli hors-MLflow de l'API
   de service (§5).

### Modèles reproduits (issus des notebooks 06-07, pas de réimplémentation « à l'estime »)

| Tâche | Modèle retenu | Provenance | Résultat (notebook) |
|---|---|---|---|
| Classification `club_member_status` | `RandomForestClassifier(n_estimators=200, max_depth=20, min_samples_leaf=5, class_weight="balanced")` — **sans SMOTE** | `best_params_` exact de `GridSearchCV`, notebook 06 §17.5.1 | F1-macro=0.3889 (bat CatBoost+SMOTE à 0.3652, §17.5.2) |
| Régression `total_spend` | `SelectKBest(f_regression, k=12)` puis `XGBRegressor(random_state=42)` (hyperparamètres par défaut) sur `log1p(total_spend)` | Notebook 06 §17.6.2 et §17.6.4 | R²(test, log)=0.943 |
| Clustering | `KMeans(n_clusters=6, n_init=10)` | Notebook 07 §17.7.2 (bat GMM et hiérarchique en silhouette) | Silhouette=0.2537 |

> **Point d'attention** : les notebooks 06/07 n'exportaient eux-mêmes aucun modèle entraîné avant
> les cellules ajoutées au §3.0 (pas de `joblib.dump`/`pickle.dump` sur les modèles finaux à
> l'origine) — seule la synthèse §17.8 documentait le vainqueur de chaque comparaison. Les scripts
> `ml/training/` ré-exécutent donc la même recette (mêmes hyperparamètres, même sélection de
> features, même cible transformée) pour produire un artefact réellement servable à partir des
> données PostgreSQL, au lieu de repartir sur des choix différents.

### Promouvoir un modèle en production (alias)
MLflow 2.9+ remplace les anciens "stages" (Staging/Production) par des **alias**. Après avoir
comparé plusieurs runs dans l'UI MLflow et choisi le meilleur :
```bash
mlflow models set-alias hm-club-status-classifier champion 3   # promeut la version 3
```
`ml/serving/app.py` charge systématiquement `models:/<nom>@champion` : changer l'alias suffit à
déployer une nouvelle version sans toucher au code de service ni redéployer l'API.

### Noms des modèles enregistrés
Définis dans `ml/config.yaml` :
| Tâche | Nom dans le Registry |
|---|---|
| Classification `club_member_status` | `hm-club-status-classifier` |
| Régression `total_spend` | `hm-spend-regressor` |
| Clustering / segmentation | `hm-customer-segmentation` |

---

## 5. Service d'inférence — `ml/serving/`

### Lancer l'API en local
```bash
pip install -r ml/requirements.txt
uvicorn ml.serving.app:app --reload --port 8500
```
Documentation interactive auto-générée : `http://localhost:8500/docs`.

### Endpoints
| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | Statut de l'API + disponibilité de chaque modèle |
| POST | `/predict/club-status` | Prédit `club_member_status` (ACTIVE / PRE-CREATE / LEFT CLUB) + probabilités |
| POST | `/predict/segment` | Prédit le cluster K-Means (0 à 5) |
| POST | `/predict/spend` | Prédit `total_spend` (dépense totale estimée) |

Exemple d'appel :
```bash
curl -X POST http://localhost:8500/predict/club-status \
  -H "Content-Type: application/json" \
  -d '{"age": 34, "n_transactions": 27, "tenure_days": 540, "n_distinct_categories": 6,
       "avg_basket_value": 42.5, "purchase_frequency_per_month": 1.8, "recency_days": 12}'
```

### Stratégie de chargement des modèles
1. **MLflow Model Registry**, via l'alias `champion` (`models:/<nom>@champion`), si
   `MLFLOW_TRACKING_URI` pointe vers un serveur MLflow joignable.
2. **Repli local automatique** sur `ml/models/<tâche>/*.joblib` sinon (poste de dev sans MLflow
   lancé, ou premier déploiement avant configuration complète du Registry — y compris les
   artefacts déposés directement par les cellules d'export des notebooks, §3.0).

Cela permet de développer et tester l'API sans dépendre en permanence d'un serveur MLflow actif.
Le champ `model_version` de chaque réponse indique quelle source a été utilisée
(`"registry:champion"` ou `"local"`), utile pour le débogage et les tableaux de bord de monitoring.

**Important** : `ml/serving/app.py` sert des modèles déjà entraînés (`ml/models/` ou le Registry) —
il n'interroge PostgreSQL qu'au moment de l'entraînement (`ml/training/`) ou du monitoring
(`ml/monitoring/`), jamais à l'inférence. Les features nécessaires à une prédiction sont fournies
dans le corps de la requête HTTP par l'appelant (typiquement `backend/app/`, qui les aura
lui-même lues depuis PostgreSQL ou calculées à la volée).

### Docker
```bash
docker build -t hm-ml-serving ml/
docker run -p 8500:8500 -e MLFLOW_TRACKING_URI=http://mlflow:5000 hm-ml-serving
```
Ou, dans la stack complète : `./run.sh ml` (démarre `mlflow` + `ml-serving`, tous deux ajoutés à
`docker-compose.yml`, avec `POSTGRES_HOST=postgres` positionné automatiquement pour `ml-serving`).

### Intégration avec `backend/app/`
Le backend applicatif (FastAPI/Node, à développer) doit simplement appeler ces 3 endpoints en HTTP
interne (`http://ml-serving:8500/predict/...` dans le réseau Docker `shop_data_net`), sans jamais
charger de modèle lui-même : cela garde la responsabilité du chargement/versionning des modèles
entièrement dans `ml/`.

---

## 6. Monitoring de la dérive — Evidently AI

### Pourquoi
Le comportement client évolue (saisonnalité, soldes, nouveaux segments) : un modèle entraîné sur un
instantané des données se dégrade avec le temps (*data drift* / *concept drift*). Evidently AI
compare une fenêtre de référence (données d'entraînement) à une fenêtre courante et quantifie la
dérive colonne par colonne.

### Générer un rapport
```bash
# Référence = un échantillon de customers_features_train (PostgreSQL) au moment de l'exécution.
# Sans --current : simule une fenêtre "courante" avec une dérive volontaire (vieillissement de la
# base, baisse de fréquence d'achat) à titre de démonstration.
python ml/monitoring/drift_report.py

# Avec un extrait réel de données plus récentes (ex. ré-export de customers_features_train après
# une nouvelle exécution du pipeline Spark sur des données Kaggle mises à jour) :
python ml/monitoring/drift_report.py --current data/processed/customers_recent.csv
```
Le rapport HTML est généré dans `ml/monitoring/reports/drift_report.html` (ouvrable dans un
navigateur) et un résumé (part de colonnes en dérive, alerte si au-dessus du seuil défini dans
`ml/config.yaml` → `monitoring.drift_share_threshold`) est affiché en console — exploitable comme
condition de déclenchement d'un ré-entraînement automatique en CI (§7).

### Limite actuelle liée au caractère batch du pipeline Spark
Le dataset Kaggle H&M est un instantané historique figé : `spark/jobs/pipeline_hm.py` le rejoue en
mode batch (`mode("overwrite")`, toute la table est recalculée à chaque exécution), il n'y a pas
encore de flux Kafka réellement branché qui ferait évoluer `customers_features_train` en continu
(voir `kafka/producers/` et `kafka/consumers/`, encore à implémenter). Tant que ce flux temps réel
n'existe pas, "référence" et "courant" proviennent de la même exécution batch — le monitoring
fonctionne aujourd'hui en mode exploratoire/simulé (paramètre `--current`), pas encore sur un vrai
flux de données évolutif.

---

## 7. CI/CD — `.github/workflows/mlops-ci.yml`

Trois jobs :

1. **`lint-and-test`** (à chaque push/PR touchant `ml/`) : `ruff check` puis `pytest ml/tests/`.
   Les tests s'exécutent sur le jeu de données synthétique de repli (`ml/common.py`), donc **aucune
   base PostgreSQL n'est nécessaire en CI** — ils valident que le pipeline (features → prétraitement →
   entraînement → tracking → service) reste exécutable de bout en bout, pas la qualité prédictive.

2. **`build-serving-image`** (sur push vers `main`, après succès des tests) : construit l'image
   Docker de `ml/serving/`. La publication vers un registre d'images (GHCR, Docker Hub…) est
   pré-écrite en commentaire, à activer une fois le registre cible choisi.

3. **`scheduled-retrain`** (cron hebdomadaire + déclenchement manuel) : génère le rapport de
   dérive et ré-entraîne/enregistre les 3 modèles dans le Model Registry MLflow, **en lisant
   `customers_features_train` sur une instance PostgreSQL accessible depuis le runner**. Un runner
   GitHub-hosted classique ne peut pas atteindre un `docker-compose` lancé en local sur un
   ordinateur : ce job suppose soit un runner **self-hosted** sur le même réseau que la stack, soit
   une instance PostgreSQL/MLflow de staging/prod exposée avec des identifiants dédiés en secrets.
   Reste "best effort" tant que ces secrets ne sont pas configurés (repli automatique sur les
   données synthétiques, comme en local).

### Secrets GitHub à configurer (Settings → Secrets and variables → Actions)
| Secret | Utilisé pour |
|---|---|
| `MLFLOW_TRACKING_URI` | Pointer le ré-entraînement planifié vers le serveur MLflow de production |
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Lire `customers_features_train` sur l'instance PostgreSQL de production/staging |
| `DAGSHUB_USER` / `DAGSHUB_TOKEN` | `dvc pull` des CSV bruts versionnés depuis DagsHub (optionnel, voir §8) |

---

## 8. Versioning des données brutes — DVC + DagsHub (portée réduite)

DVC dans ce projet **ne verse pas les features** (elles vivent dans PostgreSQL, pas dans un
fichier) : sa portée se limite aux **CSV Kaggle bruts** (`data/raw/`), consommés en entrée par
`spark/jobs/pipeline_hm.py`.

```bash
# Une fois (déjà fait dans ce dépôt, voir .dvc/) :
dvc init

# Déclarer le remote DagsHub (déjà pré-rempli dans .dvc/config, à adapter) :
dvc remote modify dagshub url https://dagshub.com/<user>/HM-Retail-Intelligence-platform.dvc
dvc remote modify dagshub --local auth basic
dvc remote modify dagshub --local user <votre_user_dagshub>
dvc remote modify dagshub --local password <votre_token_dagshub>

# Versionner les CSV Kaggle bruts
dvc add data/raw/customers.csv data/raw/articles.csv data/raw/transactions_train.csv
git add data/raw/*.dvc .gitignore
git commit -m "Versionne les données brutes Kaggle (DVC)"
dvc push
```

`dvc.yaml` déclare les étapes d'entraînement (`train_classification`, `train_regression`,
`train_clustering`, `drift_report`) avec le **code** comme dépendance (scripts, `common.py`,
`config.yaml`) — pas la table Postgres, que DVC ne peut pas suivre comme un fichier. Concrètement,
`dvc repro` rejoue un entraînement si le code change, mais ne détecte **pas** un changement de
contenu de `customers_features_train` (nouvelle exécution du pipeline Spark). Pour forcer un
ré-entraînement après une mise à jour des données, utiliser `dvc repro --force`, ou déclencher les
stages explicitement (n8n, CI planifiée) après le job Spark — voir le commentaire en tête de
`dvc.yaml`.

---

## 9. Démarrage rapide (résumé)

**Option A — voie directe (recommandée si vous avez les données Kaggle) :** exécuter les
notebooks 01 → 07 dans l'ordre (`notebooks/README.md`). Les cellules d'export de 06 et 07 déposent
automatiquement les 3 modèles dans `ml/models/`. Passer directement à l'étape 4 ci-dessous.

**Option B — pipeline complet Spark → PostgreSQL → scripts (recommandé pour la plateforme temps réel) :**

```bash
# 0. Dépendances Python + infrastructure
pip install -r ml/requirements.txt
cp .env.example .env
./run.sh infra                  # démarre kafka, postgres, adminer, qdrant, n8n, mlflow

# 1. Placer les CSV Kaggle dans data/raw/, puis exécuter le pipeline Spark
docker exec shop-spark-worker \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
  /opt/spark/work-dir/jobs/pipeline_hm.py

# 2. Entraîner les 3 modèles (lit customers_features_train depuis PostgreSQL)
python ml/training/train_classification.py --register
python ml/training/train_regression.py --register
python ml/training/train_clustering.py --register

# 3. Promouvoir les versions retenues (après revue dans l'UI MLflow sur http://localhost:5000)
mlflow models set-alias hm-club-status-classifier champion 1
mlflow models set-alias hm-spend-regressor champion 1
mlflow models set-alias hm-customer-segmentation champion 1
```

**Dans les deux cas ensuite :**

```bash
# 4. Démarrer l'API d'inférence
uvicorn ml.serving.app:app --reload --port 8500
# -> http://localhost:8500/docs

# 5. Générer un rapport de dérive
python ml/monitoring/drift_report.py

# 6. Lancer les tests
pytest ml/tests/ -v
ruff check ml/ --exclude ml/models
```

---

## 10. Limites actuelles & prochaines étapes

- **Deux chemins de données non unifiés** : les notebooks (§3.0) lisent des CSV Kaggle
  directement, tandis que les scripts `ml/training/` (§3.1) lisent la table PostgreSQL produite par
  Spark. Les deux appliquent le même nettoyage/les mêmes bins d'âge (vérifié colonne par colonne),
  mais restent deux exécutions indépendantes — pas de garantie qu'elles tournent exactement sur le
  même instantané de données à un instant donné.
- **Pas encore de split temporel strict** pour l'entraînement (héritage des notebooks, voir
  `notebooks/README.md` §3) : à corriger avant un vrai passage en production (entraîner sur le
  passé, valider sur une fenêtre plus récente, pour éviter la fuite d'information temporelle).
- **`spark/jobs/pipeline_hm.py` est un job batch** (`mode("overwrite")`, tout est recalculé à
  chaque exécution) : pas de flux Kafka réellement branché à ce jour (`kafka/producers/` et
  `kafka/consumers/` sont encore des emplacements réservés) — le monitoring de dérive (§6)
  fonctionne donc en mode exploratoire/simulé faute de flux temps réel alimentant en continu
  `customers_features_train`.
- **La voie notebook (§3.0) n'enregistre rien dans MLflow** : elle écrit directement les fichiers
  dans `ml/models/`, sans passer par le tracking d'expériences ni le Model Registry (pas de
  comparaison de runs, pas d'alias `champion` associé). Pour une traçabilité complète, ré-exécuter
  ensuite `python ml/training/train_*.py --register` avec les mêmes données, ou logger le modèle
  exporté manuellement via `mlflow.sklearn.log_model()` dans une cellule additionnelle.
- **Le remote DVC DagsHub** dans `.dvc/config` est un gabarit (`<user>`) à remplacer par le vrai
  dépôt DagsHub du projet.
- **La publication de l'image Docker** (`build-serving-image`) n'est pas branchée à un registre
  réel — les lignes sont pré-écrites en commentaire dans le workflow, à activer avec un registre et
  des secrets choisis par l'équipe.
- ~~Tests de qualité prédictive (seuils minimaux avant `--register`) non automatisés~~ — **résolu** :
  `ml/training/training_api.py` (`POST /train/<tâche>` et `/train/all`) applique désormais un seuil
  de qualité absolu par tâche (`QUALITY_GATES` : `f1_macro ≥ 0.20`, `r2_log_target ≥ 0.50`,
  `silhouette_score ≥ 0.10`) qui bloque toute promotion `champion` en dessous — y compris en
  l'absence de champion actuel — puis compare au champion existant via l'API MLflow avant de
  promouvoir. Testé indépendamment dans `ml/tests/test_training_api.py`. Ce endpoint est appelé par
  le workflow n8n `hm-reentrainement-hebdomadaire.json` (voir `n8n/workflows/README.md`).
  Reste néanmoins à ajuster : les seuils sont des valeurs de départ volontairement basses (bloquer
  un modèle clairement cassé, pas exiger de battre le score des notebooks) — à durcir une fois un
  historique de runs disponible en production.