"""Security Compliance Scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.security_compliance_scorer import (
    ComplianceArea,
    FrameworkType,
    GapSeverity,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/security-compliance-scorer",
    tags=["Security Compliance Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Security compliance scorer service unavailable")
    return _engine


class RecordComplianceRequest(BaseModel):
    control_name: str
    compliance_area: ComplianceArea = ComplianceArea.ACCESS_CONTROL
    gap_severity: GapSeverity = GapSeverity.CRITICAL
    framework_type: FrameworkType = FrameworkType.SOC2
    compliance_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    control_name: str
    compliance_area: ComplianceArea = ComplianceArea.ACCESS_CONTROL
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/compliance-records")
async def record_compliance(
    body: RecordComplianceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_compliance(**body.model_dump())
    return result.model_dump()


@router.get("/compliance-records")
async def list_compliance_records(
    compliance_area: ComplianceArea | None = None,
    gap_severity: GapSeverity | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_compliance_records(
            compliance_area=compliance_area,
            gap_severity=gap_severity,
            team=team,
            limit=limit,
        )
    ]


@router.get("/compliance-records/{record_id}")
async def get_compliance(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    found = engine.get_compliance(record_id)
    if found is None:
        raise HTTPException(404, f"Compliance record '{record_id}' not found")
    return found.model_dump()


@router.post("/assessments")
async def add_assessment(
    body: AddAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assessment(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_compliance_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_compliance_distribution()


@router.get("/compliance-gaps")
async def identify_compliance_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_compliance_gaps()


@router.get("/compliance-rankings")
async def rank_by_compliance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_compliance()


@router.get("/trends")
async def detect_compliance_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_compliance_trends()


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


scs_route = router
