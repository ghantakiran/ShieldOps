"""Audit Compliance Reporter API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.compliance_reporter import (
    AuditScope,
    ComplianceLevel,
    ReportType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/compliance-reporter", tags=["Compliance Reporter"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Compliance reporter service unavailable")
    return _engine


class RecordComplianceRequest(BaseModel):
    framework: str
    report_type: ReportType = ReportType.SOC2
    compliance_level: ComplianceLevel = ComplianceLevel.UNDER_REVIEW
    audit_scope: AuditScope = AuditScope.FULL
    compliance_score: float = 0.0
    findings_count: int = 0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    control_id: str
    report_type: ReportType = ReportType.SOC2
    audit_scope: AuditScope = AuditScope.FULL
    required_evidence_count: int = 0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_compliance(
    body: RecordComplianceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_compliance(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_compliance_records(
    report_type: ReportType | None = None,
    compliance_level: ComplianceLevel | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_compliance_records(
            report_type=report_type,
            compliance_level=compliance_level,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_compliance(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_compliance(record_id)
    if result is None:
        raise HTTPException(404, f"Compliance record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/gaps")
async def analyze_compliance_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_compliance_gaps()


@router.get("/non-compliant")
async def identify_non_compliant(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_non_compliant()


@router.get("/score-rankings")
async def rank_by_compliance_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_compliance_score()


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


acr_route = router
