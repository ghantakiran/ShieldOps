"""Disaster recovery readiness API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dr-readiness",
    tags=["DR Readiness"],
)

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "DR readiness service unavailable")
    return _tracker


class RegisterPlanRequest(BaseModel):
    service: str
    rto_minutes: int = 60
    rpo_minutes: int = 30
    mttr_minutes: int = 45
    wrt_minutes: int = 15
    owner: str = ""


class UpdatePlanRequest(BaseModel):
    rto_minutes: int | None = None
    rpo_minutes: int | None = None
    mttr_minutes: int | None = None
    wrt_minutes: int | None = None
    owner: str | None = None


class ScheduleDrillRequest(BaseModel):
    plan_id: str


class CompleteDrillRequest(BaseModel):
    passed: bool = True
    actual_rto_minutes: float | None = None
    actual_rpo_minutes: float | None = None
    notes: str = ""


@router.post("/plans")
async def register_plan(
    body: RegisterPlanRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    plan = tracker.register_plan(
        service=body.service,
        rto_minutes=body.rto_minutes,
        rpo_minutes=body.rpo_minutes,
        mttr_minutes=body.mttr_minutes,
        wrt_minutes=body.wrt_minutes,
        owner=body.owner,
    )
    return plan.model_dump()


@router.get("/plans")
async def list_plans(
    service: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    plans = tracker.list_plans(service=service)
    return [p.model_dump() for p in plans[-limit:]]


@router.get("/plans/{plan_id}")
async def get_plan(
    plan_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    plan = tracker.get_plan(plan_id)
    if plan is None:
        raise HTTPException(404, f"Plan '{plan_id}' not found")
    return plan.model_dump()


@router.put("/plans/{plan_id}")
async def update_plan(
    plan_id: str,
    body: UpdatePlanRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    plan = tracker.update_plan(plan_id, **updates)
    if plan is None:
        raise HTTPException(404, f"Plan '{plan_id}' not found")
    return plan.model_dump()


@router.post("/drills")
async def schedule_drill(
    body: ScheduleDrillRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    drill = tracker.schedule_drill(plan_id=body.plan_id)
    if drill is None:
        raise HTTPException(404, f"Plan '{body.plan_id}' not found")
    return drill.model_dump()


@router.put("/drills/{drill_id}/complete")
async def complete_drill(
    drill_id: str,
    body: CompleteDrillRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    drill = tracker.complete_drill(
        drill_id,
        passed=body.passed,
        actual_rto_minutes=body.actual_rto_minutes,
        actual_rpo_minutes=body.actual_rpo_minutes,
        notes=body.notes,
    )
    if drill is None:
        raise HTTPException(404, f"Drill '{drill_id}' not found")
    return drill.model_dump()


@router.get("/drills")
async def list_drills(
    plan_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    drills = tracker.list_drills(plan_id=plan_id, status=status)
    return [d.model_dump() for d in drills[-limit:]]


@router.get("/readiness/{service}")
async def assess_readiness(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.assess_readiness(service).model_dump()


@router.get("/overdue")
async def get_overdue_drills(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    overdue = tracker.get_overdue_drills()
    return [p.model_dump() for p in overdue]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
