"""Incident impact scoring API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.agents.investigation.impact_scorer import ImpactLevel
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/incident-impact", tags=["Incident Impact"])

_scorer: Any = None


def set_scorer(scorer: Any) -> None:
    global _scorer
    _scorer = scorer


def _get_scorer() -> Any:
    if _scorer is None:
        raise HTTPException(503, "Impact scoring service unavailable")
    return _scorer


class ScoreRequest(BaseModel):
    incident_id: str
    dimensions: list[dict[str, Any]] = Field(default_factory=list)
    affected_services: list[str] = Field(default_factory=list)
    estimated_users_affected: int = 0
    estimated_revenue_impact: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class TopologyScoreRequest(BaseModel):
    incident_id: str
    affected_services: list[str]
    total_services: int = 0
    users_per_service: int = 100
    revenue_per_service_hour: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/score")
async def score_incident(
    body: ScoreRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    result = scorer.score_incident(**body.model_dump())
    return result.model_dump()


@router.post("/score-from-topology")
async def score_from_topology(
    body: TopologyScoreRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    result = scorer.score_from_topology(**body.model_dump())
    return result.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    return scorer.get_stats()


@router.get("/{incident_id}")
async def get_impact_score(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    score = scorer.get_score(incident_id)
    if score is None:
        raise HTTPException(404, f"Impact score for '{incident_id}' not found")
    return score.model_dump()


@router.get("")
async def list_impact_scores(
    min_level: ImpactLevel = ImpactLevel.NEGLIGIBLE,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [s.model_dump() for s in scorer.list_by_severity(min_level=min_level, limit=limit)]
