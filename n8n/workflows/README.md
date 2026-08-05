# Workflows n8n — H&M Retail Intelligence Platform

Orchestration du pipeline de données H&M : génération de transactions synthétiques, ingestion Kafka/Spark, calcul RFM nocturne, génération de rapport via LLM (Ollama), **ré-entraînement hebdomadaire des modèles ML** et diffusion multi-canal (SSE, chatbot, notifications push).

## Fichiers

Ces trois boucles étaient à l'origine un seul workflow (`HM Streaming Pipeline.json`). Elles sont
maintenant **séparées en 3 fichiers indépendants**, importables séparément dans n8n, car elles n'ont
aucune dépendance d'exécution entre elles (déclencheurs, horaires et échecs indépendants) :

| Fichier | Boucle | Déclenchement | Rôle |
|---|---|---|---|
| [`hm-simulation-quotidienne-kafka.json`](./hm-simulation-quotidienne-kafka.json) | **Streaming quotidien** | Tous les jours à **06:00** | Génère des transactions synthétiques, les publie sur Kafka, déclenche le job Spark streaming |
| [`hm-rfm-nocturne-notifications.json`](./hm-rfm-nocturne-notifications.json) | **RFM nocturne** | Tous les jours à **02:00** | Fusionne les données streaming dans l'entrepôt, recalcule les scores RFM, génère un rapport IA et le diffuse aux clients (dashboard, chatbot, notifications) |
| [`hm-reentrainement-hebdomadaire.json`](./hm-reentrainement-hebdomadaire.json) | **Ré-entraînement ML hebdomadaire** | Tous les **lundis à 06:00** (même cadence que `mlops-ci.yml`) | Ré-entraîne les 3 modèles (`ml/training/train_*.py`), promeut automatiquement le nouveau champion MLflow s'il est meilleur, recharge le cache de `ml-serving` et notifie |

Chaque fichier est un export n8n valide et autonome (`nodes` + `connections` propres), à importer
individuellement via *Import from File* dans n8n.

## Architecture du workflow

```
06:00 ─┬─ Déclencheur simulation quotidienne
       │
       ├─ Calculer la date simulée1 (Code)
       │
       ├─ Générer les transactions du jour (HTTP → generator_api:8089)
       │
       ├─ Déclencher le producer Kafka (HTTP → kafka-producer-api:8090)
       │
       └─ spark_pipeline_streaming 


02:00 ─┬─ Déclencheur RFM nocturne
       │
       ├─ Lancer merge_stream_to_warehouse.py (HTTP → spark-job-trigger:8091)
       │
       ├─ Lancer pipeline_hm.py --source=warehouse (HTTP → spark-job-trigger:8091)
       │
       ├─ Attendre la fin du recalcul RFM (Wait)
       │
       ├─  Appeler l'API modèle prédiction (HTTP → ml-model-api:8000)
       │
       ├─ Préparer Prompt Ollama (Code)
       │
       ├─ Basic LLM Chain (Ollama Model : llama3.2:3b-instruct-q4_K_M)
       │
       ├─ Formater Payload SSE (Code)
       │
       └─┬─ Push SSE → Django (dashboard temps réel)
         ├─ Envoyer au Chatbot (RAG Django)
         └─ Envoyer FCM (notification push mobile)


Lundi 06:00 ─┬─ Déclencheur ré-entraînement hebdomadaire
             │
             ├─ Lancer le ré-entraînement des 3 modèles (HTTP → ml-training-trigger:8600/train/all)
             │
             ├─ Analyser les résultats d'entraînement (Code — compare aux seuils/champion actuel)
             │
             ├─ Recharger les modèles (HTTP → ml-serving:8500/admin/reload-models)
             │
             └─ Notifier FCM - ré-entraînement terminé (HTTP → shopanalytics-django-api:8000)
```

## Déclencheurs

| Nœud | Type | Cron | Description |
|---|---|---|---|
| `Déclencheur - Simulation quotidienne` | Schedule Trigger | `0 6 * * *` | Démarre la boucle de génération/streaming chaque jour à 6h |
| `Déclencheur - RFM nocturne (02:00)` | Schedule Trigger | `0 2 * * *` | Démarre la boucle de fusion + calcul RFM + rapport IA chaque nuit à 2h |
| `Déclencheur - Ré-entraînement hebdomadaire (lundi 06:00)` | Schedule Trigger | `0 6 * * 1` | Démarre la boucle de ré-entraînement ML chaque lundi à 6h (même cadence que le cron `scheduled-retrain` de `.github/workflows/mlops-ci.yml`, mais ici pour la stack Docker locale) |

## Boucle de ré-entraînement ML (nouveau)

1. **Lancer le ré-entraînement des 3 modèles** — `POST http://ml-training-trigger:8600/train/all?register=true&promote=true`.
   Appelle en interne `ml/training/train_classification.py`, `train_regression.py` et `train_clustering.py` (aucune logique dupliquée), enregistre chaque run dans MLflow, puis compare la métrique clé du nouveau run (`f1_macro`, `rmse`, `silhouette_score` selon la tâche) à celle de l'alias `champion` actuel. Le nouveau modèle n'est promu `champion` que s'il est meilleur ou égal — c'est le garde-fou anti-régression décrit comme manquant dans `ml/MLOPS_GUIDE.md` §10.
