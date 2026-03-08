"""Agent Tasks API routes — backend for the Agent Factory UI.

Provides endpoints for submitting, listing, inspecting, approving, and
cancelling agent task runs that are executed via the WorkflowEngine or
SupervisorAgent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse
from shieldops.orchestration.models import (
    WorkflowRun,
    WorkflowStatus,
    WorkflowStep,
)
from shieldops.orchestration.workflow_engine import WorkflowEngine

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/agent-tasks", tags=["agent-tasks"])

# ---------------------------------------------------------------------------
# In-memory task store (until full DB integration)
# ---------------------------------------------------------------------------

_task_runs: dict[str, WorkflowRun] = {}

# Module-level engine reference — configured at app startup via set_engine()
_engine: WorkflowEngine | None = None


def set_engine(engine: WorkflowEngine) -> None:
    """Configure the workflow engine used by these routes."""
    global _engine  # noqa: PLW0603
    _engine = engine


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateTaskRequest(BaseModel):
    """Request body for submitting a new agent task."""

    prompt: str = Field(..., min_length=1, description="Natural-language task description")
    persona: str | None = Field(
        default=None,
        description="Optional agent persona / type to handle the task",
    )
    workflow_type: str | None = Field(
        default=None,
        description="Named workflow to execute (e.g. incident_response, security_scan)",
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Additional context passed to the workflow as parameters",
    )


class CreateTaskResponse(BaseModel):
    """Response returned after a task is successfully submitted."""

    task_id: str
    status: str


class StepApprovalRequest(BaseModel):
    """Request body for approving or rejecting a gated workflow step."""

    approved: bool
    comment: str | None = Field(
        default=None,
        description="Optional reviewer comment for audit trail",
    )


class TaskSummary(BaseModel):
    """Lightweight summary of a task run for list views."""

    task_id: str
    workflow_name: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    step_count: int


class StepDetail(BaseModel):
    """Detailed view of a single workflow step."""

    step_id: str
    agent_type: str
    action: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class TaskDetail(BaseModel):
    """Full detail view of a task run including all steps."""

    task_id: str
    workflow_name: str
    trigger: str
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None
    initiated_by: str
    steps: list[StepDetail]


# ---------------------------------------------------------------------------
# Helper converters
# ---------------------------------------------------------------------------


def _run_to_summary(run: WorkflowRun) -> TaskSummary:
    """Convert a WorkflowRun to a lightweight TaskSummary."""
    return TaskSummary(
        task_id=run.run_id,
        workflow_name=run.workflow_name,
        status=run.status.value,
        created_at=run.created_at,
        completed_at=run.completed_at,
        step_count=len(run.steps),
    )


def _run_to_detail(run: WorkflowRun) -> TaskDetail:
    """Convert a WorkflowRun to a full TaskDetail with step information."""
    return TaskDetail(
        task_id=run.run_id,
        workflow_name=run.workflow_name,
        trigger=run.trigger,
        status=run.status.value,
        metadata=run.metadata,
        created_at=run.created_at,
        completed_at=run.completed_at,
        initiated_by=run.initiated_by,
        steps=[
            StepDetail(
                step_id=step.step_id,
                agent_type=step.agent_type.value,
                action=step.action,
                status=step.status.value,
                started_at=step.started_at,
                completed_at=step.completed_at,
                result=step.result,
                error=step.error,
            )
            for step in run.steps
        ],
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", response_model=CreateTaskResponse)
async def create_task(
    body: CreateTaskRequest,
    user: UserResponse = Depends(get_current_user),
) -> CreateTaskResponse:
    """Submit a new agent task for execution.

    Creates a workflow run using the configured WorkflowEngine. The
    ``workflow_type`` selects a built-in or custom workflow; when omitted
    the default ``incident_response`` workflow is used.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Workflow engine not configured")

    workflow_name = body.workflow_type or "incident_response"
    params: dict[str, Any] = {
        "prompt": body.prompt,
        **({"persona": body.persona} if body.persona else {}),
        **(body.context or {}),
    }

    logger.info(
        "agent_task_submitted",
        workflow=workflow_name,
        persona=body.persona,
        user=user.email,
    )

    try:
        run = await _engine.execute_workflow(
            workflow_name=workflow_name,
            trigger="manual",
            params=params,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    run.initiated_by = user.email
    _task_runs[run.run_id] = run

    logger.info(
        "agent_task_created",
        task_id=run.run_id,
        status=run.status.value,
    )

    return CreateTaskResponse(task_id=run.run_id, status=run.status.value)


@router.get("", response_model=list[TaskSummary])
async def list_tasks(
    status: str | None = Query(default=None, description="Filter by workflow status"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results to return"),
    _user: UserResponse = Depends(get_current_user),
) -> list[TaskSummary]:
    """List recent task runs with optional status filter.

    Returns lightweight summaries sorted by creation time (newest first).
    """
    runs = sorted(_task_runs.values(), key=lambda r: r.created_at, reverse=True)

    if status is not None:
        try:
            target_status = WorkflowStatus(status)
        except ValueError as exc:
            valid = [s.value for s in WorkflowStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Must be one of: {valid}",
            ) from exc
        runs = [r for r in runs if r.status == target_status]

    return [_run_to_summary(r) for r in runs[:limit]]


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> TaskDetail:
    """Get full task details including all step statuses, results, and errors."""
    run = _task_runs.get(task_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return _run_to_detail(run)


@router.post("/{task_id}/steps/{step_id}/approve")
async def approve_step(
    task_id: str,
    step_id: str,
    body: StepApprovalRequest,
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Approve or reject a gated workflow step.

    When approved the step status moves to RUNNING so the engine can
    continue execution.  When rejected the step is marked FAILED and
    the overall task is CANCELLED.
    """
    run = _task_runs.get(task_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    target_step: WorkflowStep | None = None
    for step in run.steps:
        if step.step_id == step_id:
            target_step = step
            break

    if target_step is None:
        raise HTTPException(
            status_code=404,
            detail=f"Step '{step_id}' not found in task '{task_id}'",
        )

    if target_step.status != WorkflowStatus.PAUSED:
        raise HTTPException(
            status_code=409,
            detail=f"Step is not awaiting approval (current status: {target_step.status.value})",
        )

    now = datetime.now(UTC)

    if body.approved:
        target_step.status = WorkflowStatus.RUNNING
        target_step.started_at = target_step.started_at or now
        logger.info(
            "agent_task_step_approved",
            task_id=task_id,
            step_id=step_id,
            approved_by=user.email,
            comment=body.comment,
        )
    else:
        target_step.status = WorkflowStatus.FAILED
        target_step.error = body.comment or "Rejected by reviewer"
        target_step.completed_at = now
        run.status = WorkflowStatus.CANCELLED
        run.completed_at = now
        logger.info(
            "agent_task_step_rejected",
            task_id=task_id,
            step_id=step_id,
            rejected_by=user.email,
            comment=body.comment,
        )

    return {
        "task_id": task_id,
        "step_id": step_id,
        "approved": body.approved,
        "step_status": target_step.status.value,
        "task_status": run.status.value,
    }


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Cancel a running task.

    Only tasks in PENDING or RUNNING status can be cancelled.
    """
    run = _task_runs.get(task_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    if run.status not in (WorkflowStatus.PENDING, WorkflowStatus.RUNNING, WorkflowStatus.PAUSED):
        raise HTTPException(
            status_code=409,
            detail=f"Task cannot be cancelled (current status: {run.status.value})",
        )

    now = datetime.now(UTC)
    run.status = WorkflowStatus.CANCELLED
    run.completed_at = now

    # Mark any pending/running steps as cancelled
    for step in run.steps:
        if step.status in (WorkflowStatus.PENDING, WorkflowStatus.RUNNING, WorkflowStatus.PAUSED):
            step.status = WorkflowStatus.CANCELLED
            step.completed_at = now

    logger.info(
        "agent_task_cancelled",
        task_id=task_id,
        cancelled_by=user.email,
    )

    return {
        "task_id": task_id,
        "status": run.status.value,
        "cancelled": True,
    }
