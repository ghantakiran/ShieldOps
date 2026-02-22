"""API routes for learning recommendation approvals."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shieldops.playbooks.auto_applier import (
    PlaybookAutoApplier,
    RecommendationStatus,
    RecommendationType,
)

router = APIRouter()

_applier: PlaybookAutoApplier | None = None


def set_applier(applier: PlaybookAutoApplier) -> None:
    global _applier
    _applier = applier


def _get_applier() -> PlaybookAutoApplier:
    if _applier is None:
        raise HTTPException(status_code=503, detail="Auto-applier not initialized")
    return _applier


class ApproveRequest(BaseModel):
    reviewer: str


class RejectRequest(BaseModel):
    reviewer: str
    reason: str = ""


@router.get("/learning/recommendations")
async def list_recommendations(
    status: str | None = None,
    recommendation_type: str | None = None,
) -> dict[str, Any]:
    applier = _get_applier()
    status_filter = RecommendationStatus(status) if status else None
    type_filter = RecommendationType(recommendation_type) if recommendation_type else None
    recs = applier.list_recommendations(status=status_filter, recommendation_type=type_filter)
    return {"recommendations": [r.model_dump() for r in recs], "count": len(recs)}


@router.post("/learning/recommendations/{rec_id}/approve")
async def approve_recommendation(rec_id: str, body: ApproveRequest) -> dict[str, Any]:
    applier = _get_applier()
    rec = applier.approve_recommendation(rec_id, reviewer=body.reviewer)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec.model_dump()


@router.post("/learning/recommendations/{rec_id}/reject")
async def reject_recommendation(rec_id: str, body: RejectRequest) -> dict[str, Any]:
    applier = _get_applier()
    rec = applier.reject_recommendation(rec_id, reviewer=body.reviewer, reason=body.reason)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec.model_dump()


@router.get("/learning/auto-applied")
async def list_auto_applied() -> dict[str, Any]:
    applier = _get_applier()
    results = applier.list_auto_applied()
    return {"auto_applied": [r.model_dump() for r in results], "count": len(results)}
