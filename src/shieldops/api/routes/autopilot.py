"""API routes for cost optimization autopilot."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

logger = structlog.get_logger()
router = APIRouter()

_autopilot: Any | None = None


def set_autopilot(autopilot: Any) -> None:
    global _autopilot
    _autopilot = autopilot


class AutopilotConfigUpdate(BaseModel):
    enabled: bool | None = None
    auto_approval_threshold: float | None = None
    max_monthly_savings_auto: float | None = None
    min_confidence: float | None = None
    excluded_environments: list[str] | None = None
    dry_run: bool | None = None


class AnalyzeRequest(BaseModel):
    cost_data: dict[str, Any] = Field(default_factory=dict)


@router.get("/cost/autopilot/config")
async def get_config(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if not _autopilot:
        return {"configured": False}
    return {"configured": True, "config": _autopilot.config.model_dump(mode="json")}


@router.put("/cost/autopilot/config")
async def update_config(
    request: AutopilotConfigUpdate,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    if not _autopilot:
        raise HTTPException(status_code=503, detail="Autopilot not initialized")
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    config = _autopilot.update_config(**updates)
    return {"config": config.model_dump(mode="json")}


@router.post("/cost/autopilot/analyze")
async def run_analysis(
    request: AnalyzeRequest | None = None,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    if not _autopilot:
        raise HTTPException(status_code=503, detail="Autopilot not initialized")
    cost_data = request.cost_data if request else {}
    result = await _autopilot.analyze_and_recommend(cost_data=cost_data)
    return {"result": result.model_dump(mode="json")}


@router.get("/cost/autopilot/recommendations")
async def list_recommendations(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if not _autopilot:
        return {"recommendations": [], "total": 0}
    recs = _autopilot.list_recommendations(status=status, limit=limit)
    return {
        "recommendations": [r.model_dump(mode="json") for r in recs],
        "total": len(recs),
    }


@router.post("/cost/autopilot/recommendations/{rec_id}/approve")
async def approve_recommendation(
    rec_id: str,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    if not _autopilot:
        raise HTTPException(status_code=503, detail="Autopilot not initialized")
    rec = await _autopilot.approve_recommendation(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found or not pending")
    return {"recommendation": rec.model_dump(mode="json")}


@router.post("/cost/autopilot/recommendations/{rec_id}/execute")
async def execute_recommendation(
    rec_id: str,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    if not _autopilot:
        raise HTTPException(status_code=503, detail="Autopilot not initialized")
    rec = await _autopilot.execute_recommendation(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found or not approved")
    return {"recommendation": rec.model_dump(mode="json")}


@router.get("/cost/autopilot/history")
async def get_history(
    limit: int = Query(20, ge=1, le=100),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if not _autopilot:
        return {"history": [], "total": 0}
    history = _autopilot.get_history(limit=limit)
    return {
        "history": [h.model_dump(mode="json") for h in history],
        "total": len(history),
    }
