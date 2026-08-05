# HM Streaming Pipeline — Workflow n8n

Orchestration quotidienne du pipeline de données H&M : génération de transactions synthétiques, ingestion Kafka/Spark, calcul RFM nocturne, génération de rapport via LLM (Ollama), **ré-entraînement hebdomadaire des modèles ML** et diffusion multi-canal (SSE, chatbot, notifications push).


## Vue d'ensemble

Ce workflow n8n orchestre l'ensemble du pipeline de données du projet **HM-Retail-Intelligence-platform* basé sur le dataset H&M. Il combine trois boucles indépendantes :

| Boucle | Déclenchement | Rôle |
|---|---|---|
| **Streaming quotidien** | Tous les jours à **06:00** | Génère des transactions synthétiques, les publie sur Kafka, déclenche le job Spark streaming |
| **RFM nocturne** | Tous les jours à **02:00** | Fusionne les données streaming dans l'entrepôt, recalcule les scores RFM, génère un rapport IA et le diffuse aux clients (dashboard, chatbot, notifications) |
| **Ré-entraînement ML hebdomadaire** | Tous les **lundis à 06:00** (même cadence que `mlops-ci.yml`) | Ré-entraîne les 3 modèles (`ml/training/train_*.py`), promeut automatiquement le nouveau champion MLflow s'il est meilleur, recharge le cache de `ml-serving` et notifie |

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
| `ml-model-api` | 8000 | API de prédiction batch pour le rapport IA *(non déployée, nœud désactivé — reste à faire, voir Limites ci-dessous)* |
| `ml-training-trigger` | 8600 | **Nouveau** — déclenche les ré-entraînements et l'auto-promotion du champion MLflow (`ml/training/training_api.py`) |
| `ml-serving` | 8500 | API d'inférence (`ml/serving/app.py`) ; expose désormais aussi `POST /admin/reload-models` |
| `shopanalytics-django-api` | 8000 | Backend Django : SSE, chatbot RAG, notifications FCM |

## Limites connues restantes

- Le nœud `Appeler l'API modèle (prédiction) — à activer` (boucle RFM nocturne) pointe toujours vers un service `ml-model-api:8000/predict/batch` qui n'existe pas : `ml/serving/app.py` n'expose pour l'instant que des endpoints de prédiction unitaire (`/predict/club-status`, `/predict/segment`, `/predict/spend`), pas de variante batch. Ce nœud reste désactivé tant que cet endpoint batch n'est pas ajouté.
- Le seuil de décision "promu / non promu" compare uniquement au champion précédent (pas de seuil absolu minimal type "F1 < 0.2 → toujours refuser").