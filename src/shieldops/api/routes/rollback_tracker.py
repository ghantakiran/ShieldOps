"""Deployment Rollback Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.rollback_tracker import (
    RollbackImpact,
    RollbackReason,
    RollbackStatus,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/rollback-tracker", tags=["Rollback Tracker"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Rollback tracker service unavailable")
    return _engine


class RecordRollbackRequest(BaseModel):
    deployment_id: str
    rollback_reason: RollbackReason = RollbackReason.BUG
    rollback_impact: RollbackImpact = RollbackImpact.NONE
    rollback_status: RollbackStatus = RollbackStatus.INITIATED
    duration_minutes: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddPatternRequest(BaseModel):
    service_pattern: str
    rollback_reason: RollbackReason = RollbackReason.BUG
    frequency_threshold: int = 0
    auto_block: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_rollback(
    body: RecordRollbackRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_rollback(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_rollbacks(
    reason: RollbackReason | None = None,
    impact: RollbackImpact | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_rollbacks(
            reason=reason,
            impact=impact,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_rollback(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_rollback(record_id)
    if result is None:
        raise HTTPException(404, f"Rollback record '{record_id}' not found")
    return result.model_dump()


@router.post("/patterns")
async def add_pattern(
    body: AddPatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_pattern(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_rollback_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_rollback_patterns()


@router.get("/frequent-rollers")
async def identify_frequent_rollers(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_frequent_rollers()


@router.get("/duration-rankings")
async def rank_by_duration(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_duration()


@router.get("/trends")
async def detect_rollback_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_rollback_trends()


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


rbt_route = router
