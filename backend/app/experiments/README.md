# `experiments/` — exploratory scripts, not part of the chatbot

Nothing here runs as part of `backend/app/`'s actual pipeline. These are one-off scripts kept for
reference/documentation, not imported by `main.py`, `rag_pipeline.py`, or any `tools/*`.

## `qdrant_poc.py` — Qdrant vs. in-memory cosine similarity

**Result: Qdrant was tested and deliberately not adopted.** Production `semantic_search`
(`tools/semantic.py`) stays on a plain Python cosine-similarity scan over the knowledge base.

This script indexes the same knowledge-base chunks into both a running `qdrant` container and the
production in-memory approach, then compares them on a few sample questions. Findings: identical
top match and identical similarity score on every query (Qdrant uses cosine similarity internally
too), and Qdrant was slightly *slower* per query at this scale due to the extra HTTP round-trip. A
dedicated vector database only pays off once ANN indexing actually matters — i.e. a knowledge base
far larger than the handful of documents used here.

Run it (needs the `qdrant` and `ollama` services up, from inside the `chatbot-app` container or any
environment with network access to both):
```bash
python -m experiments.qdrant_poc
```
