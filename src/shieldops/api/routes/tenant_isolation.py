"""Tenant resource isolation API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/tenant-isolation",
    tags=["Tenant Isolation"],
)

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Tenant isolation service unavailable")
    return _manager


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RegisterTenantRequest(BaseModel):
    tenant_name: str
    namespace: str = ""
    isolation_level: str = "soft"
    resource_limits: dict[str, float] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class UpdateUsageRequest(BaseModel):
    resource_type: str
    value: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/tenants")
async def register_tenant(
    body: RegisterTenantRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    tenant = mgr.register_tenant(
        tenant_name=body.tenant_name,
        namespace=body.namespace,
        isolation_level=body.isolation_level,
        resource_limits=body.resource_limits,
        tags=body.tags,
    )
    return tenant.model_dump()


@router.get("/tenants")
async def list_tenants(
    isolation_level: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    tenants = mgr.list_tenants(isolation_level=isolation_level)
    return [t.model_dump() for t in tenants[-limit:]]


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    tenant = mgr.get_tenant(tenant_id)
    if tenant is None:
        raise HTTPException(404, f"Tenant '{tenant_id}' not found")
    return tenant.model_dump()


@router.put("/tenants/{tenant_id}/usage")
async def update_usage(
    tenant_id: str,
    body: UpdateUsageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    tenant = mgr.update_usage(tenant_id, body.resource_type, body.value)
    if tenant is None:
        raise HTTPException(404, f"Tenant '{tenant_id}' not found")
    return tenant.model_dump()


@router.post("/tenants/{tenant_id}/check")
async def check_limits(
    tenant_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    violations = mgr.check_limits(tenant_id)
    return [v.model_dump() for v in violations]


@router.get("/violations")
async def list_violations(
    tenant_id: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    violations = mgr.list_violations(tenant_id=tenant_id, severity=severity)
    return [v.model_dump() for v in violations[-limit:]]


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    deleted = mgr.delete_tenant(tenant_id)
    if not deleted:
        raise HTTPException(404, f"Tenant '{tenant_id}' not found")
    return {"deleted": True, "tenant_id": tenant_id}


@router.get("/utilization")
async def get_utilization(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return mgr.get_utilization_report()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()
