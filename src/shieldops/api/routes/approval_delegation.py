"""Approval delegation API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/approval-delegation", tags=["Approval Delegation"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Approval delegation service unavailable")
    return _engine


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateRuleRequest(BaseModel):
    delegator: str
    delegate: str
    scope: str
    reason: str = "workload"
    expires_at: float | None = None


class CheckDelegationRequest(BaseModel):
    delegate: str
    scope: str
    action_type: str = "approve"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/rules")
async def create_rule(
    body: CreateRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rule = engine.create_rule(**body.model_dump())
    return rule.model_dump()


@router.post("/check")
async def check_delegation(
    body: CheckDelegationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.check_delegation(**body.model_dump())
    return result.model_dump()


@router.delete("/rules/{rule_id}")
async def revoke_rule(
    rule_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    removed = engine.revoke_rule(rule_id)
    if not removed:
        raise HTTPException(404, f"Rule '{rule_id}' not found")
    return {"deleted": True, "rule_id": rule_id}


@router.get("/rules")
async def list_rules(
    delegator: str | None = None,
    active_only: bool = True,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [r.model_dump() for r in engine.list_rules(delegator=delegator, active_only=active_only)]


@router.get("/audit")
async def get_audit_trail(
    delegate: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [e.model_dump() for e in engine.get_audit_trail(delegate=delegate, limit=limit)]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
