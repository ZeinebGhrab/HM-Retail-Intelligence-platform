# HM Streaming Pipeline — Workflow n8n

Orchestration quotidienne du pipeline de données H&M : génération de transactions synthétiques, ingestion Kafka/Spark, calcul RFM nocturne, génération de rapport via LLM (Ollama) et diffusion multi-canal (SSE, chatbot, notifications push).


## Vue d'ensemble

Ce workflow n8n orchestre l'ensemble du pipeline de données du projet **HM-Retail-Intelligence-platform* basé sur le dataset H&M. Il combine deux boucles indépendantes :

| Boucle | Déclenchement | Rôle |
|---|---|---|
| **Streaming quotidien** | Tous les jours à **06:00** | Génère des transactions synthétiques, les publie sur Kafka, déclenche le job Spark streaming |
| **RFM nocturne** | Tous les jours à **02:00** | Fusionne les données streaming dans l'entrepôt, recalcule les scores RFM, génère un rapport IA et le diffuse aux clients (dashboard, chatbot, notifications) |

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
```

## Déclencheurs

| Nœud | Type | Cron | Description |
|---|---|---|---|
| `Déclencheur - Simulation quotidienne` | Schedule Trigger | `0 6 * * *` | Démarre la boucle de génération/streaming chaque jour à 6h |
| `Déclencheur - RFM nocturne (02:00)` | Schedule Trigger | `0 2 * * *` | Démarre la boucle de fusion + calcul RFM + rapport IA chaque nuit à 2h |


## Services externes appelés

| Service | Port | Rôle |
|---|---|---|
| `generator_api` | 8089 | Génère les transactions synthétiques du jour |
| `kafka-producer-api` | 8090 | Publie les transactions sur Kafka |
| `shop-streaming-api` | 8000 | Job Spark Structured Streaming |
| `spark-job-trigger` | 8091 | Déclenche les jobs batch (merge warehouse, calcul RFM) |
| `ml-model-api` | 8000 | API de prédiction ML *(non déployée, nœud désactivé)* |
| `shopanalytics-django-api` | 8000 | Backend Django : SSE, chatbot RAG, notifications FCM |

