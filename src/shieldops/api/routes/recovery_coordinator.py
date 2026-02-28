"""Recovery coordinator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.recovery_coordinator import (
    RecoveryPhase,
    RecoveryPriority,
    RecoveryStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/recovery-coordinator",
    tags=["Recovery Coordinator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Recovery coordinator service unavailable")
    return _engine


class RecordRecoveryRequest(BaseModel):
    incident_id: str
    recovery_phase: RecoveryPhase = RecoveryPhase.ASSESSMENT
    recovery_status: RecoveryStatus = RecoveryStatus.PENDING
    recovery_priority: RecoveryPriority = RecoveryPriority.HIGH
    affected_services: int = 0
    details: str = ""


class AddMilestoneRequest(BaseModel):
    milestone_name: str
    recovery_phase: RecoveryPhase = RecoveryPhase.RESTORATION
    recovery_status: RecoveryStatus = RecoveryStatus.IN_PROGRESS
    duration_seconds: float = 0.0


@router.post("/recoveries")
async def record_recovery(
    body: RecordRecoveryRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_recovery(**body.model_dump())
    return result.model_dump()


@router.get("/recoveries")
async def list_recoveries(
    incident_id: str | None = None,
    recovery_status: RecoveryStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_recoveries(
            incident_id=incident_id, recovery_status=recovery_status, limit=limit
        )
    ]


@router.get("/recoveries/{record_id}")
async def get_recovery(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_recovery(record_id)
    if result is None:
        raise HTTPException(404, f"Recovery record '{record_id}' not found")
    return result.model_dump()


@router.post("/milestones")
async def add_milestone(
    body: AddMilestoneRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_milestone(**body.model_dump())
    return result.model_dump()


@router.get("/recovery-speed/{incident_id}")
async def analyze_recovery_speed(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_recovery_speed(incident_id)


@router.get("/stalled-recoveries")
async def identify_stalled_recoveries(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_stalled_recoveries()


@router.get("/rankings")
async def rank_by_recovery_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_recovery_time()


@router.get("/regressions")
async def detect_recovery_regressions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_recovery_regressions()


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


rcc_route = router
