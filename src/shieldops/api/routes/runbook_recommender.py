"""Runbook recommender API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/runbook-recommender", tags=["Runbook Recommender"])

_recommender: Any = None


def set_recommender(recommender: Any) -> None:
    global _recommender
    _recommender = recommender


def _get_recommender() -> Any:
    if _recommender is None:
        raise HTTPException(503, "Runbook recommender service unavailable")
    return _recommender


class GetRecommendationsRequest(BaseModel):
    service: str
    symptoms: list[str] = Field(default_factory=list)
    limit: int = 5


class RecordFeedbackRequest(BaseModel):
    runbook_id: str
    service: str
    was_helpful: bool
    resolution_time_minutes: float = 0


@router.post("/recommendations")
async def get_recommendations(
    body: GetRecommendationsRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    recommender = _get_recommender()
    candidates = recommender.recommend(
        incident_id="",
        symptoms=body.symptoms,
        service=body.service,
        limit=body.limit,
    )
    return [c.model_dump() for c in candidates]


@router.post("/feedback")
async def record_feedback(
    body: RecordFeedbackRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    recommender = _get_recommender()
    record = recommender.record_feedback(
        candidate_id=body.runbook_id,
        success=body.was_helpful,
        outcome=body.service,
        execution_time=body.resolution_time_minutes * 60,
    )
    return record.model_dump()


@router.get("/profiles")
async def list_profiles(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    recommender = _get_recommender()
    return [p.model_dump() for p in recommender.list_profiles()]


@router.get("/profiles/{runbook_id}")
async def get_profile(
    runbook_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    recommender = _get_recommender()
    profile = recommender.get_profile(runbook_id)
    if profile is None:
        raise HTTPException(404, f"Runbook profile '{runbook_id}' not found")
    return profile.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    recommender = _get_recommender()
    return recommender.get_stats()
