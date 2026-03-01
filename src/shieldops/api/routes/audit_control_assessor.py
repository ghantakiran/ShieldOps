"""Audit Control Assessor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.audit_control_assessor import (
    AssessmentType,
    ControlDomain,
    ControlEffectiveness,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/audit-control-assessor",
    tags=["Audit Control Assessor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Audit control assessor service unavailable")
    return _engine


class RecordControlRequest(BaseModel):
    control_id: str
    control_domain: ControlDomain = ControlDomain.ACCESS_CONTROL
    control_effectiveness: ControlEffectiveness = ControlEffectiveness.NOT_TESTED
    assessment_type: AssessmentType = AssessmentType.AUTOMATED
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    control_id: str
    control_domain: ControlDomain = ControlDomain.ACCESS_CONTROL
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/controls")
async def record_control(
    body: RecordControlRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_control(**body.model_dump())
    return result.model_dump()


@router.get("/controls")
async def list_controls(
    domain: ControlDomain | None = None,
    effectiveness: ControlEffectiveness | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_controls(
            domain=domain,
            effectiveness=effectiveness,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/controls/{record_id}")
async def get_control(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_control(record_id)
    if result is None:
        raise HTTPException(404, f"Control '{record_id}' not found")
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
async def analyze_control_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_control_distribution()


@router.get("/ineffective-controls")
async def identify_ineffective_controls(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_ineffective_controls()


@router.get("/effectiveness-rankings")
async def rank_by_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_effectiveness()


@router.get("/trends")
async def detect_control_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_control_trends()


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


acx_route = router
