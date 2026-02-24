"""Deployment approval gate API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/deployment-gate",
    tags=["Deployment Gate"],
)

_instance: Any = None


def set_gate_manager(manager: Any) -> None:
    global _instance
    _instance = manager


def _get_gate_manager() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Deployment gate service unavailable",
        )
    return _instance


class CreateGateRequest(BaseModel):
    deployment_id: str
    service_name: str = ""
    gate_type: str = "manual_review"
    approval_level: str = "team_lead"
    reason: str = ""
    pre_checks: list[str] = Field(
        default_factory=list,
    )


class GateDecisionRequest(BaseModel):
    approver: str
    rationale: str = ""


@router.post("/gates")
async def create_gate(
    body: CreateGateRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_gate_manager()
    gate = mgr.create_gate(**body.model_dump())
    return gate.model_dump()


@router.get("/gates")
async def list_gates(
    deployment_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_gate_manager()
    return [
        g.model_dump()
        for g in mgr.list_gates(
            deployment_id=deployment_id,
            status=status,
            limit=limit,
        )
    ]


@router.get("/gates/{gate_id}")
async def get_gate(
    gate_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_gate_manager()
    gate = mgr.get_gate(gate_id)
    if gate is None:
        raise HTTPException(
            404,
            f"Gate '{gate_id}' not found",
        )
    return gate.model_dump()


@router.post("/gates/{gate_id}/approve")
async def approve_gate(
    gate_id: str,
    body: GateDecisionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_gate_manager()
    gate = mgr.approve_gate(
        gate_id,
        body.approver,
        body.rationale,
    )
    if gate is None:
        raise HTTPException(
            404,
            f"Gate '{gate_id}' not found",
        )
    return gate.model_dump()


@router.post("/gates/{gate_id}/reject")
async def reject_gate(
    gate_id: str,
    body: GateDecisionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_gate_manager()
    gate = mgr.reject_gate(
        gate_id,
        body.approver,
        body.rationale,
    )
    if gate is None:
        raise HTTPException(
            404,
            f"Gate '{gate_id}' not found",
        )
    return gate.model_dump()


@router.post("/gates/{gate_id}/auto-approve")
async def evaluate_auto_approval(
    gate_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_gate_manager()
    gate = mgr.evaluate_auto_approval(gate_id)
    if gate is None:
        raise HTTPException(
            404,
            f"Gate '{gate_id}' not found",
        )
    return gate.model_dump()


@router.post("/check-expiry")
async def check_expiry(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_gate_manager()
    expired = mgr.check_gate_expiry()
    return [g.model_dump() for g in expired]


@router.get("/velocity")
async def approval_velocity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_gate_manager()
    return mgr.calculate_approval_velocity()


@router.get("/report")
async def gate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_gate_manager()
    return mgr.generate_gate_report().model_dump()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_gate_manager()
    count = mgr.clear_data()
    return {"cleared": count}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_gate_manager()
    return mgr.get_stats()
