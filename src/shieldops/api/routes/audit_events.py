"""Audit event bus API routes."""

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query, status

from shieldops.audit.event_bus import AuditEventBus

logger = structlog.get_logger()
router = APIRouter(prefix="/audit/events", tags=["Audit Events"])

_bus: AuditEventBus | None = None


def set_bus(bus: AuditEventBus) -> None:
    global _bus
    _bus = bus


def _get_bus() -> AuditEventBus:
    if _bus is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit event bus not initialized",
        )
    return _bus


@router.get("")
async def list_audit_events(
    category: str | None = Query(None),
    actor: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Query audit events."""
    bus = _get_bus()
    events = bus.query_events(
        category=category,
        actor=actor,
        action=action,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [e.model_dump() for e in events],
        "total": bus.event_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/summary")
async def audit_summary() -> dict[str, Any]:
    """Get audit event counts by category/actor."""
    bus = _get_bus()
    return bus.summary().model_dump()


@router.get("/{event_id}")
async def get_audit_event(event_id: str) -> dict[str, Any]:
    """Get audit event detail."""
    bus = _get_bus()
    event = bus.get_event(event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit event '{event_id}' not found",
        )
    return event.model_dump()
