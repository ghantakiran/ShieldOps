"""Audit Remediation Tracker — track audit finding remediation, detect overdue items."""

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


class RemediationState(StrEnum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"


class FindingSource(StrEnum):
    INTERNAL_AUDIT = "internal_audit"
    EXTERNAL_AUDIT = "external_audit"
    PENETRATION_TEST = "penetration_test"
    COMPLIANCE_SCAN = "compliance_scan"
    SELF_ASSESSMENT = "self_assessment"


# --- Models ---


class RemediationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_id: str = ""
    remediation_priority: RemediationPriority = RemediationPriority.MEDIUM
    remediation_state: RemediationState = RemediationState.OPEN
    finding_source: FindingSource = FindingSource.INTERNAL_AUDIT
    remediation_days: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RemediationAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_id: str = ""
    remediation_priority: RemediationPriority = RemediationPriority.MEDIUM
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditRemediationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    overdue_count: int = 0
    avg_remediation_days: float = 0.0
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_state: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    top_overdue: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditRemediationTracker:
    """Track audit finding remediation, detect overdue items, measure remediation velocity."""

    def __init__(
        self,
        max_records: int = 200000,
        max_remediation_days: float = 45.0,
    ) -> None:
        self._max_records = max_records
        self._max_remediation_days = max_remediation_days
        self._records: list[RemediationRecord] = []
        self._assessments: list[RemediationAssessment] = []
        logger.info(
            "audit_remediation_tracker.initialized",
            max_records=max_records,
            max_remediation_days=max_remediation_days,
        )

    # -- record / get / list ------------------------------------------------

    def record_remediation(
        self,
        finding_id: str,
        remediation_priority: RemediationPriority = RemediationPriority.MEDIUM,
        remediation_state: RemediationState = RemediationState.OPEN,
        finding_source: FindingSource = FindingSource.INTERNAL_AUDIT,
        remediation_days: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RemediationRecord:
        record = RemediationRecord(
            finding_id=finding_id,
            remediation_priority=remediation_priority,
            remediation_state=remediation_state,
            finding_source=finding_source,
            remediation_days=remediation_days,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "audit_remediation_tracker.remediation_recorded",
            record_id=record.id,
            finding_id=finding_id,
            remediation_priority=remediation_priority.value,
            remediation_state=remediation_state.value,
        )
        return record

    def get_remediation(self, record_id: str) -> RemediationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_remediations(
        self,
        priority: RemediationPriority | None = None,
        state: RemediationState | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RemediationRecord]:
        results = list(self._records)
        if priority is not None:
            results = [r for r in results if r.remediation_priority == priority]
        if state is not None:
            results = [r for r in results if r.remediation_state == state]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        finding_id: str,
        remediation_priority: RemediationPriority = RemediationPriority.MEDIUM,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RemediationAssessment:
        assessment = RemediationAssessment(
            finding_id=finding_id,
            remediation_priority=remediation_priority,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "audit_remediation_tracker.assessment_added",
            finding_id=finding_id,
            remediation_priority=remediation_priority.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_remediation_distribution(self) -> dict[str, Any]:
        """Group by remediation_priority; return count and avg remediation_days."""
        priority_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.remediation_priority.value
            priority_data.setdefault(key, []).append(r.remediation_days)
        result: dict[str, Any] = {}
        for priority, days in priority_data.items():
            result[priority] = {
                "count": len(days),
                "avg_remediation_days": round(sum(days) / len(days), 2),
            }
        return result

    def identify_overdue_remediations(self) -> list[dict[str, Any]]:
        """Return records where remediation_days > max_remediation_days."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.remediation_days > self._max_remediation_days:
                results.append(
                    {
                        "record_id": r.id,
                        "finding_id": r.finding_id,
                        "remediation_priority": r.remediation_priority.value,
                        "remediation_days": r.remediation_days,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_remediation_time(self) -> list[dict[str, Any]]:
        """Group by service, avg remediation_days, sort descending."""
        svc_days: dict[str, list[float]] = {}
        for r in self._records:
            svc_days.setdefault(r.service, []).append(r.remediation_days)
        results: list[dict[str, Any]] = []
        for svc, days in svc_days.items():
            results.append(
                {
                    "service": svc,
                    "avg_remediation_days": round(sum(days) / len(days), 2),
                }
            )
        results.sort(key=lambda x: x["avg_remediation_days"], reverse=True)
        return results

    def detect_remediation_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.assessment_score for a in self._assessments]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> AuditRemediationReport:
        by_priority: dict[str, int] = {}
        by_state: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in self._records:
            by_priority[r.remediation_priority.value] = (
                by_priority.get(r.remediation_priority.value, 0) + 1
            )
            by_state[r.remediation_state.value] = by_state.get(r.remediation_state.value, 0) + 1
            by_source[r.finding_source.value] = by_source.get(r.finding_source.value, 0) + 1
        overdue_count = sum(
            1 for r in self._records if r.remediation_days > self._max_remediation_days
        )
        days = [r.remediation_days for r in self._records]
        avg_remediation_days = round(sum(days) / len(days), 2) if days else 0.0
        overdue_list = self.identify_overdue_remediations()
        top_overdue = [o["finding_id"] for o in overdue_list[:5]]
        recs: list[str] = []
        if overdue_count > 0:
            recs.append(f"{overdue_count} overdue remediation(s) — escalate immediately")
        if self._records and avg_remediation_days > self._max_remediation_days:
            recs.append(
                f"Avg remediation days {avg_remediation_days} exceeds threshold "
                f"({self._max_remediation_days})"
            )
        if not recs:
            recs.append("Audit remediation levels are healthy")
        return AuditRemediationReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            overdue_count=overdue_count,
            avg_remediation_days=avg_remediation_days,
            by_priority=by_priority,
            by_state=by_state,
            by_source=by_source,
            top_overdue=top_overdue,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("audit_remediation_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        priority_dist: dict[str, int] = {}
        for r in self._records:
            key = r.remediation_priority.value
            priority_dist[key] = priority_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "max_remediation_days": self._max_remediation_days,
            "priority_distribution": priority_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
