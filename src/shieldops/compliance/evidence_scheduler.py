"""Compliance Evidence Scheduler — schedule periodic
compliance evidence collection with deadline tracking."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CollectionFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ScheduleStatus(StrEnum):
    ON_TIME = "on_time"
    UPCOMING = "upcoming"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    MISSED = "missed"


class ComplianceFramework(StrEnum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"
    ISO_27001 = "iso_27001"


# --- Models ---


class EvidenceSchedule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_name: str = ""
    framework: ComplianceFramework = ComplianceFramework.SOC2
    frequency: CollectionFrequency = CollectionFrequency.MONTHLY
    status: ScheduleStatus = ScheduleStatus.ON_TIME
    next_due_at: float = 0.0
    last_collected_at: float = 0.0
    owner: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CollectionTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schedule_id: str = ""
    evidence_name: str = ""
    status: str = "pending"
    due_at: float = 0.0
    completed_at: float = 0.0
    collected_by: str = ""
    created_at: float = Field(default_factory=time.time)


class SchedulerReport(BaseModel):
    total_schedules: int = 0
    total_tasks: int = 0
    total_overdue: int = 0
    total_completed: int = 0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_frequency: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    overdue_schedules: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceEvidenceScheduler:
    """Schedule periodic compliance evidence collection with deadline tracking."""

    def __init__(
        self,
        max_schedules: int = 50000,
        overdue_grace_days: int = 7,
    ) -> None:
        self._max_schedules = max_schedules
        self._overdue_grace_days = overdue_grace_days
        self._schedules: list[EvidenceSchedule] = []
        self._tasks: list[CollectionTask] = []
        logger.info(
            "evidence_scheduler.initialized",
            max_schedules=max_schedules,
            overdue_grace_days=overdue_grace_days,
        )

    # -- schedule / get / list ---------------------------------------

    def create_schedule(
        self,
        evidence_name: str,
        framework: ComplianceFramework = ComplianceFramework.SOC2,
        frequency: CollectionFrequency = CollectionFrequency.MONTHLY,
        next_due_at: float = 0.0,
        owner: str = "",
        description: str = "",
        **kw: Any,
    ) -> EvidenceSchedule:
        schedule = EvidenceSchedule(
            evidence_name=evidence_name,
            framework=framework,
            frequency=frequency,
            next_due_at=next_due_at,
            owner=owner,
            description=description,
            **kw,
        )
        self._schedules.append(schedule)
        if len(self._schedules) > self._max_schedules:
            self._schedules = self._schedules[-self._max_schedules :]
        logger.info(
            "evidence_scheduler.schedule_created",
            schedule_id=schedule.id,
            evidence_name=evidence_name,
        )
        return schedule

    def get_schedule(self, schedule_id: str) -> EvidenceSchedule | None:
        for s in self._schedules:
            if s.id == schedule_id:
                return s
        return None

    def list_schedules(
        self,
        framework: ComplianceFramework | None = None,
        status: ScheduleStatus | None = None,
        limit: int = 50,
    ) -> list[EvidenceSchedule]:
        results = list(self._schedules)
        if framework is not None:
            results = [r for r in results if r.framework == framework]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results[-limit:]

    # -- due dates ---------------------------------------------------

    def compute_due_dates(self) -> list[dict[str, Any]]:
        """Compute and update due date status for all schedules."""
        now = time.time()
        results: list[dict[str, Any]] = []
        for s in self._schedules:
            if s.next_due_at <= 0:
                s.status = ScheduleStatus.ON_TIME
            else:
                days_until = (s.next_due_at - now) / 86400
                if days_until < -self._overdue_grace_days:
                    s.status = ScheduleStatus.MISSED
                elif days_until < 0:
                    s.status = ScheduleStatus.OVERDUE
                elif days_until <= 7:
                    s.status = ScheduleStatus.DUE_SOON
                elif days_until <= 30:
                    s.status = ScheduleStatus.UPCOMING
                else:
                    s.status = ScheduleStatus.ON_TIME
            results.append(
                {
                    "schedule_id": s.id,
                    "evidence_name": s.evidence_name,
                    "status": s.status.value,
                    "next_due_at": s.next_due_at,
                }
            )
        return results

    # -- collection tasks --------------------------------------------

    def create_collection_task(
        self,
        schedule_id: str,
        due_at: float = 0.0,
        **kw: Any,
    ) -> CollectionTask | None:
        schedule = self.get_schedule(schedule_id)
        if schedule is None:
            return None
        task = CollectionTask(
            schedule_id=schedule_id,
            evidence_name=schedule.evidence_name,
            due_at=due_at or schedule.next_due_at,
            **kw,
        )
        self._tasks.append(task)
        logger.info(
            "evidence_scheduler.task_created",
            task_id=task.id,
            schedule_id=schedule_id,
        )
        return task

    def complete_task(
        self,
        task_id: str,
        collected_by: str = "",
    ) -> bool:
        for t in self._tasks:
            if t.id == task_id:
                t.status = "completed"
                t.completed_at = time.time()
                t.collected_by = collected_by
                logger.info(
                    "evidence_scheduler.task_completed",
                    task_id=task_id,
                )
                return True
        return False

    def list_tasks(
        self,
        schedule_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[CollectionTask]:
        results = list(self._tasks)
        if schedule_id is not None:
            results = [r for r in results if r.schedule_id == schedule_id]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def find_overdue_schedules(self) -> list[EvidenceSchedule]:
        """Find schedules that are overdue or missed."""
        self.compute_due_dates()
        return [
            s
            for s in self._schedules
            if s.status in (ScheduleStatus.OVERDUE, ScheduleStatus.MISSED)
        ]

    # -- report / stats ----------------------------------------------

    def generate_scheduler_report(self) -> SchedulerReport:
        self.compute_due_dates()
        by_framework: dict[str, int] = {}
        for s in self._schedules:
            key = s.framework.value
            by_framework[key] = by_framework.get(key, 0) + 1
        by_frequency: dict[str, int] = {}
        for s in self._schedules:
            key = s.frequency.value
            by_frequency[key] = by_frequency.get(key, 0) + 1
        by_status: dict[str, int] = {}
        for s in self._schedules:
            key = s.status.value
            by_status[key] = by_status.get(key, 0) + 1
        overdue = [
            s.evidence_name
            for s in self._schedules
            if s.status in (ScheduleStatus.OVERDUE, ScheduleStatus.MISSED)
        ]
        completed_tasks = sum(1 for t in self._tasks if t.status == "completed")
        recs: list[str] = []
        if overdue:
            recs.append(f"{len(overdue)} overdue evidence collection(s)")
        if not recs:
            recs.append("All evidence collections on schedule")
        return SchedulerReport(
            total_schedules=len(self._schedules),
            total_tasks=len(self._tasks),
            total_overdue=len(overdue),
            total_completed=completed_tasks,
            by_framework=by_framework,
            by_frequency=by_frequency,
            by_status=by_status,
            overdue_schedules=overdue[:10],
            recommendations=recs,
        )

    def clear_data(self) -> int:
        count = len(self._schedules)
        self._schedules.clear()
        self._tasks.clear()
        logger.info("evidence_scheduler.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        fw_dist: dict[str, int] = {}
        for s in self._schedules:
            key = s.framework.value
            fw_dist[key] = fw_dist.get(key, 0) + 1
        return {
            "total_schedules": len(self._schedules),
            "total_tasks": len(self._tasks),
            "overdue_grace_days": self._overdue_grace_days,
            "framework_distribution": fw_dist,
        }
