"""SLO Compliance Monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_compliance_monitor import (
    ComplianceMetric,
    ComplianceState,
    MonitoringFrequency,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/slo-compliance-monitor",
    tags=["SLO Compliance Monitor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "SLO compliance monitor service unavailable")
    return _engine


class RecordComplianceRequest(BaseModel):
    slo_id: str
    compliance_state: ComplianceState = ComplianceState.COMPLIANT
    compliance_metric: ComplianceMetric = ComplianceMetric.AVAILABILITY
    monitoring_frequency: MonitoringFrequency = MonitoringFrequency.REAL_TIME
    compliance_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddCheckRequest(BaseModel):
    slo_id: str
    compliance_state: ComplianceState = ComplianceState.COMPLIANT
    check_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/compliance")
async def record_compliance(
    body: RecordComplianceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_compliance(**body.model_dump())
    return result.model_dump()


@router.get("/compliance")
async def list_compliance(
    state: ComplianceState | None = None,
    metric: ComplianceMetric | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_compliance(
            state=state,
            metric=metric,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/compliance/{record_id}")
async def get_compliance(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    found = engine.get_compliance(record_id)
    if found is None:
        raise HTTPException(404, f"Compliance record '{record_id}' not found")
    return found.model_dump()


@router.post("/checks")
async def add_check(
    body: AddCheckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_check(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_compliance_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_compliance_distribution()


@router.get("/non-compliant")
async def identify_non_compliant(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_non_compliant()


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


slc_route = router
