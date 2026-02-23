"""Runbook execution tracking API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role
from shieldops.playbooks.execution_tracker import ExecutionStatus, StepStatus

logger = structlog.get_logger()
router = APIRouter(prefix="/runbook-executions", tags=["Runbook Executions"])

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Runbook execution service unavailable")
    return _tracker


class StartExecutionRequest(BaseModel):
    runbook_id: str
    runbook_name: str = ""
    trigger: str = "manual"
    triggered_by: str = ""
    steps: list[str] = Field(default_factory=list)
    incident_id: str = ""
    environment: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordStepRequest(BaseModel):
    step_name: str
    status: StepStatus
    output: str = ""
    error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompleteExecutionRequest(BaseModel):
    status: ExecutionStatus = ExecutionStatus.COMPLETED


@router.post("")
async def start_execution(
    body: StartExecutionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    execution = tracker.start_execution(**body.model_dump())
    return execution.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()


@router.get("")
async def list_executions(
    runbook_id: str | None = None,
    status: ExecutionStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [
        e.model_dump()
        for e in tracker.list_executions(runbook_id=runbook_id, status=status, limit=limit)
    ]


@router.get("/{execution_id}")
async def get_execution(
    execution_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    execution = tracker.get_execution(execution_id)
    if execution is None:
        raise HTTPException(404, f"Execution '{execution_id}' not found")
    return execution.model_dump()


@router.put("/{execution_id}/steps")
async def record_step(
    execution_id: str,
    body: RecordStepRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    step = tracker.record_step(execution_id, **body.model_dump())
    if step is None:
        raise HTTPException(404, f"Execution '{execution_id}' not found")
    return step.model_dump()


@router.put("/{execution_id}/complete")
async def complete_execution(
    execution_id: str,
    body: CompleteExecutionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    execution = tracker.complete_execution(execution_id, body.status)
    if execution is None:
        raise HTTPException(404, f"Execution '{execution_id}' not found")
    return execution.model_dump()
