"""Runbook scheduler API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/runbook-scheduler", tags=["Runbook Scheduler"])

_scheduler: Any = None


def set_scheduler(scheduler: Any) -> None:
    global _scheduler
    _scheduler = scheduler


def _get_scheduler() -> Any:
    if _scheduler is None:
        raise HTTPException(503, "Runbook scheduler service unavailable")
    return _scheduler


class ScheduleRunbookRequest(BaseModel):
    runbook_id: str
    name: str
    scheduled_at: float
    frequency: str = "once"
    cron_expression: str = ""
    environment: str = "production"
    parameters: dict[str, Any] = Field(default_factory=dict)
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordResultRequest(BaseModel):
    success: bool
    output: str = ""
    error_message: str = ""


@router.post("/schedules")
async def schedule_runbook(
    body: ScheduleRunbookRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scheduler = _get_scheduler()
    schedule = scheduler.schedule_runbook(**body.model_dump())
    return schedule.model_dump()


@router.get("/schedules")
async def list_schedules(
    status: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scheduler = _get_scheduler()
    return [s.model_dump() for s in scheduler.list_schedules(status=status)]


@router.get("/schedules/{schedule_id}")
async def get_schedule(
    schedule_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scheduler = _get_scheduler()
    schedule = scheduler.get_schedule(schedule_id)
    if schedule is None:
        raise HTTPException(404, f"Schedule '{schedule_id}' not found")
    return schedule.model_dump()


@router.delete("/schedules/{schedule_id}")
async def cancel_schedule(
    schedule_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scheduler = _get_scheduler()
    schedule = scheduler.cancel_schedule(schedule_id)
    if schedule is None:
        raise HTTPException(404, f"Schedule '{schedule_id}' not found")
    return schedule.model_dump()


@router.get("/due")
async def get_due(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scheduler = _get_scheduler()
    return [s.model_dump() for s in scheduler.get_due_runbooks()]


@router.post("/schedules/{schedule_id}/execute")
async def execute_scheduled(
    schedule_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scheduler = _get_scheduler()
    execution = scheduler.execute_scheduled(schedule_id)
    if execution is None:
        raise HTTPException(404, f"Schedule '{schedule_id}' not found or not ready")
    return execution.model_dump()


@router.get("/history")
async def get_history(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scheduler = _get_scheduler()
    return [e.model_dump() for e in scheduler.get_execution_history()]


@router.get("/history/{schedule_id}")
async def get_schedule_history(
    schedule_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scheduler = _get_scheduler()
    return [e.model_dump() for e in scheduler.get_execution_history(schedule_id=schedule_id)]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scheduler = _get_scheduler()
    return scheduler.get_stats()
