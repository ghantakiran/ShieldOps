"""Incident Escalation Scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.incident_escalation_scorer import (
    EscalationQuality,
    EscalationTarget,
    EscalationTrigger,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/incident-escalation-scorer",
    tags=["Incident Escalation Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Incident escalation scorer service unavailable")
    return _engine


class RecordEscalationRequest(BaseModel):
    escalation_id: str
    escalation_quality: EscalationQuality = EscalationQuality.APPROPRIATE
    escalation_target: EscalationTarget = EscalationTarget.TIER2
    escalation_trigger: EscalationTrigger = EscalationTrigger.MANUAL
    quality_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    escalation_id: str
    escalation_quality: EscalationQuality = EscalationQuality.APPROPRIATE
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/escalations")
async def record_escalation(
    body: RecordEscalationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_escalation(**body.model_dump())
    return result.model_dump()


@router.get("/escalations")
async def list_escalations(
    escalation_quality: EscalationQuality | None = None,
    escalation_target: EscalationTarget | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_escalations(
            escalation_quality=escalation_quality,
            escalation_target=escalation_target,
            team=team,
            limit=limit,
        )
    ]


@router.get("/escalations/{record_id}")
async def get_escalation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_escalation(record_id)
    if result is None:
        raise HTTPException(404, f"Escalation '{record_id}' not found")
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
async def analyze_escalation_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_escalation_distribution()


@router.get("/poor-escalations")
async def identify_poor_escalations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_poor_escalations()


@router.get("/quality-rankings")
async def rank_by_quality(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_quality()


@router.get("/trends")
async def detect_escalation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_escalation_trends()


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


iex_route = router
