# ============================================================
# ollama_client.py — Appels HTTP vers Ollama (/api/chat, /api/embeddings).
# Même modèle que backend/benchmark/ (appels REST directs, pas de framework
# LangChain/LlamaIndex — voir django_api/README.md pour la justification :
# la base de connaissance est petite, un framework complet serait
# disproportionné ici).
# ============================================================
from __future__ import annotations

import math

import requests

from config import INFERENCE_OPTIONS, OLLAMA_EMBED_MODEL, OLLAMA_HOST, OLLAMA_MODEL


def chat(
    messages: list[dict],
    system: str = "",
    model: str = OLLAMA_MODEL,
    options: dict | None = None,
) -> str:
    full_messages = (
        [{"role": "system", "content": system}] + messages if system else messages
    )
    payload = {
        "model": model,
        "messages": full_messages,
        "stream": False,
        "options": options or INFERENCE_OPTIONS,
    }
    resp = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json().get("message", {}).get("content", "").strip()


def embed(text: str, model: str = OLLAMA_EMBED_MODEL) -> list[float]:
    # /api/embed (pas l'ancien /api/embeddings, déprécié) — voir config.py :
    # qwen2.5:3b (modèle de chat) échoue avec "does not support embeddings"
    # sur cette version d'Ollama, d'où un modèle dédié par défaut ici.
    resp = requests.post(
        f"{OLLAMA_HOST}/api/embed",
        json={"model": model, "input": text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"][0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
