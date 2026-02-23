"""Dependency health tracking API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/dependency-health", tags=["Dependency Health"])

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Dependency health service unavailable")
    return _tracker


class RegisterDependencyRequest(BaseModel):
    name: str
    dependency_type: str = "api"
    upstream_of: list[str] = Field(default_factory=list)
    downstream_of: list[str] = Field(default_factory=list)
    endpoint: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordCheckRequest(BaseModel):
    dependency_id: str
    status: str
    latency_ms: float = 0.0
    error_message: str = ""


@router.post("/dependencies")
async def register_dependency(
    body: RegisterDependencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    dep = tracker.register_dependency(**body.model_dump())
    return dep.model_dump()


@router.get("/dependencies")
async def list_dependencies(
    status: str | None = None,
    dep_type: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [d.model_dump() for d in tracker.list_dependencies(status=status, dep_type=dep_type)]


@router.get("/dependencies/{dep_id}")
async def get_dependency(
    dep_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    dep = tracker.get_dependency(dep_id)
    if dep is None:
        raise HTTPException(404, f"Dependency '{dep_id}' not found")
    return dep.model_dump()


@router.delete("/dependencies/{dep_id}")
async def remove_dependency(
    dep_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    removed = tracker.remove_dependency(dep_id)
    if not removed:
        raise HTTPException(404, f"Dependency '{dep_id}' not found")
    return {"deleted": True, "dependency_id": dep_id}


@router.post("/checks")
async def record_check(
    body: RecordCheckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    check = tracker.record_health_check(**body.model_dump())
    return check.model_dump()


@router.get("/cascades")
async def get_cascades(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [c.model_dump() for c in tracker.detect_cascades()]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
