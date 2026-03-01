"""SLO Breach Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_breach_analyzer import (
    BreachCause,
    BreachSeverity,
    BreachType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/slo-breach-analyzer",
    tags=["SLO Breach Analyzer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "SLO breach analyzer service unavailable")
    return _engine


class RecordBreachRequest(BaseModel):
    breach_id: str
    breach_type: BreachType = BreachType.AVAILABILITY
    breach_severity: BreachSeverity = BreachSeverity.MODERATE
    breach_cause: BreachCause = BreachCause.INFRASTRUCTURE_FAILURE
    breach_duration_minutes: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    breach_id: str
    breach_type: BreachType = BreachType.AVAILABILITY
    impact_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/breaches")
async def record_breach(
    body: RecordBreachRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_breach(**body.model_dump())
    return result.model_dump()


@router.get("/breaches")
async def list_breaches(
    breach_type: BreachType | None = None,
    breach_severity: BreachSeverity | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_breaches(
            breach_type=breach_type,
            breach_severity=breach_severity,
            team=team,
            limit=limit,
        )
    ]


@router.get("/breaches/{record_id}")
async def get_breach(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_breach(record_id)
    if result is None:
        raise HTTPException(404, f"Breach '{record_id}' not found")
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
async def analyze_breach_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_breach_distribution()


@router.get("/critical-breaches")
async def identify_critical_breaches(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_breaches()


@router.get("/duration-rankings")
async def rank_by_breach_duration(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_breach_duration()


@router.get("/trends")
async def detect_breach_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_breach_trends()


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


sba_route = router
