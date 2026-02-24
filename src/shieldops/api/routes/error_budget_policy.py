"""Error budget policy API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.error_budget_policy import (
    BudgetStatus,
    BudgetWindow,
    PolicyAction,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/error-budget-policy",
    tags=["Error Budget Policy"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Error budget policy service unavailable")
    return _engine


class CreatePolicyRequest(BaseModel):
    service_name: str
    slo_target_pct: float = 99.9
    window: BudgetWindow = BudgetWindow.MONTHLY


class ConsumeBudgetRequest(BaseModel):
    error_pct: float


class TriggerActionRequest(BaseModel):
    action: PolicyAction


@router.post("/policies")
async def create_policy(
    body: CreatePolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    policy = engine.create_policy(**body.model_dump())
    return policy.model_dump()


@router.get("/policies")
async def list_policies(
    service_name: str | None = None,
    status: BudgetStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        p.model_dump()
        for p in engine.list_policies(
            service_name=service_name,
            status=status,
            limit=limit,
        )
    ]


@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    policy = engine.get_policy(policy_id)
    if policy is None:
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return policy.model_dump()


@router.post("/policies/{policy_id}/consume")
async def consume_budget(
    policy_id: str,
    body: ConsumeBudgetRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.consume_budget(policy_id, body.error_pct)
    if result.get("error"):
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return result


@router.post("/policies/{policy_id}/evaluate")
async def evaluate_policy(
    policy_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.evaluate_policy(policy_id)
    if result.get("error"):
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return result


@router.post("/policies/{policy_id}/trigger")
async def trigger_action(
    policy_id: str,
    body: TriggerActionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.trigger_action(policy_id, body.action)
    if result.get("error"):
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return result


@router.get("/policies/{policy_id}/burn-rate")
async def get_burn_rate(
    policy_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.calculate_burn_rate(policy_id)
    if result.get("error"):
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return result


@router.post("/policies/{policy_id}/reset")
async def reset_budget(
    policy_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.reset_budget(policy_id)
    if result.get("error"):
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return result


@router.get("/report")
async def get_budget_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_budget_report().model_dump()


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
