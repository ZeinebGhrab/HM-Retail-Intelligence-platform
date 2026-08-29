# `backend/app/` — Chatbot RAG client-spécifique

API FastAPI qui répond à des questions sur un client H&M précis (`customer_id`), en s'appuyant sur
Ollama (`qwen2.5:3b-instruct-q4_K_M`, retenu par [`backend/benchmark/`](../benchmark/README.md) —
voir `backend/benchmark/results/benchmark_report.json`, champ `winner`) pour le routage d'outils et
la génération de réponse.

---

## Fonctionnement

Pipeline à deux appels Ollama par question (voir `rag_pipeline.py`), même principe qu'un projet de
référence consulté en amont (Django, supprimé du dépôt depuis — servait uniquement d'inspiration, pas
une dépendance) :

1. **Routage** — le LLM reçoit la question et la liste des outils (`tools/SYSTEM_TOOL_CALLING`) et
   répond avec un JSON `{"tool": "...", "parameters": {...}}`.
2. **Exécution** — le backend exécute l'outil choisi en Python (`tools/run_tool`). `customer_id`
   vient **toujours** de la requête API, jamais du JSON renvoyé par le LLM — on ne fait pas
   confiance à un modèle pour retranscrire fidèlement un identifiant de 64 caractères.
3. **Génération** — le résultat de l'outil est injecté comme contexte dans un second appel Ollama,
   qui formule la réponse en langage naturel.

## Outils

| Outil | Source de données |
|---|---|
| `get_customer_profile` | Postgres (`customers_features_train`), repli CSV (`data/customers_features.csv`) |
| `compare_customer_to_segment` | idem + `data/customer_segments_summary.csv` |
| `predict_customer_spend` / `predict_customer_status` / `predict_customer_cluster` | `ml/serving/app.py` (`/predict/*`) — lookup client puis appel HTTP, `ml-serving` reste inchangé |
| `get_customer_purchase_history` / `get_customer_top_categories` | Postgres (`fact_transaction`) **uniquement** — pas de repli CSV, aucun fichier client × article × date n'a été exporté par les notebooks. Renvoie un message explicite si indisponible. |
| `semantic_search` | `data/insights_summary.md`, découpé par section `##`, embeddings via `Ollama /api/embeddings`, cosine similarity en Python pur (pas de Qdrant — corpus trop petit pour le justifier) |

## Données réelles vs repli

`data/` attend les exports du notebook 04 (§15) : `customers_features.csv`,
`products_performance.csv`, `daily_sales.csv` (+ `daily_sales_calendar_enriched.csv`),
`customer_segments_summary.csv`, `age_group_summary.csv`, `insights_summary.md`. Ce sont des CSV
figés (instantané des données au moment de l'export) — Postgres reste la source de vérité privilégiée
quand `customers_features_train` est peuplé et accessible.

⚠️ **Ces fichiers ne sont pas versionnés dans ce dépôt** (`customers_features.csv` seul pèse
~317 Mo — voir `data/.gitignore`), même convention que `data/raw/` et `notebooks/intermediate/` (voir
`notebooks/README.md`). À placer manuellement dans ce dossier avant de lancer le service — sans eux,
seuls les outils passant par Postgres/`ml-serving` fonctionnent ; `get_customer_profile`,
`compare_customer_to_segment` et `semantic_search` échoueront si Postgres est aussi indisponible.
`company_info.md` (rédigé à la main, pas un export) reste le seul fichier de `data/` suivi par git.

⚠️ Les valeurs de dépense (`total_spend`, `avg_basket_value`, prédictions de `predict_customer_spend`)
sont des **indices normalisés** (particularité du dataset Kaggle H&M — `price` n'est pas en devise
réelle), jamais affichés avec un symbole monétaire.

## Authentification

Aucune cette itération (décision du 2026-08-28) : `customer_id` est un champ explicite de la requête
`POST /chat/`, fourni par l'appelant (le frontend doit savoir quel client est sélectionné). Un module
d'authentification pourra être ajouté plus tard sans changer le contrat des outils — ils prennent déjà
`customer_id` en paramètre, pas une session.

## API

```
POST /chat/
{
  "question": "Quel est le profil du client 6d78cd0b...9a17 ?",
  "customer_id": "6d78cd0b0eb31e75f5c00b7458c7a5f4f4d5e6a1a9e6a3ce2b1f3ab9d84f9a17",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
}
```
→
```
{ "answer": "...", "model": "qwen2.5:3b-instruct-q4_K_M", "tool_used": "get_customer_profile" }
```

Consommé par [`frontend/`](../../frontend/README.md) (`src/services/chatApi.ts`), qui reprend le
contrat d'un ancien frontend Ionic consulté en amont (supprimé du dépôt depuis) étendu du seul champ
`customer_id`.

## Lancement local

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8600
```

Variables d'environnement (voir `config.py`) : `OLLAMA_HOST`, `OLLAMA_MODEL`, `ML_SERVING_URL`,
`POSTGRES_HOST`/`POSTGRES_PORT`/`POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD`, `APP_DATA_DIR`.
