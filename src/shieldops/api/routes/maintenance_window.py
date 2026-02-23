"""Maintenance window API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/maintenance-windows", tags=["Maintenance Windows"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Maintenance window service unavailable")
    return _manager


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateWindowRequest(BaseModel):
    title: str
    services: list[str] = Field(default_factory=list)
    window_type: str = "planned"
    start_time: float
    end_time: float
    owner: str = ""
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtendWindowRequest(BaseModel):
    new_end_time: float


class CheckConflictsRequest(BaseModel):
    window_id: str | None = None


class NotifyWindowRequest(BaseModel):
    channel: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/windows")
async def create_window(
    body: CreateWindowRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    window = mgr.create_window(**body.model_dump())
    return window.model_dump()


@router.get("/windows")
async def list_windows(
    status: str | None = None,
    service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [w.model_dump() for w in mgr.list_windows(status=status, service=service)]


@router.get("/windows/active")
async def get_active_windows(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [w.model_dump() for w in mgr.get_active_windows()]


@router.get("/windows/{window_id}")
async def get_window(
    window_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    window = mgr.get_window(window_id)
    if window is None:
        raise HTTPException(404, f"Window '{window_id}' not found")
    return window.model_dump()


@router.put("/windows/{window_id}/activate")
async def activate_window(
    window_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    window = mgr.activate_window(window_id)
    if window is None:
        raise HTTPException(404, f"Window '{window_id}' not found")
    return window.model_dump()


@router.put("/windows/{window_id}/complete")
async def complete_window(
    window_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    window = mgr.complete_window(window_id)
    if window is None:
        raise HTTPException(404, f"Window '{window_id}' not found")
    return window.model_dump()


@router.put("/windows/{window_id}/cancel")
async def cancel_window(
    window_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    window = mgr.cancel_window(window_id)
    if window is None:
        raise HTTPException(404, f"Window '{window_id}' not found")
    return window.model_dump()


@router.put("/windows/{window_id}/extend")
async def extend_window(
    window_id: str,
    body: ExtendWindowRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    window = mgr.extend_window(window_id, body.new_end_time)
    if window is None:
        raise HTTPException(404, f"Window '{window_id}' not found")
    return window.model_dump()


@router.post("/conflicts")
async def check_conflicts(
    body: CheckConflictsRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [c.model_dump() for c in mgr.check_conflicts(window_id=body.window_id)]


@router.post("/windows/{window_id}/notify")
async def notify_window(
    window_id: str,
    body: NotifyWindowRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    window = mgr.notify_window(window_id, body.channel)
    if window is None:
        raise HTTPException(404, f"Window '{window_id}' not found")
    return window.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()
