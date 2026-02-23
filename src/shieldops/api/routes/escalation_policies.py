"""Notification escalation policy API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role
from shieldops.integrations.notifications.escalation import (
    EscalationPolicy,
    EscalationStep,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/escalation-policies", tags=["Escalation Policies"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Escalation service unavailable")
    return _engine


class CreatePolicyRequest(BaseModel):
    name: str
    description: str = ""
    steps: list[EscalationStep] = Field(default_factory=list)
    max_duration_seconds: int = 300
    severity_filter: list[str] = Field(default_factory=list)
    enabled: bool = True


class UpdatePolicyRequest(BaseModel):
    description: str | None = None
    steps: list[EscalationStep] | None = None
    max_duration_seconds: int | None = None
    severity_filter: list[str] | None = None
    enabled: bool | None = None


@router.get("")
async def list_escalation_policies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    eng = _get_engine()
    return [p.model_dump() for p in eng.list_policies()]


@router.post("")
async def create_escalation_policy(
    body: CreatePolicyRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    policy = EscalationPolicy(**body.model_dump())
    return eng.register_policy(policy).model_dump()


@router.get("/{name}")
async def get_escalation_policy(
    name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    policy = eng.get_policy(name)
    if policy is None:
        raise HTTPException(404, f"Policy '{name}' not found")
    return policy.model_dump()


@router.put("/{name}")
async def update_escalation_policy(
    name: str,
    body: UpdatePolicyRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    policy = eng.update_policy(name, updates)
    if policy is None:
        raise HTTPException(404, f"Policy '{name}' not found")
    return policy.model_dump()


@router.delete("/{name}")
async def delete_escalation_policy(
    name: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, str]:
    eng = _get_engine()
    if not eng.delete_policy(name):
        raise HTTPException(404, f"Policy '{name}' not found")
    return {"deleted": name}


@router.post("/{name}/test")
async def test_escalation_policy(
    name: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    result = await eng.test_policy(name)
    return result.model_dump()


@router.get("/history/recent")
async def get_escalation_history(
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    eng = _get_engine()
    return [r.model_dump() for r in eng.get_history(limit)]
