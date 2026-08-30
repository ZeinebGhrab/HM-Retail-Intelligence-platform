# ============================================================
# tools/semantic.py — semantic_search
#
# Même approche que django_api/history/rag_pipeline.py::_retrieve_kb() :
# embeddings via Ollama /api/embeddings, cosine similarity en Python pur.
# Pas de Qdrant — la base de connaissance (insights_summary.md découpé par
# section) ne compte qu'une poignée de documents, ce qui rend une base
# vectorielle disproportionnée (même justification que django_api/README.md,
# section "Bases vectorielles associées au RAG").
# ============================================================
from __future__ import annotations

import data_store
import ollama_client
from tool_signals import unavailable

_MIN_SIMILARITY = 0.3

_chunk_embeddings: list[tuple[dict, list[float]]] | None = None


def _get_chunk_embeddings() -> list[tuple[dict, list[float]]]:
    global _chunk_embeddings
    if _chunk_embeddings is None:
        chunks = data_store.get_insights_chunks()
        _chunk_embeddings = [
            (chunk, ollama_client.embed(f"{chunk['title']} : {chunk['content']}"))
            for chunk in chunks
        ]
    return _chunk_embeddings


def semantic_search(query: str, n_results: int = 2) -> str:
    try:
        indexed = _get_chunk_embeddings()
    except Exception:
        return unavailable(
            "La recherche sémantique est indisponible pour le moment "
            "(service d'embeddings injoignable)."
        )

    if not indexed:
        return unavailable("Aucune base de connaissance disponible.")

    try:
        query_embedding = ollama_client.embed(query)
    except Exception:
        return unavailable("La recherche sémantique est indisponible pour le moment.")

    scored = sorted(
        ((ollama_client.cosine_similarity(emb, query_embedding), chunk) for chunk, emb in indexed),
        key=lambda t: t[0],
        reverse=True,
    )
    top = [(sim, chunk) for sim, chunk in scored[:n_results] if sim >= _MIN_SIMILARITY]

    if not top:
        return unavailable("Aucune information pertinente trouvée dans la base de connaissance.")

    return "\n\n".join(f"[{chunk['title']}]\n{chunk['content']}" for _, chunk in top)
