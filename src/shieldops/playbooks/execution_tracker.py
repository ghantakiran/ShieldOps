"""Runbook execution tracker.

Persistent execution history with step-level tracking for runbook/playbook
executions, enabling audit trails and performance analysis.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class ExecutionStatus(enum.StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class StepStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ── Models ───────────────────────────────────────────────────────────


class ExecutionStep(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    status: StepStatus = StepStatus.PENDING
    started_at: float | None = None
    completed_at: float | None = None
    duration_seconds: float = 0.0
    output: str = ""
    error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunbookExecution(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    runbook_id: str
    runbook_name: str = ""
    trigger: str = ""
    triggered_by: str = ""
    status: ExecutionStatus = ExecutionStatus.RUNNING
    steps: list[ExecutionStep] = Field(default_factory=list)
    started_at: float = Field(default_factory=time.time)
    completed_at: float | None = None
    duration_seconds: float = 0.0
    incident_id: str = ""
    environment: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Tracker ──────────────────────────────────────────────────────────


class RunbookExecutionTracker:
    """Track runbook execution history with step-level detail.

    Parameters
    ----------
    max_executions:
        Maximum executions to retain.
    execution_ttl_days:
        Days to retain completed executions.
    """

    def __init__(
        self,
        max_executions: int = 10000,
        execution_ttl_days: int = 90,
    ) -> None:
        self._executions: dict[str, RunbookExecution] = {}
        self._max_executions = max_executions
        self._ttl_seconds = execution_ttl_days * 86400

    def start_execution(
        self,
        runbook_id: str,
        runbook_name: str = "",
        trigger: str = "manual",
        triggered_by: str = "",
        steps: list[str] | None = None,
        incident_id: str = "",
        environment: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> RunbookExecution:
        if len(self._executions) >= self._max_executions:
            self._cleanup_oldest()
        step_models = [ExecutionStep(name=s) for s in (steps or [])]
        execution = RunbookExecution(
            runbook_id=runbook_id,
            runbook_name=runbook_name or runbook_id,
            trigger=trigger,
            triggered_by=triggered_by,
            steps=step_models,
            incident_id=incident_id,
            environment=environment,
            metadata=metadata or {},
        )
        self._executions[execution.id] = execution
        logger.info(
            "runbook_execution_started",
            execution_id=execution.id,
            runbook_id=runbook_id,
        )
        return execution

    def record_step(
        self,
        execution_id: str,
        step_name: str,
        status: StepStatus,
        output: str = "",
        error: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionStep | None:
        execution = self._executions.get(execution_id)
        if execution is None:
            return None
        # Find existing step or create new
        step = None
        for s in execution.steps:
            if s.name == step_name:
                step = s
                break
        if step is None:
            step = ExecutionStep(name=step_name)
            execution.steps.append(step)

        now = time.time()
        if status == StepStatus.RUNNING and step.started_at is None:
            step.started_at = now
        if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
            step.completed_at = now
            if step.started_at:
                step.duration_seconds = now - step.started_at
        step.status = status
        step.output = output or step.output
        step.error = error or step.error
        if metadata:
            step.metadata.update(metadata)
        return step

    def complete_execution(
        self,
        execution_id: str,
        status: ExecutionStatus = ExecutionStatus.COMPLETED,
    ) -> RunbookExecution | None:
        execution = self._executions.get(execution_id)
        if execution is None:
            return None
        now = time.time()
        execution.status = status
        execution.completed_at = now
        execution.duration_seconds = now - execution.started_at
        logger.info(
            "runbook_execution_completed",
            execution_id=execution_id,
            status=status,
            duration=execution.duration_seconds,
        )
        return execution

    def get_execution(self, execution_id: str) -> RunbookExecution | None:
        return self._executions.get(execution_id)

    def list_executions(
        self,
        runbook_id: str | None = None,
        status: ExecutionStatus | None = None,
        limit: int = 50,
    ) -> list[RunbookExecution]:
        execs = sorted(
            self._executions.values(),
            key=lambda e: e.started_at,
            reverse=True,
        )
        if runbook_id:
            execs = [e for e in execs if e.runbook_id == runbook_id]
        if status:
            execs = [e for e in execs if e.status == status]
        return execs[:limit]

    def _cleanup_oldest(self) -> None:
        if not self._executions:
            return
        sorted_execs = sorted(self._executions.values(), key=lambda e: e.started_at)
        to_remove = len(self._executions) - self._max_executions // 2
        for e in sorted_execs[:to_remove]:
            del self._executions[e.id]

    def get_stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        total_steps = 0
        avg_duration = 0.0
        completed_count = 0
        for e in self._executions.values():
            by_status[e.status.value] = by_status.get(e.status.value, 0) + 1
            total_steps += len(e.steps)
            if e.status == ExecutionStatus.COMPLETED and e.duration_seconds > 0:
                avg_duration += e.duration_seconds
                completed_count += 1
        return {
            "total_executions": len(self._executions),
            "by_status": by_status,
            "total_steps": total_steps,
            "avg_duration_seconds": avg_duration / completed_count if completed_count else 0.0,
        }
