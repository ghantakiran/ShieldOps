"""API lifecycle management routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.api.versioning.lifecycle import DeprecationStatus

logger = structlog.get_logger()
router = APIRouter(prefix="/api-lifecycle", tags=["API Lifecycle"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "API lifecycle service unavailable")
    return _manager


class DeprecateRequest(BaseModel):
    path: str
    method: str = "GET"
    sunset_date: str | None = None
    replacement_path: str | None = None
    migration_guide: str = ""


@router.get("/endpoints")
async def list_endpoints(
    status: DeprecationStatus | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [e.model_dump() for e in mgr.list_endpoints(status)]


@router.get("/deprecated")
async def list_deprecated(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [e.model_dump() for e in mgr.get_deprecated()]


@router.post("/deprecate")
async def deprecate_endpoint(
    body: DeprecateRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    ep = mgr.deprecate(
        body.path,
        body.method,
        body.sunset_date,
        body.replacement_path,
        body.migration_guide,
    )
    if ep is None:
        raise HTTPException(404, "Endpoint not found")
    return ep.model_dump()


@router.get("/endpoints/{path:path}/migration")
async def get_migration_guide(
    path: str,
    method: str = "GET",
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, str]:
    mgr = _get_manager()
    guide = mgr.get_migration_guide(f"/{path}", method)
    return {"path": f"/{path}", "method": method, "migration_guide": guide}


@router.get("/stats")
async def get_lifecycle_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()
