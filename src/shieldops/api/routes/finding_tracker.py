"""Audit Finding Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.finding_tracker import (
    FindingCategory,
    FindingSeverity,
    FindingStatus,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/finding-tracker", tags=["Finding Tracker"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Finding tracker service unavailable")
    return _engine


class RecordFindingRequest(BaseModel):
    finding_id: str
    finding_severity: FindingSeverity = FindingSeverity.INFORMATIONAL
    finding_status: FindingStatus = FindingStatus.OPEN
    finding_category: FindingCategory = FindingCategory.ACCESS_CONTROL
    open_finding_pct: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRemediationRequest(BaseModel):
    plan_pattern: str
    finding_severity: FindingSeverity = FindingSeverity.INFORMATIONAL
    days_to_remediate: int = 0
    resources_required: int = 0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_finding(
    body: RecordFindingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_finding(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_findings(
    finding_severity: FindingSeverity | None = None,
    finding_status: FindingStatus | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_findings(
            finding_severity=finding_severity,
            finding_status=finding_status,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_finding(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_finding(record_id)
    if result is None:
        raise HTTPException(404, f"Finding record '{record_id}' not found")
    return result.model_dump()


@router.post("/remediations")
async def add_remediation(
    body: AddRemediationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_remediation(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_finding_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_finding_patterns()


@router.get("/overdue")
async def identify_overdue_findings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overdue_findings()


@router.get("/severity-rankings")
async def rank_by_severity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_severity()


@router.get("/trends")
async def detect_finding_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_finding_trends()


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


aft_route = router
