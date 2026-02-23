"""Rollback registry API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/rollback-registry", tags=["Rollback Registry"])

_registry: Any = None


def set_registry(registry: Any) -> None:
    global _registry
    _registry = registry


def _get_registry() -> Any:
    if _registry is None:
        raise HTTPException(503, "Rollback registry service unavailable")
    return _registry


class RecordRollbackRequest(BaseModel):
    service: str
    rollback_type: str = "deployment"
    result: str = "success"
    trigger_reason: str = ""
    from_version: str = ""
    to_version: str = ""
    duration_seconds: float = 0.0
    initiated_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/events")
async def record_rollback(
    body: RecordRollbackRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reg = _get_registry()
    event = reg.record_rollback(**body.model_dump())
    return event.model_dump()


@router.get("/events")
async def list_rollbacks(
    service: str | None = None,
    rollback_type: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reg = _get_registry()
    events = reg.list_rollbacks(service=service, rollback_type=rollback_type)
    return [e.model_dump() for e in events]


@router.get("/events/{event_id}")
async def get_rollback(
    event_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reg = _get_registry()
    event = reg.get_rollback(event_id)
    if event is None:
        raise HTTPException(404, f"Rollback event '{event_id}' not found")
    return event.model_dump()


@router.delete("/events/{event_id}")
async def delete_rollback(
    event_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reg = _get_registry()
    removed = reg.delete_rollback(event_id)
    if not removed:
        raise HTTPException(404, f"Rollback event '{event_id}' not found")
    return {"deleted": True, "event_id": event_id}


@router.get("/triggers")
async def analyze_triggers(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reg = _get_registry()
    return [t.model_dump() for t in reg.analyze_triggers()]


@router.get("/patterns")
async def detect_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reg = _get_registry()
    return [p.model_dump() for p in reg.detect_patterns()]


@router.get("/success-rate")
async def get_success_rate(
    service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reg = _get_registry()
    return reg.get_success_rate(service=service)


@router.get("/by-service/{service}")
async def get_by_service(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reg = _get_registry()
    return [e.model_dump() for e in reg.get_rollback_by_service(service)]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reg = _get_registry()
    return reg.get_stats()
