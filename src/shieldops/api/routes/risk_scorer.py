"""Compliance Risk Scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.risk_scorer import (
    AssessmentStatus,
    RiskDomain,
    RiskLevel,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/risk-scorer", tags=["Risk Scorer"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Risk scorer service unavailable")
    return _engine


class RecordRiskRequest(BaseModel):
    control_id: str
    risk_level: RiskLevel = RiskLevel.LOW
    risk_domain: RiskDomain = RiskDomain.DATA_PRIVACY
    assessment_status: AssessmentStatus = AssessmentStatus.SCHEDULED
    risk_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    domain_pattern: str
    risk_domain: RiskDomain = RiskDomain.DATA_PRIVACY
    max_acceptable_risk: float = 0.0
    review_frequency_days: int = 90
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_risk(
    body: RecordRiskRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_risk(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_risks(
    risk_level: RiskLevel | None = None,
    risk_domain: RiskDomain | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_risks(
            risk_level=risk_level,
            risk_domain=risk_domain,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_risk(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_risk(record_id)
    if result is None:
        raise HTTPException(404, f"Risk record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_risk_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_risk_distribution()


@router.get("/critical-risks")
async def identify_critical_risks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_risks()


@router.get("/risk-rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/trends")
async def detect_risk_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_risk_trends()


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


crs_route = router
