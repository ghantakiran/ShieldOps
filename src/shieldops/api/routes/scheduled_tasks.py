"""Scheduled tasks API routes — create, list, update, delete, trigger."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled-tasks"])

# In-memory store (swap for DB-backed repository later)
_tasks: dict[str, dict[str, Any]] = {}


# ── Enums ────────────────────────────────────────────────────


class ScheduleFrequency(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CRON = "cron"


# ── Request / Response bodies ────────────────────────────────


class ScheduledTask(BaseModel):
    """Scheduled task representation."""

    id: str
    name: str
    prompt: str
    workflow_type: str
    frequency: ScheduleFrequency
    cron_expression: str | None = None
    enabled: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime
    created_by: str
    run_count: int = 0
    last_status: str | None = None


class CreateScheduledTaskBody(BaseModel):
    """Request body for creating a scheduled task."""

    name: str = Field(..., min_length=1, max_length=255)
    prompt: str = Field(..., min_length=1, max_length=5000)
    workflow_type: str = Field(..., min_length=1, max_length=100)
    frequency: ScheduleFrequency
    cron_expression: str | None = Field(
        default=None,
        max_length=100,
        description="Cron expression, required when frequency is 'cron'",
    )
    enabled: bool = True


class UpdateScheduledTaskBody(BaseModel):
    """Request body for updating a scheduled task."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    prompt: str | None = Field(default=None, min_length=1, max_length=5000)
    frequency: ScheduleFrequency | None = None
    cron_expression: str | None = Field(default=None, max_length=100)
    enabled: bool | None = None


class TriggerResult(BaseModel):
    """Result of manually triggering a scheduled task."""

    task_id: str
    triggered_at: datetime
    status: str


# ── Helpers ──────────────────────────────────────────────────


def _task_to_dict(task_data: dict[str, Any]) -> dict[str, Any]:
    """Ensure datetime fields are serialised as ISO strings."""
    out = {**task_data}
    for key in ("created_at", "last_run_at", "next_run_at"):
        val = out.get(key)
        if isinstance(val, datetime):
            out[key] = val.isoformat()
    return out


# ── Endpoints ────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_scheduled_task(
    body: CreateScheduledTaskBody,
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a new scheduled task."""
    if body.frequency == ScheduleFrequency.CRON and not body.cron_expression:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cron_expression is required when frequency is 'cron'",
        )

    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    task: dict[str, Any] = {
        "id": task_id,
        "name": body.name,
        "prompt": body.prompt,
        "workflow_type": body.workflow_type,
        "frequency": body.frequency.value,
        "cron_expression": body.cron_expression,
        "enabled": body.enabled,
        "last_run_at": None,
        "next_run_at": None,
        "created_at": now,
        "created_by": user.id,
        "run_count": 0,
        "last_status": None,
    }

    _tasks[task_id] = task

    logger.info(
        "scheduled_task_created",
        task_id=task_id,
        name=body.name,
        workflow_type=body.workflow_type,
        frequency=body.frequency.value,
        user_id=user.id,
    )

    return _task_to_dict(task)


@router.get("")
async def list_scheduled_tasks(
    enabled: bool | None = Query(default=None, description="Filter by enabled status"),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all scheduled tasks with optional enabled filter."""
    tasks = list(_tasks.values())

    if enabled is not None:
        tasks = [t for t in tasks if t["enabled"] is enabled]

    items = [_task_to_dict(t) for t in tasks]

    return {
        "items": items,
        "total": len(items),
    }


@router.get("/{task_id}")
async def get_scheduled_task(
    task_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a single scheduled task by ID."""
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled task not found",
        )

    return _task_to_dict(task)


@router.put("/{task_id}")
async def update_scheduled_task(
    task_id: str,
    body: UpdateScheduledTaskBody,
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Update a scheduled task."""
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled task not found",
        )

    update_fields: dict[str, Any] = {}
    if body.name is not None:
        update_fields["name"] = body.name
    if body.prompt is not None:
        update_fields["prompt"] = body.prompt
    if body.frequency is not None:
        update_fields["frequency"] = body.frequency.value
    if body.cron_expression is not None:
        update_fields["cron_expression"] = body.cron_expression
    if body.enabled is not None:
        update_fields["enabled"] = body.enabled

    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    # Validate cron requirement
    new_freq = update_fields.get("frequency", task["frequency"])
    new_cron = update_fields.get("cron_expression", task.get("cron_expression"))
    if new_freq == ScheduleFrequency.CRON and not new_cron:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cron_expression is required when frequency is 'cron'",
        )

    task.update(update_fields)

    logger.info(
        "scheduled_task_updated",
        task_id=task_id,
        updated_fields=list(update_fields.keys()),
        user_id=user.id,
    )

    return _task_to_dict(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_scheduled_task(
    task_id: str,
    user: UserResponse = Depends(get_current_user),
) -> None:
    """Delete a scheduled task."""
    if task_id not in _tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled task not found",
        )

    del _tasks[task_id]

    logger.info(
        "scheduled_task_deleted",
        task_id=task_id,
        user_id=user.id,
    )


@router.post("/{task_id}/trigger")
async def trigger_scheduled_task(
    task_id: str,
    user: UserResponse = Depends(get_current_user),
) -> TriggerResult:
    """Manually trigger a scheduled task to run now."""
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled task not found",
        )

    now = datetime.now(UTC)
    task["last_run_at"] = now
    task["run_count"] = task.get("run_count", 0) + 1
    task["last_status"] = "triggered"

    logger.info(
        "scheduled_task_triggered",
        task_id=task_id,
        run_count=task["run_count"],
        user_id=user.id,
    )

    return TriggerResult(
        task_id=task_id,
        triggered_at=now,
        status="triggered",
    )
