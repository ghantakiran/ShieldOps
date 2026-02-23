"""Deployment freeze management API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/deployment-freezes", tags=["Deployment Freezes"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Deployment freeze service unavailable")
    return _manager


class CreateFreezeRequest(BaseModel):
    name: str
    start_time: float
    end_time: float
    scope: str = "all"
    environments: list[str] = Field(default_factory=list)
    reason: str = ""
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddExceptionRequest(BaseModel):
    service: str
    reason: str
    approved_by: str = ""


class CheckFrozenRequest(BaseModel):
    environment: str = "production"
    service: str = ""


@router.post("")
async def create_freeze(
    body: CreateFreezeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    freeze = mgr.create_freeze(**body.model_dump())
    return freeze.model_dump()


@router.get("")
async def list_freezes(
    status: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [f.model_dump() for f in mgr.list_freezes(status=status)]


@router.get("/active")
async def get_active_freezes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [f.model_dump() for f in mgr.get_active_freezes()]


@router.get("/{freeze_id}")
async def get_freeze(
    freeze_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    freeze = mgr.get_freeze(freeze_id)
    if freeze is None:
        raise HTTPException(404, f"Freeze '{freeze_id}' not found")
    return freeze.model_dump()


@router.delete("/{freeze_id}")
async def cancel_freeze(
    freeze_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    freeze = mgr.cancel_freeze(freeze_id)
    if freeze is None:
        raise HTTPException(404, f"Freeze '{freeze_id}' not found")
    return freeze.model_dump()


@router.post("/{freeze_id}/exceptions")
async def add_exception(
    freeze_id: str,
    body: AddExceptionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    exc = mgr.add_exception(freeze_id=freeze_id, **body.model_dump())
    return exc.model_dump()


@router.post("/check")
async def check_frozen(
    body: CheckFrozenRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    result = mgr.check_frozen(**body.model_dump())
    return result.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()
