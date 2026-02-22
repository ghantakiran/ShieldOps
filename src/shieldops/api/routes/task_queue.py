"""Background task queue API endpoints.

Allows operators and admins to enqueue heavy operations (compliance audits,
bulk exports, git syncs, cost analyses, learning cycles), monitor their
progress, and retrieve results.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.workers.task_queue import TaskQueue

logger = structlog.get_logger()

router = APIRouter(prefix="/tasks", tags=["Task Queue"])

# ------------------------------------------------------------------
# Module-level singleton -- wired from app.py lifespan
# ------------------------------------------------------------------

_queue: TaskQueue | None = None


def set_task_queue(queue: TaskQueue) -> None:
    """Inject the TaskQueue instance (called from app.py)."""
    global _queue
    _queue = queue


def _get_queue() -> TaskQueue:
    if _queue is None:
        raise HTTPException(
            status_code=503,
            detail="Task queue not configured",
        )
    return _queue


# ------------------------------------------------------------------
# Request / response models
# ------------------------------------------------------------------


class EnqueueRequest(BaseModel):
    """Request body to enqueue a named task."""

    task_name: str
    params: dict[str, Any] = {}


class TaskStatusResponse(BaseModel):
    """Public view of a task's current state."""

    id: str
    name: str
    status: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: Any | None = None
    error: str | None = None
    retries: int = 0
    max_retries: int = 3


class TaskResultResponse(BaseModel):
    """Lightweight result view."""

    task_id: str
    status: str
    result: Any | None = None
    error: str | None = None
    duration_ms: float | None = None


class QueueStatsResponse(BaseModel):
    """Aggregate queue statistics."""

    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    total: int = 0


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/enqueue")
async def enqueue_task(
    body: EnqueueRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, str]:
    """Enqueue a named background task.

    Supported task names: ``compliance_audit``, ``bulk_export``,
    ``git_sync``, ``cost_analysis``, ``learning_cycle``.
    """
    from shieldops.workers.tasks import (
        run_bulk_export,
        run_compliance_audit,
        run_cost_analysis,
        run_git_sync,
        run_learning_cycle,
    )

    queue = _get_queue()

    # Map task name -> callable + kwargs
    task_map: dict[str, Any] = {
        "compliance_audit": run_compliance_audit,
        "bulk_export": run_bulk_export,
        "git_sync": run_git_sync,
        "cost_analysis": run_cost_analysis,
        "learning_cycle": run_learning_cycle,
    }

    func = task_map.get(body.task_name)
    if func is None:
        raise HTTPException(
            status_code=400,
            detail=(f"Unknown task: {body.task_name}. Supported: {sorted(task_map.keys())}"),
        )

    task_id = await queue.enqueue(body.task_name, func, **body.params)
    return {"task_id": task_id, "status": "pending"}


@router.get("")
async def list_tasks(
    status: str | None = Query(default=None, description="Filter by task status"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List tasks with optional status filter."""
    queue = _get_queue()
    tasks = await queue.list_tasks(status=status, limit=limit)
    return {
        "tasks": [
            TaskStatusResponse(
                id=t.id,
                name=t.name,
                status=t.status.value,
                created_at=t.created_at.isoformat(),
                started_at=t.started_at.isoformat() if t.started_at else None,
                completed_at=t.completed_at.isoformat() if t.completed_at else None,
                result=t.result,
                error=t.error,
                retries=t.retries,
                max_retries=t.max_retries,
            ).model_dump()
            for t in tasks
        ],
        "count": len(tasks),
    }


@router.get("/stats")
async def queue_stats(
    _user: UserResponse = Depends(get_current_user),
) -> QueueStatsResponse:
    """Return aggregate queue statistics."""
    queue = _get_queue()
    raw = queue.stats()
    return QueueStatsResponse(**raw)


@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> TaskStatusResponse:
    """Get the full status of a specific task."""
    queue = _get_queue()
    task_def = await queue.get_status(task_id)
    if task_def is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(
        id=task_def.id,
        name=task_def.name,
        status=task_def.status.value,
        created_at=task_def.created_at.isoformat(),
        started_at=task_def.started_at.isoformat() if task_def.started_at else None,
        completed_at=(task_def.completed_at.isoformat() if task_def.completed_at else None),
        result=task_def.result,
        error=task_def.error,
        retries=task_def.retries,
        max_retries=task_def.max_retries,
    )


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    """Cancel a pending task (admin only)."""
    queue = _get_queue()
    cancelled = await queue.cancel(task_id)
    if not cancelled:
        raise HTTPException(
            status_code=409,
            detail="Task cannot be cancelled (not pending or not found)",
        )
    return {"task_id": task_id, "status": "cancelled"}
