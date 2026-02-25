"""Post-Incident Action Tracker — track follow-up actions to completion."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ActionStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class ActionPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


class ActionCategory(StrEnum):
    PREVENTION = "prevention"
    DETECTION = "detection"
    RESPONSE = "response"
    DOCUMENTATION = "documentation"
    PROCESS = "process"


# --- Models ---


class PostIncidentAction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    title: str = ""
    assignee: str = ""
    status: ActionStatus = ActionStatus.OPEN
    priority: ActionPriority = ActionPriority.MEDIUM
    category: ActionCategory = ActionCategory.PREVENTION
    due_days: int = 30
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ActionSummary(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    total_actions: int = 0
    completed: int = 0
    overdue: int = 0
    completion_rate_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ActionTrackerReport(BaseModel):
    total_actions: int = 0
    total_completed: int = 0
    total_overdue: int = 0
    completion_rate_pct: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PostIncidentActionTracker:
    """Track follow-up action items from incident retrospectives."""

    def __init__(
        self,
        max_records: int = 200000,
        overdue_threshold_days: int = 30,
    ) -> None:
        self._max_records = max_records
        self._overdue_threshold_days = overdue_threshold_days
        self._records: list[PostIncidentAction] = []
        self._summaries: list[ActionSummary] = []
        logger.info(
            "action_tracker.initialized",
            max_records=max_records,
            overdue_threshold_days=overdue_threshold_days,
        )

    # -- record / get / list ---------------------------------------------

    def record_action(
        self,
        incident_id: str,
        title: str,
        assignee: str = "",
        priority: ActionPriority = ActionPriority.MEDIUM,
        category: ActionCategory = ActionCategory.PREVENTION,
        due_days: int = 30,
        details: str = "",
    ) -> PostIncidentAction:
        record = PostIncidentAction(
            incident_id=incident_id,
            title=title,
            assignee=assignee,
            priority=priority,
            category=category,
            due_days=due_days,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "action_tracker.action_recorded",
            record_id=record.id,
            incident_id=incident_id,
            title=title,
            priority=priority.value,
        )
        return record

    def get_action(self, record_id: str) -> PostIncidentAction | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_actions(
        self,
        incident_id: str | None = None,
        status: ActionStatus | None = None,
        assignee: str | None = None,
        limit: int = 50,
    ) -> list[PostIncidentAction]:
        results = list(self._records)
        if incident_id is not None:
            results = [r for r in results if r.incident_id == incident_id]
        if status is not None:
            results = [r for r in results if r.status == status]
        if assignee is not None:
            results = [r for r in results if r.assignee == assignee]
        return results[-limit:]

    def complete_action(self, record_id: str) -> PostIncidentAction | None:
        for r in self._records:
            if r.id == record_id:
                r.status = ActionStatus.COMPLETED
                logger.info("action_tracker.action_completed", record_id=record_id)
                return r
        return None

    # -- domain operations -----------------------------------------------

    def identify_overdue_actions(self) -> list[dict[str, Any]]:
        """Find actions that have exceeded their due date."""
        now = time.time()
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.status in (ActionStatus.OPEN, ActionStatus.IN_PROGRESS):
                age_days = (now - r.created_at) / 86400
                if age_days > r.due_days:
                    r.status = ActionStatus.OVERDUE
                    results.append(
                        {
                            "action_id": r.id,
                            "incident_id": r.incident_id,
                            "title": r.title,
                            "assignee": r.assignee,
                            "priority": r.priority.value,
                            "age_days": round(age_days, 1),
                            "due_days": r.due_days,
                        }
                    )
        results.sort(key=lambda x: x["age_days"], reverse=True)
        return results

    def calculate_completion_rate(self) -> dict[str, Any]:
        """Calculate overall action completion rate."""
        if not self._records:
            return {"total": 0, "completed": 0, "completion_rate_pct": 0.0}
        completed = sum(1 for r in self._records if r.status == ActionStatus.COMPLETED)
        rate = round((completed / len(self._records)) * 100, 2)
        return {
            "total": len(self._records),
            "completed": completed,
            "completion_rate_pct": rate,
        }

    def summarize_incident_actions(self, incident_id: str) -> dict[str, Any]:
        """Summarize action status for a specific incident."""
        actions = [r for r in self._records if r.incident_id == incident_id]
        if not actions:
            return {"incident_id": incident_id, "total_actions": 0}
        completed = sum(1 for a in actions if a.status == ActionStatus.COMPLETED)
        overdue = sum(1 for a in actions if a.status == ActionStatus.OVERDUE)
        rate = round((completed / len(actions)) * 100, 2)
        return {
            "incident_id": incident_id,
            "total_actions": len(actions),
            "completed": completed,
            "overdue": overdue,
            "completion_rate_pct": rate,
        }

    def rank_assignees_by_completion(self) -> list[dict[str, Any]]:
        """Rank assignees by their action completion rate."""
        assignee_total: dict[str, int] = {}
        assignee_done: dict[str, int] = {}
        for r in self._records:
            if r.assignee:
                assignee_total[r.assignee] = assignee_total.get(r.assignee, 0) + 1
                if r.status == ActionStatus.COMPLETED:
                    assignee_done[r.assignee] = assignee_done.get(r.assignee, 0) + 1
        results: list[dict[str, Any]] = []
        for assignee, total in assignee_total.items():
            done = assignee_done.get(assignee, 0)
            rate = round((done / total) * 100, 2)
            results.append(
                {
                    "assignee": assignee,
                    "total": total,
                    "completed": done,
                    "completion_rate_pct": rate,
                }
            )
        results.sort(key=lambda x: x["completion_rate_pct"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ActionTrackerReport:
        by_status: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for r in self._records:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            by_priority[r.priority.value] = by_priority.get(r.priority.value, 0) + 1
        completed = sum(1 for r in self._records if r.status == ActionStatus.COMPLETED)
        overdue = sum(1 for r in self._records if r.status == ActionStatus.OVERDUE)
        rate = round((completed / len(self._records)) * 100, 2) if self._records else 0.0
        recs: list[str] = []
        if overdue > 0:
            recs.append(f"{overdue} action(s) are overdue")
        critical_open = sum(
            1
            for r in self._records
            if r.priority == ActionPriority.CRITICAL and r.status != ActionStatus.COMPLETED
        )
        if critical_open > 0:
            recs.append(f"{critical_open} critical action(s) still open")
        if not recs:
            recs.append("All post-incident actions on track")
        return ActionTrackerReport(
            total_actions=len(self._records),
            total_completed=completed,
            total_overdue=overdue,
            completion_rate_pct=rate,
            by_status=by_status,
            by_priority=by_priority,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._summaries.clear()
        logger.info("action_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_actions": len(self._records),
            "overdue_threshold_days": self._overdue_threshold_days,
            "status_distribution": status_dist,
            "unique_incidents": len({r.incident_id for r in self._records}),
            "unique_assignees": len({r.assignee for r in self._records if r.assignee}),
        }
