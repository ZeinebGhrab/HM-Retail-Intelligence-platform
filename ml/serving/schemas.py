"""Schémas Pydantic des requêtes/réponses de l'API d'inférence (ml/serving/app.py)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class BehaviorFeatures(BaseModel):
    """Features comportementales communes (classification + clustering), cf. config.yaml."""

    age: float = Field(..., ge=0, le=120, examples=[34])
    n_transactions: float = Field(..., ge=0, examples=[27])
    tenure_days: float = Field(..., ge=0, examples=[540])
    n_distinct_categories: float = Field(..., ge=0, examples=[6])
    avg_basket_value: float = Field(..., ge=0, examples=[42.5])
    purchase_frequency_per_month: float = Field(..., ge=0, examples=[1.8])
    recency_days: float = Field(..., ge=0, examples=[12])


class ClubStatusPrediction(BaseModel):
    club_member_status: str
    probabilities: dict[str, float]
    model_version: str | None = None


class SegmentPrediction(BaseModel):
    cluster: int
    model_version: str | None = None


class SpendFeatures(BaseModel):
    age: float
    n_transactions: float
    tenure_days: float
    n_distinct_categories: float
    purchase_frequency_per_month: float
    recency_days: float
    club_member_status: str = Field(..., examples=["ACTIVE"])
    fashion_news_frequency: str = Field(..., examples=["Regularly"])
    age_group: str = Field(..., examples=["26-35"])


class SpendPrediction(BaseModel):
    predicted_total_spend: float
    model_version: str | None = None


class HealthResponse(BaseModel):
    status: str
    models_loaded: dict[str, bool]