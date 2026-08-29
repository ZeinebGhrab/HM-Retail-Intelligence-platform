# ============================================================
# main.py — API du chatbot RAG (backend/app/)
#
# Contrat compatible avec l'ancien frontend (old-frontend/src/pages/ChatIA.tsx
# — POST /chat/ { question, history } -> { answer, model, error }), étendu
# d'un champ customer_id. Pas d'authentification cette itération (décision
# du 2026-08-28) : customer_id est fourni explicitement par l'appelant.
#
# Lancement local : uvicorn main:app --reload --port 8600
# ============================================================
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag_pipeline import answer_question
from schemas import ChatRequest, ChatResponse

app = FastAPI(
    title="H&M Retail Intelligence — Chatbot RAG",
    description="Assistant conversationnel client-spécifique (Ollama + tool calling).",
    version="1.0.0",
)

# frontend/ (localhost:5173 en dev) appelle cette API depuis le navigateur —
# sans CORS, le fetch() échoue silencieusement ("fetch failed") dès le
# preflight OPTIONS, jamais vu pendant les tests via curl/docker exec (qui
# n'appliquent pas CORS). allow_origins="*" : pas d'authentification par
# cookie/session cette itération (customer_id passe en clair dans le corps
# de la requête, voir schemas.py) — pas de risque CSRF lié aux origines ici.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat/", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = answer_question(
            question=request.question,
            customer_id=request.customer_id,
            history=[h.model_dump() for h in request.history],
        )
        return ChatResponse(**result)
    except Exception as e:
        return ChatResponse(answer="", error=str(e))
