# ============================================================
# config.py — H&M Retail Intelligence — Chatbot backend (backend/app/)
# Configuration centrale : hôtes des services, chemins des données,
# modèle Ollama retenu par le benchmark (backend/benchmark/).
# ============================================================
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", APP_DIR / "data"))

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")

# Modèle retenu par backend/benchmark/ (score 97/100, recommended=true) —
# voir backend/benchmark/results/benchmark_report.json -> "winner".
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b-instruct-q4_K_M")

# Modèle dédié pour /api/embed — découvert en test réel (2026-08-29) que
# qwen2.5:3b-instruct (modèle de chat) renvoie une erreur 500/"does not
# support embeddings" sur cette version d'Ollama (0.30.10) : la capacité
# d'embedding n'est pas déclarée pour ce modèle, contrairement à un modèle
# dédié comme nomic-embed-text (274 Mo, même choix que documenté dans
# django_api/README.md).
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# Service ml/serving/app.py (voir ml/MLOPS_GUIDE.md). Nom de service Docker +
# port interne au conteneur (8500, cf. docker-compose.yml), pas le port hôte
# ML_SERVING_PORT publié dans .env.
ML_SERVING_URL = os.environ.get("ML_SERVING_URL", "http://ml-serving:8500")

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "hm_retail")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "hm_admin")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")

FEATURES_TABLE = "customers_features_train"
TRANSACTIONS_TABLE = "fact_transaction"

INFERENCE_OPTIONS = {
    "temperature": 0.1,
    "top_p": 0.9,
    "num_ctx": 2048,
    "num_predict": 512,
}

# Historique de conversation transmis au LLM : mêmes 6 derniers échanges que
# l'ancien frontend (old-frontend/src/pages/ChatIA.tsx, slice(-6)).
MAX_HISTORY_TURNS = 6
