"""DR drill tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.dr_drill_tracker import (
    DrillOutcome,
    DrillScope,
    DrillType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dr-drill-tracker",
    tags=["DR Drill Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "DR drill tracker service unavailable")
    return _engine


class RecordDrillRequest(BaseModel):
    service_name: str
    drill_type: DrillType = DrillType.FAILOVER
    outcome: DrillOutcome = DrillOutcome.SUCCESS
    scope: DrillScope = DrillScope.SINGLE_SERVICE
    recovery_time_minutes: float = 0.0
    details: str = ""


class AddFindingRequest(BaseModel):
    finding_name: str
    drill_type: DrillType = DrillType.FAILOVER
    outcome: DrillOutcome = DrillOutcome.SUCCESS
    severity_score: float = 0.0
    description: str = ""


@router.post("/drills")
async def record_drill(
    body: RecordDrillRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_drill(**body.model_dump())
    return result.model_dump()


@router.get("/drills")
async def list_drills(
    service_name: str | None = None,
    drill_type: DrillType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_drills(service_name=service_name, drill_type=drill_type, limit=limit)
    ]


@router.get("/drills/{record_id}")
async def get_drill(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_drill(record_id)
    if result is None:
        raise HTTPException(404, f"Drill record '{record_id}' not found")
    return result.model_dump()


@router.post("/findings")
async def add_finding(
    body: AddFindingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_finding(**body.model_dump())
    return result.model_dump()


@router.get("/service-effectiveness/{service_name}")
async def analyze_drill_effectiveness(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_drill_effectiveness(service_name)


@router.get("/failed-drills")
async def identify_failed_drills(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failed_drills()


@router.get("/rankings")
async def rank_by_recovery_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_recovery_time()


@router.get("/trends")
async def detect_drill_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_drill_trends()


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


drt_route = router
