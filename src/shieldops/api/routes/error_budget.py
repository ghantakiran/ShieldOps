"""Error budget tracking API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/error-budgets", tags=["Error Budgets"])

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Error budget service unavailable")
    return _tracker


class CreatePolicyRequest(BaseModel):
    service: str
    slo_target: float
    period: str = "monthly"
    warning_threshold: float | None = None
    critical_threshold: float | None = None
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordConsumptionRequest(BaseModel):
    policy_id: str
    error_minutes: float
    total_minutes: float
    description: str = ""


class GateCheckRequest(BaseModel):
    service: str


@router.post("/policies")
async def create_policy(
    body: CreatePolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    policy = tracker.create_policy(**body.model_dump())
    return policy.model_dump()


@router.get("/policies")
async def list_policies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [p.model_dump() for p in tracker.list_policies()]


@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    policy = tracker.get_policy(policy_id)
    if policy is None:
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return policy.model_dump()


@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    removed = tracker.delete_policy(policy_id)
    if not removed:
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return {"deleted": True, "policy_id": policy_id}


@router.post("/consume")
async def record_consumption(
    body: RecordConsumptionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    consumption = tracker.record_consumption(**body.model_dump())
    return consumption.model_dump()


@router.get("/remaining/{service}")
async def get_remaining(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_remaining_budget(service)


@router.post("/gate-check")
async def gate_check(
    body: GateCheckRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.check_deployment_gate(body.service)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