2. **Analyser les résultats d'entraînement** (Code) — construit un résumé lisible (quel modèle a été promu, avec quelle métrique) et un indicateur `any_promoted`.
3. **Recharger les modèles** — `POST http://ml-serving:8500/admin/reload-models`. Nécessaire car l'API d'inférence met les modèles en cache mémoire au premier appel ; sans ce vidage de cache, un nouveau champion ne serait pris en compte qu'après redémarrage du conteneur `ml-serving`.
4. **Notifier FCM** — réutilise l'endpoint `shopanalytics-django-api:8000/api/send-fcm/` déjà utilisé par la boucle RFM nocturne, avec un payload `type: "model_retrain"`.

En cas d'échec d'un des 3 entraînements, `ml-training-trigger` renvoie un statut HTTP 500 avec le détail par tâche : le nœud HTTP Request n8n correspondant échoue alors et le workflow s'arrête avant de recharger `ml-serving` ou d'envoyer une notification (comportement voulu — pas de rechargement partiel/erroné).

## Services externes appelés

| Service | Port | Rôle |
|---|---|---|
| `generator_api` | 8089 | Génère les transactions synthétiques du jour |
| `kafka-producer-api` | 8090 | Publie les transactions sur Kafka |
| `shop-streaming-api` | 8000 | Job Spark Structured Streaming |
| `spark-job-trigger` | 8091 | Déclenche les jobs batch (merge warehouse, calcul RFM) |
| `ml-serving` | 8500 | API d'inférence (`ml/serving/app.py`) ; expose `/predict/club-status`, `/predict/segment`, `/predict/spend`, **`/predict/batch`**, et `POST /admin/reload-models` |
| `ml-training-trigger` | 8600 | Déclenche les ré-entraînements et l'auto-promotion du champion MLflow (`ml/training/training_api.py`) |
| `shopanalytics-django-api` | 8000 | Backend Django : SSE, chatbot RAG, notifications FCM |

## Scoring en masse pour le rapport IA — `POST /predict/batch`

Le nœud `Appeler l'API modèle (prédiction batch)` (boucle RFM nocturne) appelle désormais
`POST http://ml-serving:8500/predict/batch` (`ml/serving/app.py`), **implémenté et testé**
(`ml/tests/test_serving.py::test_predict_batch_*`), qui n'existait pas jusqu'ici (l'ancienne
version pointait vers un service `ml-model-api:8000` inexistant et restait désactivée).

Corps de requête (`source_table` et `limit` optionnels) :
```json
{"source_table": "customers_features_train"}
```

Réponse : un résumé agrégé (`BatchPredictionSummary`), pas des prédictions ligne par ligne — pensé
pour être directement injecté dans le prompt Ollama qui suit (`Préparer Prompt Ollama`, mis à jour
en conséquence pour consommer ces champs plutôt que les champs de prévision de fréquentation d'un
autre projet) :

```json
{
  "generated_at": "2026-08-05T02:03:11.123Z",
  "source_table": "customers_features_train",
  "n_customers_scored": 5000,
  "club_status_distribution": {"ACTIVE": 3421, "PRE-CREATE": 1102, "LEFT CLUB": 477},
  "dominant_club_status": "ACTIVE",
  "segment_distribution": {"0": 812, "1": 950, "2": 703, "3": 890, "4": 845, "5": 800},
  "dominant_segment": 1,
  "predicted_spend_mean": 187.42,
  "predicted_spend_median": 152.10,
  "predicted_spend_total": 937100.0,
  "model_versions": {"classification": "registry:champion", "clustering": "local", "regression": "local"}
}
```

**Ce qui reste une limite connue (hors périmètre de ce correctif)** : le nœud suivant `Push SSE →
Django` (et `Envoyer au Chatbot`, `Envoyer FCM`) pointe toujours vers un backend Django absent de ce
dépôt (voir `README.md` §2, projet `ShopAnalytics`). `Formater Payload SSE` produit donc un payload
correctement formé à partir des vraies données H&M, mais l'appel HTTP qui le consomme échouera tant
qu'aucun backend Django n'est déployé à l'URL configurée.

## Garde-fou de qualité pour la promotion automatique du champion

Contrairement à ce qu'indiquait une version précédente de cette page, la promotion automatique de
l'alias `champion` **n'est pas** une simple comparaison au champion précédent : `ml/training/
training_api.py` applique d'abord un **seuil de qualité absolu par tâche** (`QUALITY_GATES`), qui
bloque toute promotion si le nouveau modèle est en dessous — y compris quand il n'y a pas encore de
champion, ou quand le champion actuel est pire (deux cas qu'une comparaison purement relative ne
détecterait pas) :

| Tâche | Métrique | Seuil minimal |
|---|---|---|
| `classification` | `f1_macro` | 0.20 |
| `regression` | `r2_log_target` | 0.50 |
| `clustering` | `silhouette_score` | 0.10 |

Seulement si ce seuil est franchi, la métrique est comparée au champion actuel (lu via l'API MLflow)
et la promotion n'a lieu que si la nouvelle version est meilleure ou égale. Ce comportement est
couvert par `ml/tests/test_training_api.py` (garde-fou testé indépendamment de tout entraînement
réel ou accès réseau MLflow/PostgreSQL, via des fonctions d'entraînement factices).