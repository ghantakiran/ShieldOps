"""Service catalog API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/service-catalog",
    tags=["Service Catalog"],
)

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Service catalog service unavailable")
    return _manager


class RegisterServiceRequest(BaseModel):
    name: str
    tier: str = "tier_2"
    lifecycle: str = "incubating"
    owner: str = ""
    team: str = ""
    description: str = ""
    repository_url: str = ""
    documentation: dict[str, str] = {}
    dependencies: list[str] = []
    tags: list[str] = []


class UpdateServiceRequest(BaseModel):
    name: str | None = None
    tier: str | None = None
    lifecycle: str | None = None
    owner: str | None = None
    team: str | None = None
    description: str | None = None
    repository_url: str | None = None


@router.post("/services")
async def register_service(
    body: RegisterServiceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    entry = mgr.register_service(
        name=body.name,
        tier=body.tier,
        lifecycle=body.lifecycle,
        owner=body.owner,
        team=body.team,
        description=body.description,
        repository_url=body.repository_url,
        documentation=body.documentation,
        dependencies=body.dependencies,
        tags=body.tags,
    )
    return entry.model_dump()


@router.get("/services")
async def list_services(
    tier: str | None = None,
    lifecycle: str | None = None,
    team: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    result = mgr.search_services(tier=tier, lifecycle=lifecycle, team=team)
    return [s.model_dump() for s in result.services[-limit:]]


@router.get("/services/{service_id}")
async def get_service(
    service_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    entry = mgr.get_service(service_id)
    if entry is None:
        raise HTTPException(404, f"Service '{service_id}' not found")
    return entry.model_dump()


@router.put("/services/{service_id}")
async def update_service(
    service_id: str,
    body: UpdateServiceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    entry = mgr.update_service(service_id, **updates)
    if entry is None:
        raise HTTPException(404, f"Service '{service_id}' not found")
    return entry.model_dump()


@router.delete("/services/{service_id}")
async def decommission_service(
    service_id: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    entry = mgr.decommission_service(service_id)
    if entry is None:
        raise HTTPException(404, f"Service '{service_id}' not found")
    return entry.model_dump()


@router.get("/services/{service_id}/dependencies")
async def list_dependencies(
    service_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    deps = mgr.list_dependencies(service_id)
    return [d.model_dump() for d in deps]


@router.get("/services/{service_id}/dependents")
async def get_dependents(
    service_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    deps = mgr.get_dependents(service_id)
    return [d.model_dump() for d in deps]


@router.get("/stale")
async def get_stale_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    stale = mgr.get_stale_services()
    return [s.model_dump() for s in stale]


@router.post("/validate")
async def validate_completeness(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.validate_catalog_completeness()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()
