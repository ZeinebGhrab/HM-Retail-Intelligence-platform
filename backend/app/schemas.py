from __future__ import annotations

from pydantic import BaseModel, Field


class ChatHistoryItem(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    """Étend le contrat de l'ancien frontend (old-frontend/src/pages/ChatIA.tsx
    — POST /chat/ { question, history }) d'un seul champ : customer_id.
    Pas de session/auth pour cette itération (voir décision du 2026-08-28) —
    le client de l'ID est à la charge de l'appelant."""

    question: str
    customer_id: str | None = Field(
        default=None,
        description="Client actuellement affiché/sélectionné côté frontend, si applicable.",
    )
    history: list[ChatHistoryItem] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    model: str | None = None
    tool_used: str | None = None
    error: str | None = None
