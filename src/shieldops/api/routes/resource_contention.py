"""Resource contention detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.resource_contention import (
    ContentionSeverity,
    ContentionSource,
    ContentionType,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/resource-contention",
    tags=["Resource Contention"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Resource contention service unavailable")
    return _engine


class RecordContentionRequest(BaseModel):
    service_name: str
    contention_type: ContentionType = ContentionType.CPU_THROTTLING
    severity: ContentionSeverity = ContentionSeverity.LOW
    source: ContentionSource = ContentionSource.RESOURCE_LIMIT
    impact_duration_hours: float = 0.0
    details: str = ""


class AddEventRequest(BaseModel):
    event_name: str
    contention_type: ContentionType = ContentionType.CPU_THROTTLING
    severity: ContentionSeverity = ContentionSeverity.LOW
    duration_hours: float = 0.0
    description: str = ""


@router.post("/contentions")
async def record_contention(
    body: RecordContentionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_contention(**body.model_dump())
    return result.model_dump()


@router.get("/contentions")
async def list_contentions(
    service_name: str | None = None,
    contention_type: ContentionType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_contentions(
            service_name=service_name,
            contention_type=contention_type,
            limit=limit,
        )
    ]


@router.get("/contentions/{record_id}")
async def get_contention(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_contention(record_id)
    if result is None:
        raise HTTPException(404, f"Contention '{record_id}' not found")
    return result.model_dump()


@router.post("/events")
async def add_event(
    body: AddEventRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_event(**body.model_dump())
    return result.model_dump()


@router.get("/patterns/{service_name}")
async def analyze_contention_patterns(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_contention_patterns(service_name)


@router.get("/critical")
async def identify_critical_contentions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_contentions()


@router.get("/rankings")
async def rank_by_impact_duration(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact_duration()


@router.get("/recurring")
async def detect_recurring_contentions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_recurring_contentions()


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


rcd_route = router
