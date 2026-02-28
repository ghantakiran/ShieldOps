"""Tenant quota manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.tenant_quota import (
    EnforcementAction,
    QuotaStatus,
    ResourceType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/tenant-quota",
    tags=["Tenant Quota"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Tenant quota service unavailable")
    return _engine


class RecordQuotaRequest(BaseModel):
    tenant_name: str
    resource_type: ResourceType = ResourceType.CPU
    status: QuotaStatus = QuotaStatus.WITHIN_LIMIT
    utilization_pct: float = 0.0
    details: str = ""


class AddPolicyRequest(BaseModel):
    policy_name: str
    resource_type: ResourceType = ResourceType.CPU
    action: EnforcementAction = EnforcementAction.NO_ACTION
    limit_value: float = 0.0
    description: str = ""


@router.post("/quotas")
async def record_quota(
    body: RecordQuotaRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_quota(**body.model_dump())
    return result.model_dump()


@router.get("/quotas")
async def list_quotas(
    tenant_name: str | None = None,
    resource_type: ResourceType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_quotas(
            tenant_name=tenant_name, resource_type=resource_type, limit=limit
        )
    ]


@router.get("/quotas/{record_id}")
async def get_quota(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_quota(record_id)
    if result is None:
        raise HTTPException(404, f"Quota '{record_id}' not found")
    return result.model_dump()


@router.post("/policies")
async def add_policy(
    body: AddPolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_policy(**body.model_dump())
    return result.model_dump()


@router.get("/utilization/{tenant_name}")
async def analyze_tenant_utilization(
    tenant_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_tenant_utilization(tenant_name)


@router.get("/exceeded")
async def identify_exceeded_quotas(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_exceeded_quotas()


@router.get("/rankings")
async def rank_by_utilization(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_utilization()


@router.get("/trends")
async def detect_quota_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_quota_trends()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    return engine.clear_data()


tqm_route = router
