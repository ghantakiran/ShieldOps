"""Audit Remediation Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.audit_remediation_tracker import (
    FindingSource,
    RemediationPriority,
    RemediationState,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/audit-remediation-tracker",
    tags=["Audit Remediation Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Audit remediation tracker service unavailable")
    return _engine


class RecordRemediationRequest(BaseModel):
    finding_id: str
    remediation_priority: RemediationPriority = RemediationPriority.MEDIUM
    remediation_state: RemediationState = RemediationState.OPEN
    finding_source: FindingSource = FindingSource.INTERNAL_AUDIT
    remediation_days: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    finding_id: str
    remediation_priority: RemediationPriority = RemediationPriority.MEDIUM
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/remediations")
async def record_remediation(
    body: RecordRemediationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_remediation(**body.model_dump())
    return result.model_dump()


@router.get("/remediations")
async def list_remediations(
    priority: RemediationPriority | None = None,
    state: RemediationState | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_remediations(
            priority=priority,
            state=state,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/remediations/{record_id}")
async def get_remediation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_remediation(record_id)
    if result is None:
        raise HTTPException(404, f"Remediation '{record_id}' not found")
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
async def analyze_remediation_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_remediation_distribution()


@router.get("/overdue")
async def identify_overdue_remediations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overdue_remediations()


@router.get("/remediation-time-rankings")
async def rank_by_remediation_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_remediation_time()


@router.get("/trends")
async def detect_remediation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_remediation_trends()


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


arx_route = router
