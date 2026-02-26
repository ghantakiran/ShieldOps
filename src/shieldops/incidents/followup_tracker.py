"""Post-Incident Follow-up Tracker — track and manage post-incident follow-up items."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FollowupType(StrEnum):
    ACTION_ITEM = "action_item"
    PROCESS_CHANGE = "process_change"
    TOOLING_IMPROVEMENT = "tooling_improvement"
    TRAINING = "training"
    DOCUMENTATION = "documentation"


class FollowupStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class FollowupPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


# --- Models ---


class FollowupRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    followup_type: FollowupType = FollowupType.ACTION_ITEM
    status: FollowupStatus = FollowupStatus.OPEN
    priority: FollowupPriority = FollowupPriority.MEDIUM
    age_days: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class FollowupAssignment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assignee_name: str = ""
    followup_type: FollowupType = FollowupType.ACTION_ITEM
    status: FollowupStatus = FollowupStatus.OPEN
    due_days: float = 30.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FollowupTrackerReport(BaseModel):
    total_followups: int = 0
    total_assignments: int = 0
    completion_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    overdue_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PostIncidentFollowupTracker:
    """Track post-incident follow-up items, assignments, and completion rates."""

    def __init__(
        self,
        max_records: int = 200000,
        overdue_days: float = 30,
    ) -> None:
        self._max_records = max_records
        self._overdue_days = overdue_days
        self._records: list[FollowupRecord] = []
        self._assignments: list[FollowupAssignment] = []
        logger.info(
            "followup_tracker.initialized",
            max_records=max_records,
            overdue_days=overdue_days,
        )

    # -- record / get / list ---------------------------------------------

    def record_followup(
        self,
        service_name: str,
        followup_type: FollowupType = FollowupType.ACTION_ITEM,
        status: FollowupStatus = FollowupStatus.OPEN,
        priority: FollowupPriority = FollowupPriority.MEDIUM,
        age_days: float = 0.0,
        details: str = "",
    ) -> FollowupRecord:
        record = FollowupRecord(
            service_name=service_name,
            followup_type=followup_type,
            status=status,
            priority=priority,
            age_days=age_days,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "followup_tracker.recorded",
            record_id=record.id,
            service_name=service_name,
            followup_type=followup_type.value,
            status=status.value,
        )
        return record

    def get_followup(self, record_id: str) -> FollowupRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_followups(
        self,
        service_name: str | None = None,
        followup_type: FollowupType | None = None,
        limit: int = 50,
    ) -> list[FollowupRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if followup_type is not None:
            results = [r for r in results if r.followup_type == followup_type]
        return results[-limit:]

    def add_assignment(
        self,
        assignee_name: str,
        followup_type: FollowupType = FollowupType.ACTION_ITEM,
        status: FollowupStatus = FollowupStatus.OPEN,
        due_days: float = 30.0,
        description: str = "",
    ) -> FollowupAssignment:
        assignment = FollowupAssignment(
            assignee_name=assignee_name,
            followup_type=followup_type,
            status=status,
            due_days=due_days,
            description=description,
        )
        self._assignments.append(assignment)
        if len(self._assignments) > self._max_records:
            self._assignments = self._assignments[-self._max_records :]
        logger.info(
            "followup_tracker.assignment_added",
            assignee_name=assignee_name,
            followup_type=followup_type.value,
            status=status.value,
        )
        return assignment

    # -- domain operations -----------------------------------------------

    def analyze_followup_completion(self, service_name: str) -> dict[str, Any]:
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        completed = sum(1 for r in records if r.status == FollowupStatus.COMPLETED)
        completion_rate = round((completed / len(records)) * 100, 2)
        overdue = sum(
            1
            for r in records
            if r.status == FollowupStatus.OVERDUE or r.age_days > self._overdue_days
        )
        return {
            "service_name": service_name,
            "total_records": len(records),
            "completion_rate_pct": completion_rate,
            "overdue_count": overdue,
            "meets_target": completion_rate >= 80.0,
        }

    def identify_overdue_items(self) -> list[dict[str, Any]]:
        overdue_counts: dict[str, int] = {}
        for r in self._records:
            if r.status == FollowupStatus.OVERDUE or r.age_days > self._overdue_days:
                overdue_counts[r.service_name] = overdue_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in overdue_counts.items():
            if count > 1:
                results.append({"service_name": svc, "overdue_count": count})
        results.sort(key=lambda x: x["overdue_count"], reverse=True)
        return results

    def rank_by_age(self) -> list[dict[str, Any]]:
        svc_ages: dict[str, list[float]] = {}
        for r in self._records:
            svc_ages.setdefault(r.service_name, []).append(r.age_days)
        results: list[dict[str, Any]] = []
        for svc, ages in svc_ages.items():
            results.append(
                {
                    "service_name": svc,
                    "avg_age_days": round(sum(ages) / len(ages), 2),
                    "record_count": len(ages),
                }
            )
        results.sort(key=lambda x: x["avg_age_days"], reverse=True)
        return results

    def detect_followup_bottlenecks(self) -> list[dict[str, Any]]:
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "followup_count": count,
                        "bottleneck": True,
                    }
                )
        results.sort(key=lambda x: x["followup_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> FollowupTrackerReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.followup_type.value] = by_type.get(r.followup_type.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        completed = sum(1 for r in self._records if r.status == FollowupStatus.COMPLETED)
        completion_rate = round((completed / len(self._records)) * 100, 2) if self._records else 0.0
        overdue = sum(
            1
            for r in self._records
            if r.status == FollowupStatus.OVERDUE or r.age_days > self._overdue_days
        )
        recs: list[str] = []
        if completion_rate < 80.0:
            recs.append(f"Completion rate {completion_rate}% is below 80% target")
        bottlenecks = len(self.detect_followup_bottlenecks())
        if bottlenecks > 0:
            recs.append(f"{bottlenecks} service(s) with follow-up bottlenecks")
        if not recs:
            recs.append("Follow-up tracking meets targets")
        return FollowupTrackerReport(
            total_followups=len(self._records),
            total_assignments=len(self._assignments),
            completion_rate_pct=completion_rate,
            by_type=by_type,
            by_status=by_status,
            overdue_count=overdue,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assignments.clear()
        logger.info("followup_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.followup_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_followups": len(self._records),
            "total_assignments": len(self._assignments),
            "overdue_days": self._overdue_days,
            "type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
