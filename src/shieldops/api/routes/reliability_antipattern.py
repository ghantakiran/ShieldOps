"""Reliability anti-pattern detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.reliability_antipattern import (
    AntiPatternType,
    DetectionMethod,
    RemediationUrgency,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/reliability-antipattern",
    tags=["Reliability Antipattern"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Reliability antipattern service unavailable")
    return _engine


class RecordPatternRequest(BaseModel):
    service_name: str
    pattern_type: AntiPatternType = AntiPatternType.SINGLE_POINT_OF_FAILURE
    detection_method: DetectionMethod = DetectionMethod.STATIC_ANALYSIS
    urgency: RemediationUrgency = RemediationUrgency.MEDIUM_TERM
    impact_score: float = 0.0
    affected_services_count: int = 0
    details: str = ""


class AddRemediationPlanRequest(BaseModel):
    pattern_id: str
    plan_name: str
    urgency: RemediationUrgency = RemediationUrgency.MEDIUM_TERM
    estimated_effort_days: float = 0.0
    description: str = ""


@router.post("/patterns")
async def record_pattern(
    body: RecordPatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_pattern(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def list_patterns(
    service_name: str | None = None,
    pattern_type: AntiPatternType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_patterns(
            service_name=service_name,
            pattern_type=pattern_type,
            limit=limit,
        )
    ]


@router.get("/patterns/{record_id}")
async def get_pattern(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_pattern(record_id)
    if result is None:
        raise HTTPException(404, f"Pattern '{record_id}' not found")
    return result.model_dump()


@router.post("/remediation-plans")
async def add_remediation_plan(
    body: AddRemediationPlanRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_remediation_plan(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{service_name}")
async def analyze_service_antipatterns(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_service_antipatterns(service_name)


@router.get("/immediate-risks")
async def identify_immediate_risks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_immediate_risks()


@router.get("/rankings")
async def rank_by_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact()


@router.get("/systemic")
async def detect_systemic_issues(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_systemic_issues()


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


rap_route = router
