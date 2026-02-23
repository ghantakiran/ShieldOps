"""Runbook scheduling for automated execution during maintenance windows.

Manages scheduled runbook executions with support for one-time and recurring
frequencies (daily, weekly, monthly, cron). Tracks execution history,
results, and provides lookahead queries for upcoming due runbooks.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class ScheduleStatus(enum.StrEnum):
    PENDING = "pending"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduleFrequency(enum.StrEnum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CRON = "cron"


# -- Models --------------------------------------------------------------------


class ScheduledRunbook(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    runbook_id: str
    name: str
    frequency: ScheduleFrequency = ScheduleFrequency.ONCE
    cron_expression: str = ""
    scheduled_at: float
    environment: str = "production"
    parameters: dict[str, Any] = Field(default_factory=dict)
    status: ScheduleStatus = ScheduleStatus.PENDING
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class ScheduleExecution(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    schedule_id: str
    started_at: float = Field(default_factory=time.time)
    completed_at: float | None = None
    status: ScheduleStatus = ScheduleStatus.EXECUTING
    output: str = ""
    error_message: str = ""


class ScheduleResult(BaseModel):
    schedule_id: str
    execution_id: str
    success: bool
    duration_seconds: float = 0.0
    message: str = ""


# -- Engine --------------------------------------------------------------------


class RunbookScheduler:
    """Schedule and track runbook executions.

    Parameters
    ----------
    max_schedules:
        Maximum schedules to store.
    lookahead_minutes:
        Minutes into the future to consider runbooks as due.
    """

    def __init__(
        self,
        max_schedules: int = 500,
        lookahead_minutes: int = 60,
    ) -> None:
        self._schedules: dict[str, ScheduledRunbook] = {}
        self._executions: list[ScheduleExecution] = []
        self._max_schedules = max_schedules
        self._lookahead_minutes = lookahead_minutes

    def schedule_runbook(
        self,
        runbook_id: str,
        name: str,
        scheduled_at: float,
        frequency: ScheduleFrequency = ScheduleFrequency.ONCE,
        cron_expression: str = "",
        environment: str = "production",
        parameters: dict[str, Any] | None = None,
        created_by: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ScheduledRunbook:
        if len(self._schedules) >= self._max_schedules:
            raise ValueError(f"Maximum schedules limit reached: {self._max_schedules}")
        now = time.time()
        if scheduled_at < now:
            logger.warning(
                "runbook_scheduled_in_past",
                runbook_id=runbook_id,
                scheduled_at=scheduled_at,
                now=now,
            )
        schedule = ScheduledRunbook(
            runbook_id=runbook_id,
            name=name,
            frequency=frequency,
            cron_expression=cron_expression,
            scheduled_at=scheduled_at,
            environment=environment,
            parameters=parameters or {},
            created_by=created_by,
            metadata=metadata or {},
        )
        self._schedules[schedule.id] = schedule
        logger.info(
            "runbook_scheduled",
            schedule_id=schedule.id,
            runbook_id=runbook_id,
            name=name,
            scheduled_at=scheduled_at,
        )
        return schedule

    def cancel_schedule(self, schedule_id: str) -> ScheduledRunbook | None:
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            return None
        schedule.status = ScheduleStatus.CANCELLED
        logger.info("runbook_schedule_cancelled", schedule_id=schedule_id)
        return schedule

    def get_schedule(self, schedule_id: str) -> ScheduledRunbook | None:
        return self._schedules.get(schedule_id)

    def list_schedules(
        self,
        status: ScheduleStatus | None = None,
    ) -> list[ScheduledRunbook]:
        schedules = list(self._schedules.values())
        if status:
            schedules = [s for s in schedules if s.status == status]
        return schedules

    def get_due_runbooks(self) -> list[ScheduledRunbook]:
        now = time.time()
        horizon = now + self._lookahead_minutes * 60
        due: list[ScheduledRunbook] = []
        for s in self._schedules.values():
            if s.status == ScheduleStatus.PENDING and s.scheduled_at <= horizon:
                due.append(s)
        return due

    def execute_scheduled(self, schedule_id: str) -> ScheduleExecution | None:
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            return None
        schedule.status = ScheduleStatus.EXECUTING
        execution = ScheduleExecution(schedule_id=schedule_id)
        self._executions.append(execution)
        logger.info(
            "runbook_execution_started",
            schedule_id=schedule_id,
            execution_id=execution.id,
        )
        return execution

    def record_result(
        self,
        execution_id: str,
        success: bool,
        output: str = "",
        error_message: str = "",
    ) -> ScheduleResult | None:
        execution = None
        for ex in self._executions:
            if ex.id == execution_id:
                execution = ex
                break
        if execution is None:
            return None

        now = time.time()
        execution.completed_at = now
        execution.output = output
        execution.error_message = error_message
        execution.status = ScheduleStatus.COMPLETED if success else ScheduleStatus.FAILED

        schedule = self._schedules.get(execution.schedule_id)
        if schedule is not None:
            schedule.status = ScheduleStatus.COMPLETED if success else ScheduleStatus.FAILED

        duration = now - execution.started_at
        result = ScheduleResult(
            schedule_id=execution.schedule_id,
            execution_id=execution_id,
            success=success,
            duration_seconds=round(duration, 3),
            message=output if success else error_message,
        )
        logger.info(
            "runbook_execution_completed",
            execution_id=execution_id,
            success=success,
            duration_seconds=result.duration_seconds,
        )
        return result

    def get_execution_history(
        self,
        schedule_id: str | None = None,
    ) -> list[ScheduleExecution]:
        if schedule_id:
            return [e for e in self._executions if e.schedule_id == schedule_id]
        return list(self._executions)

    def get_stats(self) -> dict[str, Any]:
        pending = sum(1 for s in self._schedules.values() if s.status == ScheduleStatus.PENDING)
        completed = sum(1 for s in self._schedules.values() if s.status == ScheduleStatus.COMPLETED)
        failed = sum(1 for s in self._schedules.values() if s.status == ScheduleStatus.FAILED)
        cancelled = sum(1 for s in self._schedules.values() if s.status == ScheduleStatus.CANCELLED)
        return {
            "total_schedules": len(self._schedules),
            "pending_schedules": pending,
            "completed_schedules": completed,
            "failed_schedules": failed,
            "cancelled_schedules": cancelled,
            "total_executions": len(self._executions),
            "lookahead_minutes": self._lookahead_minutes,
        }
