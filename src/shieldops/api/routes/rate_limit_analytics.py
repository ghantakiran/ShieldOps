"""Rate limit analytics API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/rate-limit-analytics", tags=["Rate Limit Analytics"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Rate limit analytics service unavailable")
    return _engine


class RecordEventRequest(BaseModel):
    client_id: str
    endpoint: str
    action: str = "allowed"
    request_count: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/events")
async def record_event(
    body: RecordEventRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    event = engine.record_event(**body.model_dump())
    return event.model_dump()


@router.get("/top-offenders")
async def top_offenders(
    limit: int = 10,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [o.model_dump() for o in engine.get_top_offenders(limit=limit)]


@router.get("/utilization")
async def get_utilization(
    endpoint: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [u.model_dump() for u in engine.get_utilization(endpoint=endpoint)]


@router.get("/trends")
async def get_trends(
    period: str = "hour",
    hours: int = 24,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [t.model_dump() for t in engine.get_trends(period=period, hours=hours)]


@router.get("/bursts")
async def get_bursts(
    window_seconds: int = 60,
    threshold: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.get_burst_detection(window_seconds=window_seconds, threshold=threshold)


@router.get("/events")
async def list_events(
    client_id: str | None = None,
    endpoint: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        e.model_dump()
        for e in engine.list_events(client_id=client_id, endpoint=endpoint, limit=limit)
    ]


@router.get("/endpoints/{path:path}")
async def get_endpoint_analytics(
    path: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_endpoint_analytics(path)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
