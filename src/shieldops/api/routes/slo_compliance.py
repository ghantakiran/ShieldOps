"""SLO compliance checker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_compliance import (
    CompliancePeriod,
    ComplianceStatus,
    SLOType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/slo-compliance",
    tags=["SLO Compliance"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "SLO compliance checker service unavailable",
        )
    return _engine


class RecordComplianceRequest(BaseModel):
    service_name: str
    slo_name: str = ""
    slo_type: SLOType = SLOType.AVAILABILITY
    period: CompliancePeriod = CompliancePeriod.DAILY
    status: ComplianceStatus = ComplianceStatus.COMPLIANT
    compliance_pct: float = 100.0
    target_pct: float = 99.0
    details: str = ""


class AddViolationRequest(BaseModel):
    service_name: str
    slo_name: str = ""
    slo_type: SLOType = SLOType.AVAILABILITY
    status: ComplianceStatus = ComplianceStatus.NON_COMPLIANT
    breach_pct: float = 0.0
    duration_minutes: float = 0.0
    root_cause: str = ""
    resolved: bool = False


@router.post("/compliances")
async def record_compliance(
    body: RecordComplianceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_compliance(**body.model_dump())
    return result.model_dump()


@router.get("/compliances")
async def list_compliances(
    service_name: str | None = None,
    slo_type: SLOType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_compliances(
            service_name=service_name,
            slo_type=slo_type,
            limit=limit,
        )
    ]


@router.get("/compliances/{record_id}")
async def get_compliance(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_compliance(record_id)
    if result is None:
        raise HTTPException(404, f"Compliance record '{record_id}' not found")
    return result.model_dump()


@router.post("/violations")
async def add_violation(
    body: AddViolationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_violation(**body.model_dump())
    return result.model_dump()


@router.get("/by-service/{service_name}")
async def analyze_compliance_by_service(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_compliance_by_service(service_name)


@router.get("/non-compliant")
async def identify_non_compliant_slos(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_non_compliant_slos()


@router.get("/rankings")
async def rank_by_compliance_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_compliance_score()


@router.get("/trends")
async def detect_compliance_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
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


scc_route = router
