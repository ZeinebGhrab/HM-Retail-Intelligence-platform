# ============================================================
# experiments/qdrant_poc.py — Exploration Qdrant (hors pipeline principal).
#
# Ce script ne fait PAS partie de l'application : tools/semantic.py reste en
# production sur une similarité cosinus en mémoire pure Python (voir sa
# justification). Ce POC sert uniquement à comparer concrètement les deux
# approches sur la base de connaissance réelle (8 chunks), dans le cadre
# d'une exploration technique du stage — pas d'un besoin de production
# (le corpus est trop petit pour justifier une base vectorielle dédiée :
# indexation ANN, persistance, filtrage à l'échelle n'apportent rien ici).
#
# Usage (depuis un shell ayant accès au réseau docker-compose, ex. à
# l'intérieur du conteneur chatbot-app) :
#   python -m experiments.qdrant_poc
# ============================================================
from __future__ import annotations

import time

import requests

import data_store
import ollama_client

QDRANT_URL = "http://qdrant:6333"
COLLECTION = "hm_insights_poc"

TEST_QUERIES = [
    "Quelle est la part du chiffre d'affaires du segment VIP ?",
    "Quels sont les produits vendus par ce magasin ?",
    "Que fait l'entreprise H&M ?",
]


def _cosine_baseline(query: str, indexed: list[tuple[dict, list[float]]]) -> tuple[float, dict]:
    query_emb = ollama_client.embed(query)
    scored = sorted(
        ((ollama_client.cosine_similarity(emb, query_emb), chunk) for chunk, emb in indexed),
        key=lambda t: t[0],
        reverse=True,
    )
    return scored[0]


def _setup_qdrant_collection(indexed: list[tuple[dict, list[float]]]) -> None:
    dim = len(indexed[0][1])
    requests.delete(f"{QDRANT_URL}/collections/{COLLECTION}")
    requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION}",
        json={"vectors": {"size": dim, "distance": "Cosine"}},
    ).raise_for_status()

    points = [
        {"id": i, "vector": emb, "payload": {"title": chunk["title"], "content": chunk["content"]}}
        for i, (chunk, emb) in enumerate(indexed)
    ]
    requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION}/points",
        json={"points": points},
    ).raise_for_status()


def _qdrant_search(query: str) -> dict:
    query_emb = ollama_client.embed(query)
    resp = requests.post(
        f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
        json={"vector": query_emb, "limit": 1, "with_payload": True},
    )
    resp.raise_for_status()
    return resp.json()["result"][0]


def main() -> None:
    chunks = data_store.get_insights_chunks()
    print(f"{len(chunks)} chunks charges depuis la base de connaissance.\n")

    print("Calcul des embeddings (nomic-embed-text)...")
    indexed = [(chunk, ollama_client.embed(f"{chunk['title']} : {chunk['content']}")) for chunk in chunks]

    print("Indexation dans Qdrant...")
    _setup_qdrant_collection(indexed)

    print("\n=== Comparaison cosinus (Python pur) vs Qdrant ===\n")
    for query in TEST_QUERIES:
        t0 = time.perf_counter()
        cos_score, cos_chunk = _cosine_baseline(query, indexed)
        cos_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        qdrant_hit = _qdrant_search(query)
        qdrant_time = time.perf_counter() - t0

        print(f"Question : {query}")
        print(f"  Cosinus Python : [{cos_chunk['title']}] score={cos_score:.4f} ({cos_time*1000:.1f} ms)")
        print(f"  Qdrant         : [{qdrant_hit['payload']['title']}] score={qdrant_hit['score']:.4f} ({qdrant_time*1000:.1f} ms)")
        print(f"  Meme resultat  : {cos_chunk['title'] == qdrant_hit['payload']['title']}\n")


if __name__ == "__main__":
    main()
