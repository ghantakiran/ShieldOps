"""Temporal pattern discovery API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/temporal-patterns", tags=["Temporal Patterns"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Temporal patterns service unavailable")
    return _engine


class RecordEventRequest(BaseModel):
    service: str
    incident_type: str
    severity: str = "warning"
    timestamp: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/events")
async def record_event(
    body: RecordEventRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    event = engine.record_event(**body.model_dump())
    return event.model_dump()


@router.get("/patterns")
async def detect_patterns(
    service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [p.model_dump() for p in engine.detect_patterns(service=service)]


@router.get("/summary/{service}")
async def get_service_summary(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_service_summary(service).model_dump()


@router.get("/risk-windows/{service}")
async def get_risk_windows(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.get_risk_windows(service)


@router.delete("/events")
async def clear_events(
    before_timestamp: float | None = None,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, int]:
    engine = _get_engine()
    count = engine.clear_events(before_timestamp=before_timestamp)
    return {"cleared": count}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
