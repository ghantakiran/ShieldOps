"""Deployment rollback analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.rollback_analyzer import (
    RollbackImpact,
    RollbackReason,
    RollbackSpeed,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/rollback-analyzer",
    tags=["Rollback Analyzer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Rollback analyzer service unavailable")
    return _engine


class RecordRollbackRequest(BaseModel):
    service_name: str
    reason: RollbackReason = RollbackReason.MANUAL_TRIGGER
    impact: RollbackImpact = RollbackImpact.LOW
    speed: RollbackSpeed = RollbackSpeed.NORMAL
    rollback_rate_pct: float = 0.0
    details: str = ""


class AddPatternRequest(BaseModel):
    pattern_name: str
    reason: RollbackReason = RollbackReason.MANUAL_TRIGGER
    impact: RollbackImpact = RollbackImpact.LOW
    frequency: int = 0
    description: str = ""


@router.post("/rollbacks")
async def record_rollback(
    body: RecordRollbackRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_rollback(**body.model_dump())
    return result.model_dump()


@router.get("/rollbacks")
async def list_rollbacks(
    service_name: str | None = None,
    reason: RollbackReason | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_rollbacks(service_name=service_name, reason=reason, limit=limit)
    ]


@router.get("/rollbacks/{record_id}")
async def get_rollback(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_rollback(record_id)
    if result is None:
        raise HTTPException(404, f"Rollback '{record_id}' not found")
    return result.model_dump()


@router.post("/patterns")
async def add_pattern(
    body: AddPatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_pattern(**body.model_dump())
    return result.model_dump()


@router.get("/frequency/{service_name}")
async def analyze_rollback_frequency(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_rollback_frequency(service_name)


@router.get("/high-rollback")
async def identify_high_rollback_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_rollback_services()


@router.get("/rankings")
async def rank_by_rollback_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_rollback_rate()


@router.get("/trends")
async def detect_rollback_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
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


rba_route = router
