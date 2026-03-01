"""Knowledge Retention Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.knowledge_retention import (
    KnowledgeDomain,
    RetentionRisk,
    RetentionStrategy,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/knowledge-retention",
    tags=["Knowledge Retention"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Knowledge retention service unavailable")
    return _engine


class RecordRetentionRequest(BaseModel):
    team_id: str
    retention_risk: RetentionRisk = RetentionRisk.NONE
    knowledge_domain: KnowledgeDomain = KnowledgeDomain.INFRASTRUCTURE
    retention_strategy: RetentionStrategy = RetentionStrategy.DOCUMENTATION
    retention_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    team_id: str
    retention_risk: RetentionRisk = RetentionRisk.NONE
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/retentions")
async def record_retention(
    body: RecordRetentionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_retention(**body.model_dump())
    return result.model_dump()


@router.get("/retentions")
async def list_retentions(
    risk: RetentionRisk | None = None,
    domain: KnowledgeDomain | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_retentions(
            risk=risk,
            domain=domain,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/retentions/{record_id}")
async def get_retention(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_retention(record_id)
    if result is None:
        raise HTTPException(404, f"Retention record '{record_id}' not found")
    return result.model_dump()


@router.post("/assessments")
async def add_assessment(
    body: AddAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assessment(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_retention_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_retention_distribution()


@router.get("/at-risk-teams")
async def identify_at_risk_teams(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_at_risk_teams()


@router.get("/retention-rankings")
async def rank_by_retention_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_retention_score()


@router.get("/trends")
async def detect_retention_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_retention_trends()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    return engine.clear_data()


krt_route = router
