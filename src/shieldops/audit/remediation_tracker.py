"""Audit Remediation Tracker — track audit remediations, identify overdue items."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RemediationPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class RemediationStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    WAIVED = "waived"


class RemediationType(StrEnum):
    POLICY_UPDATE = "policy_update"
    TECHNICAL_FIX = "technical_fix"
    PROCESS_CHANGE = "process_change"
    TRAINING = "training"
    DOCUMENTATION = "documentation"


# --- Models ---


class RemediationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_id: str = ""
    remediation_priority: RemediationPriority = RemediationPriority.MEDIUM
    remediation_status: RemediationStatus = RemediationStatus.NOT_STARTED
    remediation_type: RemediationType = RemediationType.TECHNICAL_FIX
    completion_pct: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RemediationMilestone(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    milestone_name: str = ""
    remediation_priority: RemediationPriority = RemediationPriority.MEDIUM
    progress_score: float = 0.0
    items_tracked: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditRemediationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_milestones: int = 0
    completed_remediations: int = 0
    avg_completion_pct: float = 0.0
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    overdue_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditRemediationTracker:
    """Track audit remediations, identify overdue items, measure progress."""

    def __init__(
        self,
        max_records: int = 200000,
        max_overdue_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_overdue_pct = max_overdue_pct
        self._records: list[RemediationRecord] = []
        self._milestones: list[RemediationMilestone] = []
        logger.info(
            "remediation_tracker.initialized",
            max_records=max_records,
            max_overdue_pct=max_overdue_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_remediation(
        self,
        finding_id: str,
        remediation_priority: RemediationPriority = RemediationPriority.MEDIUM,
        remediation_status: RemediationStatus = RemediationStatus.NOT_STARTED,
        remediation_type: RemediationType = RemediationType.TECHNICAL_FIX,
        completion_pct: float = 0.0,
        team: str = "",
    ) -> RemediationRecord:
        record = RemediationRecord(
            finding_id=finding_id,
            remediation_priority=remediation_priority,
            remediation_status=remediation_status,
            remediation_type=remediation_type,
            completion_pct=completion_pct,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "remediation_tracker.remediation_recorded",
            record_id=record.id,
            finding_id=finding_id,
            remediation_priority=remediation_priority.value,
            remediation_status=remediation_status.value,
        )
        return record

    def get_remediation(self, record_id: str) -> RemediationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_remediations(
        self,
        remediation_priority: RemediationPriority | None = None,
        remediation_status: RemediationStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RemediationRecord]:
        results = list(self._records)
        if remediation_priority is not None:
            results = [r for r in results if r.remediation_priority == remediation_priority]
        if remediation_status is not None:
            results = [r for r in results if r.remediation_status == remediation_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_milestone(
        self,
        milestone_name: str,
        remediation_priority: RemediationPriority = RemediationPriority.MEDIUM,
        progress_score: float = 0.0,
        items_tracked: int = 0,
        description: str = "",
    ) -> RemediationMilestone:
        milestone = RemediationMilestone(
            milestone_name=milestone_name,
            remediation_priority=remediation_priority,
            progress_score=progress_score,
            items_tracked=items_tracked,
            description=description,
        )
        self._milestones.append(milestone)
        if len(self._milestones) > self._max_records:
            self._milestones = self._milestones[-self._max_records :]
        logger.info(
            "remediation_tracker.milestone_added",
            milestone_name=milestone_name,
            remediation_priority=remediation_priority.value,
            progress_score=progress_score,
        )
        return milestone

    # -- domain operations --------------------------------------------------

    def analyze_remediation_progress(self) -> dict[str, Any]:
        """Group by remediation_priority; return count and avg completion_pct per priority."""
        priority_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.remediation_priority.value
            priority_data.setdefault(key, []).append(r.completion_pct)
        result: dict[str, Any] = {}
        for priority, pcts in priority_data.items():
            result[priority] = {
                "count": len(pcts),
                "avg_completion_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_overdue_remediations(self) -> list[dict[str, Any]]:
        """Return records where completion_pct < (100 - max_overdue_pct)."""
        threshold = 100.0 - self._max_overdue_pct
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.completion_pct < threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "finding_id": r.finding_id,
                        "completion_pct": r.completion_pct,
                        "remediation_priority": r.remediation_priority.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_priority(self) -> list[dict[str, Any]]:
        """Group by team, total completion_pct, sort descending."""
        team_scores: dict[str, float] = {}
        for r in self._records:
            team_scores[r.team] = team_scores.get(r.team, 0) + r.completion_pct
        results: list[dict[str, Any]] = []
        for team, total in team_scores.items():
            results.append(
                {
                    "team": team,
                    "total_completion": total,
                }
            )
        results.sort(key=lambda x: x["total_completion"], reverse=True)
        return results

    def detect_remediation_bottlenecks(self) -> dict[str, Any]:
        """Split-half on completion_pct; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        counts = [r.completion_pct for r in self._records]
        mid = len(counts) // 2
        first_half = counts[:mid]
        second_half = counts[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> AuditRemediationReport:
        by_priority: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for r in self._records:
            by_priority[r.remediation_priority.value] = (
                by_priority.get(r.remediation_priority.value, 0) + 1
            )
            by_status[r.remediation_status.value] = by_status.get(r.remediation_status.value, 0) + 1
            by_type[r.remediation_type.value] = by_type.get(r.remediation_type.value, 0) + 1
        threshold = 100.0 - self._max_overdue_pct
        overdue_count = sum(1 for r in self._records if r.completion_pct < threshold)
        completed_remediations = len({r.finding_id for r in self._records if r.completion_pct > 0})
        avg_comp = (
            round(sum(r.completion_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        overdue_ids = [r.finding_id for r in self._records if r.completion_pct < threshold][:5]
        recs: list[str] = []
        if overdue_count > 0:
            recs.append(f"{overdue_count} remediation(s) below completion threshold ({threshold}%)")
        if self._records and avg_comp < threshold:
            recs.append(f"Average completion {avg_comp}% is below threshold ({threshold}%)")
        if not recs:
            recs.append("Audit remediation progress levels are healthy")
        return AuditRemediationReport(
            total_records=len(self._records),
            total_milestones=len(self._milestones),
            completed_remediations=completed_remediations,
            avg_completion_pct=avg_comp,
            by_priority=by_priority,
            by_status=by_status,
            by_type=by_type,
            overdue_items=overdue_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._milestones.clear()
        logger.info("remediation_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        priority_dist: dict[str, int] = {}
        for r in self._records:
            key = r.remediation_priority.value
            priority_dist[key] = priority_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_milestones": len(self._milestones),
            "max_overdue_pct": self._max_overdue_pct,
            "priority_distribution": priority_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_findings": len({r.finding_id for r in self._records}),
        }
