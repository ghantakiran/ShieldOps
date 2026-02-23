"""Synthetic monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/synthetic-monitors", tags=["Synthetic Monitors"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Synthetic monitor service unavailable")
    return _manager


class CreateMonitorRequest(BaseModel):
    name: str
    monitor_type: str
    target_url: str
    interval_seconds: int = 60
    timeout_seconds: int = 30
    expected_status_code: int = 200
    regions: list[str] = Field(default_factory=list)
    owner: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordCheckRequest(BaseModel):
    monitor_id: str
    success: bool
    response_time_ms: float = 0.0
    status_code: int | None = None
    region: str = ""
    error_message: str = ""


@router.post("/monitors")
async def create_monitor(
    body: CreateMonitorRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    monitor = manager.create_monitor(**body.model_dump())
    return monitor.model_dump()


@router.get("/monitors")
async def list_monitors(
    status: str | None = None,
    monitor_type: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    return [m.model_dump() for m in manager.list_monitors(status=status, monitor_type=monitor_type)]


@router.get("/monitors/{monitor_id}")
async def get_monitor(
    monitor_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    monitor = manager.get_monitor(monitor_id)
    if monitor is None:
        raise HTTPException(404, f"Monitor '{monitor_id}' not found")
    return monitor.model_dump()


@router.delete("/monitors/{monitor_id}")
async def delete_monitor(
    monitor_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    removed = manager.delete_monitor(monitor_id)
    if not removed:
        raise HTTPException(404, f"Monitor '{monitor_id}' not found")
    return {"deleted": True, "monitor_id": monitor_id}


@router.put("/monitors/{monitor_id}/pause")
async def pause_monitor(
    monitor_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    monitor = manager.pause_monitor(monitor_id)
    if monitor is None:
        raise HTTPException(404, f"Monitor '{monitor_id}' not found")
    return monitor.model_dump()


@router.put("/monitors/{monitor_id}/resume")
async def resume_monitor(
    monitor_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    monitor = manager.resume_monitor(monitor_id)
    if monitor is None:
        raise HTTPException(404, f"Monitor '{monitor_id}' not found")
    return monitor.model_dump()


@router.post("/checks")
async def record_check(
    body: RecordCheckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    check = manager.record_check(**body.model_dump())
    return check.model_dump()


@router.get("/checks")
async def get_check_history(
    monitor_id: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    return [c.model_dump() for c in manager.get_check_history(monitor_id=monitor_id, limit=limit)]


@router.get("/monitors/{monitor_id}/availability")
async def get_availability(
    monitor_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.get_availability(monitor_id)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.get_stats()
