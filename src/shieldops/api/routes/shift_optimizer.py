"""Shift Schedule Optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.shift_optimizer import (
    CoverageStatus,
    ScheduleIssue,
    ShiftType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/shift-optimizer", tags=["Shift Optimizer"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Shift optimizer service unavailable")
    return _engine


class RecordShiftRequest(BaseModel):
    schedule_id: str
    shift_type: ShiftType = ShiftType.PRIMARY
    coverage_status: CoverageStatus = CoverageStatus.FULL
    schedule_issue: ScheduleIssue = ScheduleIssue.FATIGUE_RISK
    coverage_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddGapRequest(BaseModel):
    schedule_id: str
    shift_type: ShiftType = ShiftType.PRIMARY
    gap_duration_hours: float = 0.0
    severity: int = 0
    auto_fill: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_shift(
    body: RecordShiftRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_shift(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_shifts(
    shift_type: ShiftType | None = None,
    coverage_status: CoverageStatus | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_shifts(
            shift_type=shift_type,
            coverage_status=coverage_status,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_shift(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_shift(record_id)
    if result is None:
        raise HTTPException(404, f"Shift record '{record_id}' not found")
    return result.model_dump()


@router.post("/gaps")
async def add_gap(
    body: AddGapRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_gap(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_coverage_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_coverage_patterns()


@router.get("/coverage-gaps")
async def identify_coverage_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_coverage_gaps()


@router.get("/coverage-rankings")
async def rank_by_coverage_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_coverage_score()


@router.get("/trends")
async def detect_schedule_issues(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_schedule_issues()


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


sso_route = router
