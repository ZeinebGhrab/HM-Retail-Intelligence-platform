"""
notifications_router.py

Reçoit les notifications poussées par le workflow n8n
("HM - Recalcul RFM nocturne + notifications", nœud "Push SSE -> Backend")
et les diffuse en temps réel au frontend via Server-Sent Events (SSE).

Remplace l'appel initialement prévu vers un backend Django qui n'existe pas
dans ce dépôt : le nœud n8n doit pointer vers
    POST {BACKEND_URL}/api/notifications


Intégration dans main.py :

    from notifications_router import router as notifications_router
    app.include_router(notifications_router)

(vérifiez que votre config CORS dans main.py autorise déjà l'origine du
frontend -- si `askChatbot` fonctionne déjà en cross-origin, c'est le cas.)
"""

import asyncio
import json
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

# --- Stockage en mémoire -------------------------------------------------
# Volontairement simple pour démarrer : perdu au redémarrage du backend.
# A remplacer plus tard par une table via db.py / data_store.py si vous
# avez besoin que les notifications survivent à un redémarrage.
MAX_NOTIFICATIONS = 200
_notifications: "deque[dict]" = deque(maxlen=MAX_NOTIFICATIONS)
_subscribers: list[asyncio.Queue] = []


class PredictionSummary(BaseModel):
    n_customers_scored: Optional[int] = None
    dominant_club_status: Optional[str] = None
    dominant_segment: Optional[str] = None
    predicted_spend_total: Optional[float] = None
    predicted_spend_mean: Optional[float] = None


class NotificationIn(BaseModel):
    # Correspond exactement au payload construit par le nœud n8n
    # "Formater Payload SSE" : { type, date, generated_at, message, prediction }
    type: str = "llm_report"
    date: Optional[str] = None
    generated_at: Optional[str] = None
    message: str
    prediction: Optional[PredictionSummary] = None


def _broadcast(notification: dict) -> None:
    for queue in list(_subscribers):
        queue.put_nowait(notification)


@router.post("", status_code=201)
async def receive_notification(payload: NotificationIn):
    """Appelé par n8n (nœud 'Push SSE -> Backend') après chaque recalcul RFM nocturne."""
    notification = {
        "id": str(uuid.uuid4()),
        "type": payload.type,
        "message": payload.message,
        "date": payload.date,
        "generated_at": payload.generated_at,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read": False,
        "prediction": payload.prediction.dict() if payload.prediction else None,
    }
    _notifications.appendleft(notification)
    _broadcast(notification)
    return notification


@router.get("")
async def list_notifications(limit: int = 50):
    """Chargement initial de la liste par le frontend (icône cloche)."""
    return list(_notifications)[:limit]

@router.patch("/read-all")
async def mark_all_as_read():
    for n in _notifications:
        n["read"] = True
    return {"updated": len(_notifications)}
@router.patch("/{notification_id}/read")
async def mark_as_read(notification_id: str):
    for n in _notifications:
        if n["id"] == notification_id:
            n["read"] = True
            return n
    raise HTTPException(status_code=404, detail="Notification introuvable")





@router.get("/stream")
async def stream_notifications():
    """Flux SSE : le frontend s'abonne une fois et reçoit chaque nouvelle
    notification en temps réel, sans polling."""
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.append(queue)

    async def event_generator():
        try:
            while True:
                try:
                    notification = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"event: notification\ndata: {json.dumps(notification)}\n\n"
                except asyncio.TimeoutError:
                    # keep-alive pour éviter la fermeture de la connexion par un proxy/reverse-proxy
                    yield ": keep-alive\n\n"
        finally:
            _subscribers.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
