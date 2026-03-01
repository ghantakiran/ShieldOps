"""Capacity bottleneck detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.bottleneck_detector import (
    BottleneckSeverity,
    BottleneckType,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/bottleneck-detector",
    tags=["Bottleneck Detector"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Bottleneck detector service unavailable")
    return _engine


class RecordBottleneckRequest(BaseModel):
    model_config = {"extra": "forbid"}

    service: str
    bottleneck_type: BottleneckType = BottleneckType.CPU
    severity: BottleneckSeverity = BottleneckSeverity.NONE
    utilization_pct: float = 0.0
    duration_minutes: float = 0.0
    team: str = ""
    details: str = ""


class AddEventRequest(BaseModel):
    model_config = {"extra": "forbid"}

    record_id: str
    event_type: str = ""
    impact_score: float = 0.0
    affected_users: int = 0


@router.post("/bottlenecks")
async def record_bottleneck(
    body: RecordBottleneckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_bottleneck(**body.model_dump())
    return result.model_dump()


@router.get("/bottlenecks")
async def list_bottlenecks(
    bottleneck_type: BottleneckType | None = None,
    severity: BottleneckSeverity | None = None,
    service: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_bottlenecks(
            bottleneck_type=bottleneck_type,
            severity=severity,
            service=service,
            limit=limit,
        )
    ]


@router.get("/bottlenecks/{record_id}")
async def get_bottleneck(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_bottleneck(record_id)
    if result is None:
        raise HTTPException(404, f"Bottleneck record '{record_id}' not found")
    return result.model_dump()


@router.post("/events")
async def add_event(
    body: AddEventRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_event(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_bottleneck_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_bottleneck_patterns()


@router.get("/critical")
async def identify_critical_bottlenecks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_bottlenecks()


@router.get("/rankings")
async def rank_by_utilization(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_utilization()


@router.get("/trends")
async def detect_bottleneck_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_bottleneck_trends()


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


cbd_route = router
