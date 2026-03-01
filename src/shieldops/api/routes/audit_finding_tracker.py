"""Audit Finding Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.audit_finding_tracker import (
    FindingCategory,
    FindingSeverity,
    FindingStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/audit-finding",
    tags=["Audit Finding"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Audit finding service unavailable")
    return _engine


class RecordFindingRequest(BaseModel):
    finding_id: str
    finding_severity: FindingSeverity = FindingSeverity.INFORMATIONAL
    finding_category: FindingCategory = FindingCategory.COMPLIANCE
    finding_status: FindingStatus = FindingStatus.OPEN
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRemediationRequest(BaseModel):
    finding_id: str
    finding_severity: FindingSeverity = FindingSeverity.INFORMATIONAL
    remediation_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/findings")
async def record_finding(
    body: RecordFindingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_finding(**body.model_dump())
    return result.model_dump()


@router.get("/findings")
async def list_findings(
    severity: FindingSeverity | None = None,
    category: FindingCategory | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_findings(
            severity=severity,
            category=category,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/findings/{record_id}")
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


@router.get("/distribution")
async def analyze_finding_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_finding_distribution()


@router.get("/open-findings")
async def identify_open_findings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_open_findings()


@router.get("/risk-rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


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


afk_route = router
