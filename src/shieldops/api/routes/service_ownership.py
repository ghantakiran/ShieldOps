"""Service ownership API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.ownership import OwnershipStatus

logger = structlog.get_logger()
router = APIRouter(prefix="/service-ownership", tags=["Service Ownership"])

_registry: Any = None


def set_registry(registry: Any) -> None:
    global _registry
    _registry = registry


def _get_registry() -> Any:
    if _registry is None:
        raise HTTPException(503, "Service ownership service unavailable")
    return _registry


class RegisterOwnerRequest(BaseModel):
    service_id: str
    team_id: str
    team_name: str
    service_name: str = ""
    escalation_contacts: list[dict[str, Any]] = Field(default_factory=list)
    description: str = ""
    repository_url: str = ""
    documentation_url: str = ""
    tier: str = "tier-3"
    tags: list[str] = Field(default_factory=list)
    team_slack: str = ""
    team_email: str = ""
    team_manager: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("")
async def register_owner(
    body: RegisterOwnerRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reg = _get_registry()
    owner = reg.register_owner(**body.model_dump())
    return owner.model_dump()


@router.get("/orphaned")
async def get_orphaned_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reg = _get_registry()
    return [o.model_dump() for o in reg.find_orphaned_services()]


@router.get("/team/{team_id}")
async def get_team_services(
    team_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reg = _get_registry()
    return [o.model_dump() for o in reg.get_team_services(team_id)]


@router.get("/escalation/{service_id}")
async def get_escalation_path(
    service_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reg = _get_registry()
    return [c.model_dump() for c in reg.get_escalation_path(service_id)]


@router.get("/{service_id}")
async def get_service_owner(
    service_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reg = _get_registry()
    owner = reg.get_owner(service_id)
    if owner is None:
        raise HTTPException(404, f"Service '{service_id}' not found")
    return owner.model_dump()


@router.get("")
async def list_owners(
    status: OwnershipStatus | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reg = _get_registry()
    return [o.model_dump() for o in reg.list_owners(status=status, limit=limit)]
