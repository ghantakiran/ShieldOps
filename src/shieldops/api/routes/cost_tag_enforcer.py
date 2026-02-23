"""Cost allocation tag enforcement API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/cost-tag-enforcer",
    tags=["Cost Tag Enforcer"],
)

_enforcer: Any = None


def set_enforcer(enforcer: Any) -> None:
    global _enforcer
    _enforcer = enforcer


def _get_enforcer() -> Any:
    if _enforcer is None:
        raise HTTPException(503, "Cost tag enforcer service unavailable")
    return _enforcer


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreatePolicyRequest(BaseModel):
    name: str
    required_tags: list[str] = Field(default_factory=list)
    enforcement_mode: str = "audit"
    resource_types: list[str] = Field(default_factory=list)
    default_values: dict[str, str] = Field(default_factory=dict)


class UpdatePolicyRequest(BaseModel):
    name: str | None = None
    required_tags: list[str] | None = None
    enforcement_mode: str | None = None
    default_values: dict[str, str] | None = None


class CheckResourceRequest(BaseModel):
    resource_id: str
    resource_type: str = ""
    existing_tags: dict[str, str] = Field(default_factory=dict)
    policy_id: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/policies")
async def create_policy(
    body: CreatePolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    enforcer = _get_enforcer()
    policy = enforcer.create_policy(
        name=body.name,
        required_tags=body.required_tags,
        enforcement_mode=body.enforcement_mode,
        resource_types=body.resource_types,
        default_values=body.default_values,
    )
    return policy.model_dump()


@router.get("/policies")
async def list_policies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    enforcer = _get_enforcer()
    return [p.model_dump() for p in enforcer.list_policies()]


@router.put("/policies/{policy_id}")
async def update_policy(
    policy_id: str,
    body: UpdatePolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    enforcer = _get_enforcer()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    policy = enforcer.update_policy(policy_id, **updates)
    if policy is None:
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return policy.model_dump()


@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    enforcer = _get_enforcer()
    deleted = enforcer.delete_policy(policy_id)
    if not deleted:
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return {"deleted": True, "policy_id": policy_id}


@router.post("/check")
async def check_resource(
    body: CheckResourceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    enforcer = _get_enforcer()
    check = enforcer.check_resource(
        resource_id=body.resource_id,
        resource_type=body.resource_type,
        existing_tags=body.existing_tags,
        policy_id=body.policy_id,
    )
    return check.model_dump()


@router.post("/checks/{check_id}/enforce")
async def enforce_check(
    check_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    enforcer = _get_enforcer()
    action = enforcer.enforce(check_id)
    if action is None:
        raise HTTPException(404, f"Check '{check_id}' not found")
    return action.model_dump()


@router.get("/checks")
async def list_checks(
    status: str | None = None,
    resource_type: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    enforcer = _get_enforcer()
    checks = enforcer.list_checks(status=status, resource_type=resource_type, limit=limit)
    return [c.model_dump() for c in checks]


@router.get("/actions")
async def list_actions(
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    enforcer = _get_enforcer()
    return [a.model_dump() for a in enforcer.list_actions(limit=limit)]


@router.get("/compliance-summary")
async def get_compliance_summary(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    enforcer = _get_enforcer()
    return enforcer.get_compliance_summary()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    enforcer = _get_enforcer()
    return enforcer.get_stats()
