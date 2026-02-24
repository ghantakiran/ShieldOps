"""Runbook Execution Engine — automated runbook execution, step tracking, outcome recording."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RunbookStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    MANUAL_OVERRIDE = "manual_override"


class TriggerType(StrEnum):
    MANUAL = "manual"
    ALERT = "alert"
    SCHEDULE = "schedule"
    INCIDENT = "incident"
    API = "api"


# --- Models ---


class RunbookExecution(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_name: str = ""
    trigger: TriggerType = TriggerType.MANUAL
    status: RunbookStatus = RunbookStatus.PENDING
    initiated_by: str = ""
    steps: list[str] = Field(default_factory=list)
    current_step: int = 0
    context: dict[str, Any] = Field(default_factory=dict)
    started_at: float = Field(default_factory=time.time)
    completed_at: float | None = None


class ExecutionStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    step_number: int = 0
    name: str = ""
    outcome: StepOutcome = StepOutcome.SUCCESS
    duration_seconds: float = 0.0
    output: str = ""
    executed_at: float = Field(default_factory=time.time)


class ExecutionSummary(BaseModel):
    total_executions: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_trigger: dict[str, int] = Field(default_factory=dict)
    avg_duration_seconds: float = 0.0
    success_rate: float = 0.0


# --- Engine ---


class RunbookExecutionEngine:
    """Automated runbook execution, step tracking, outcome recording."""

    def __init__(
        self,
        max_executions: int = 100000,
        step_timeout: int = 300,
    ) -> None:
        self._max_executions = max_executions
        self._step_timeout = step_timeout
        self._executions: list[RunbookExecution] = []
        self._steps: list[ExecutionStep] = []
        logger.info(
            "runbook_engine.initialized",
            max_executions=max_executions,
            step_timeout=step_timeout,
        )

    def start_execution(
        self,
        runbook_name: str,
        trigger: TriggerType = TriggerType.MANUAL,
        initiated_by: str = "",
        context: dict[str, Any] | None = None,
    ) -> RunbookExecution:
        execution = RunbookExecution(
            runbook_name=runbook_name,
            trigger=trigger,
            status=RunbookStatus.RUNNING,
            initiated_by=initiated_by,
            context=context or {},
        )
        self._executions.append(execution)
        if len(self._executions) > self._max_executions:
            self._executions = self._executions[-self._max_executions :]
        logger.info(
            "runbook_engine.execution_started",
            execution_id=execution.id,
            runbook_name=runbook_name,
            trigger=trigger,
        )
        return execution

    def get_execution(self, execution_id: str) -> RunbookExecution | None:
        for e in self._executions:
            if e.id == execution_id:
                return e
        return None

    def list_executions(
        self,
        runbook_name: str | None = None,
        status: RunbookStatus | None = None,
        limit: int = 100,
    ) -> list[RunbookExecution]:
        results = list(self._executions)
        if runbook_name is not None:
            results = [e for e in results if e.runbook_name == runbook_name]
        if status is not None:
            results = [e for e in results if e.status == status]
        return results[-limit:]

    def record_step(
        self,
        execution_id: str,
        name: str = "",
        outcome: StepOutcome = StepOutcome.SUCCESS,
        duration_seconds: float = 0.0,
        output: str = "",
    ) -> ExecutionStep | None:
        execution = self.get_execution(execution_id)
        if execution is None:
            return None
        step = ExecutionStep(
            execution_id=execution_id,
            step_number=execution.current_step,
            name=name,
            outcome=outcome,
            duration_seconds=duration_seconds,
            output=output,
        )
        self._steps.append(step)
        execution.steps.append(step.id)
        execution.current_step += 1
        if outcome == StepOutcome.FAILURE:
            execution.status = RunbookStatus.FAILED
            execution.completed_at = time.time()
        logger.info(
            "runbook_engine.step_recorded",
            execution_id=execution_id,
            step_id=step.id,
            outcome=outcome,
        )
        return step

    def pause_execution(self, execution_id: str) -> bool:
        execution = self.get_execution(execution_id)
        if execution is None or execution.status != RunbookStatus.RUNNING:
            return False
        execution.status = RunbookStatus.PAUSED
        logger.info("runbook_engine.execution_paused", execution_id=execution_id)
        return True

    def resume_execution(self, execution_id: str) -> bool:
        execution = self.get_execution(execution_id)
        if execution is None or execution.status != RunbookStatus.PAUSED:
            return False
        execution.status = RunbookStatus.RUNNING
        logger.info("runbook_engine.execution_resumed", execution_id=execution_id)
        return True

    def cancel_execution(self, execution_id: str) -> bool:
        execution = self.get_execution(execution_id)
        if execution is None or execution.status in (
            RunbookStatus.COMPLETED,
            RunbookStatus.FAILED,
            RunbookStatus.CANCELLED,
        ):
            return False
        execution.status = RunbookStatus.CANCELLED
        execution.completed_at = time.time()
        logger.info("runbook_engine.execution_cancelled", execution_id=execution_id)
        return True

    def complete_execution(self, execution_id: str) -> bool:
        execution = self.get_execution(execution_id)
        if execution is None or execution.status not in (
            RunbookStatus.RUNNING,
            RunbookStatus.PAUSED,
        ):
            return False
        execution.status = RunbookStatus.COMPLETED
        execution.completed_at = time.time()
        logger.info("runbook_engine.execution_completed", execution_id=execution_id)
        return True

    def get_success_rate(self, runbook_name: str | None = None) -> dict[str, Any]:
        execs = self._executions
        if runbook_name:
            execs = [e for e in execs if e.runbook_name == runbook_name]
        finished = [e for e in execs if e.status in (RunbookStatus.COMPLETED, RunbookStatus.FAILED)]
        if not finished:
            return {"total": 0, "completed": 0, "failed": 0, "success_rate": 0.0}
        completed = sum(1 for e in finished if e.status == RunbookStatus.COMPLETED)
        failed = sum(1 for e in finished if e.status == RunbookStatus.FAILED)
        return {
            "total": len(finished),
            "completed": completed,
            "failed": failed,
            "success_rate": round(completed / len(finished) * 100, 1),
        }

    def get_stats(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        trigger_counts: dict[str, int] = {}
        for e in self._executions:
            status_counts[e.status] = status_counts.get(e.status, 0) + 1
            trigger_counts[e.trigger] = trigger_counts.get(e.trigger, 0) + 1
        return {
            "total_executions": len(self._executions),
            "total_steps": len(self._steps),
            "status_distribution": status_counts,
            "trigger_distribution": trigger_counts,
            "success_rate": self.get_success_rate()["success_rate"],
        }
