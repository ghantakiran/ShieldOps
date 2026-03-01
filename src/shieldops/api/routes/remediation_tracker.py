"""Audit Remediation Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.remediation_tracker import (
    RemediationPriority,
    RemediationStatus,
    RemediationType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/remediation-tracker", tags=["Remediation Tracker"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Remediation tracker service unavailable")
    return _engine


class RecordRemediationRequest(BaseModel):
    finding_id: str
    remediation_priority: RemediationPriority = RemediationPriority.MEDIUM
    remediation_status: RemediationStatus = RemediationStatus.NOT_STARTED
    remediation_type: RemediationType = RemediationType.TECHNICAL_FIX
    completion_pct: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMilestoneRequest(BaseModel):
    milestone_name: str
    remediation_priority: RemediationPriority = RemediationPriority.MEDIUM
    progress_score: float = 0.0
    items_tracked: int = 0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_remediation(
    body: RecordRemediationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_remediation(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_remediations(
    remediation_priority: RemediationPriority | None = None,
    remediation_status: RemediationStatus | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_remediations(
            remediation_priority=remediation_priority,
            remediation_status=remediation_status,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_remediation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_remediation(record_id)
    if result is None:
        raise HTTPException(404, f"Remediation record '{record_id}' not found")
    return result.model_dump()


@router.post("/milestones")
async def add_milestone(
    body: AddMilestoneRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_milestone(**body.model_dump())
    return result.model_dump()


@router.get("/progress")
async def analyze_remediation_progress(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_remediation_progress()


@router.get("/overdue")
async def identify_overdue_remediations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overdue_remediations()


@router.get("/priority-rankings")
async def rank_by_priority(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_priority()


@router.get("/bottlenecks")
async def detect_remediation_bottlenecks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_remediation_bottlenecks()


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


art_route = router
