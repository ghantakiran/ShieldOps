"""Status page management API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/status-page", tags=["Status Page"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Status page service unavailable")
    return _manager


class CreateComponentRequest(BaseModel):
    name: str
    description: str = ""
    group: str = ""
    display_order: int = 0
    visibility: str = "public"
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateComponentStatusRequest(BaseModel):
    status: str


class CreateIncidentRequest(BaseModel):
    title: str
    description: str = ""
    severity: str = "minor"
    affected_components: list[str] = Field(default_factory=list)


class AddIncidentUpdateRequest(BaseModel):
    message: str
    status: str = "investigating"


@router.post("/components")
async def create_component(
    body: CreateComponentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    comp = mgr.create_component(**body.model_dump())
    return comp.model_dump()


@router.get("/components")
async def list_components(
    status: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [c.model_dump() for c in mgr.list_components(status=status)]


@router.put("/components/{component_id}/status")
async def update_component_status(
    component_id: str,
    body: UpdateComponentStatusRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    comp = mgr.update_component_status(component_id, body.status)
    if comp is None:
        raise HTTPException(404, f"Component '{component_id}' not found")
    return comp.model_dump()


@router.post("/incidents")
async def create_incident(
    body: CreateIncidentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    incident = mgr.create_incident(**body.model_dump())
    return incident.model_dump()


@router.post("/incidents/{incident_id}/updates")
async def add_incident_update(
    incident_id: str,
    body: AddIncidentUpdateRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    update = mgr.add_incident_update(incident_id, **body.model_dump())
    if update is None:
        raise HTTPException(404, f"Incident '{incident_id}' not found")
    return update.model_dump()


@router.put("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    incident = mgr.resolve_incident(incident_id)
    if incident is None:
        raise HTTPException(404, f"Incident '{incident_id}' not found")
    return incident.model_dump()


@router.get("/incidents")
async def list_incidents(
    active_only: bool = False,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [i.model_dump() for i in mgr.list_incidents(active_only=active_only)]


@router.get("")
async def get_page(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_page()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()
