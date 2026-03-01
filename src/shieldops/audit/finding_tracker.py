"""Audit Finding Tracker — track audit findings, manage remediation plans."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FindingSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class FindingStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    REMEDIATED = "remediated"
    ACCEPTED_RISK = "accepted_risk"
    CLOSED = "closed"


class FindingCategory(StrEnum):
    ACCESS_CONTROL = "access_control"
    DATA_PROTECTION = "data_protection"
    CHANGE_MANAGEMENT = "change_management"
    INCIDENT_RESPONSE = "incident_response"
    MONITORING = "monitoring"


# --- Models ---


class FindingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_id: str = ""
    finding_severity: FindingSeverity = FindingSeverity.INFORMATIONAL
    finding_status: FindingStatus = FindingStatus.OPEN
    finding_category: FindingCategory = FindingCategory.ACCESS_CONTROL
    open_finding_pct: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RemediationPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_pattern: str = ""
    finding_severity: FindingSeverity = FindingSeverity.INFORMATIONAL
    days_to_remediate: int = 0
    resources_required: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditFindingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_remediations: int = 0
    overdue_findings: int = 0
    avg_open_finding_pct: float = 0.0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    critical: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditFindingTracker:
    """Track audit findings, manage remediation, monitor resolution trends."""

    def __init__(
        self,
        max_records: int = 200000,
        max_open_finding_pct: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._max_open_finding_pct = max_open_finding_pct
        self._records: list[FindingRecord] = []
        self._remediations: list[RemediationPlan] = []
        logger.info(
            "finding_tracker.initialized",
            max_records=max_records,
            max_open_finding_pct=max_open_finding_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_finding(
        self,
        finding_id: str,
        finding_severity: FindingSeverity = FindingSeverity.INFORMATIONAL,
        finding_status: FindingStatus = FindingStatus.OPEN,
        finding_category: FindingCategory = FindingCategory.ACCESS_CONTROL,
        open_finding_pct: float = 0.0,
        team: str = "",
    ) -> FindingRecord:
        record = FindingRecord(
            finding_id=finding_id,
            finding_severity=finding_severity,
            finding_status=finding_status,
            finding_category=finding_category,
            open_finding_pct=open_finding_pct,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "finding_tracker.finding_recorded",
            record_id=record.id,
            finding_id=finding_id,
            finding_severity=finding_severity.value,
            finding_status=finding_status.value,
        )
        return record

    def get_finding(self, record_id: str) -> FindingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_findings(
        self,
        finding_severity: FindingSeverity | None = None,
        finding_status: FindingStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FindingRecord]:
        results = list(self._records)
        if finding_severity is not None:
            results = [r for r in results if r.finding_severity == finding_severity]
        if finding_status is not None:
            results = [r for r in results if r.finding_status == finding_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_remediation(
        self,
        plan_pattern: str,
        finding_severity: FindingSeverity = FindingSeverity.INFORMATIONAL,
        days_to_remediate: int = 0,
        resources_required: int = 0,
        description: str = "",
    ) -> RemediationPlan:
        plan = RemediationPlan(
            plan_pattern=plan_pattern,
            finding_severity=finding_severity,
            days_to_remediate=days_to_remediate,
            resources_required=resources_required,
            description=description,
        )
        self._remediations.append(plan)
        if len(self._remediations) > self._max_records:
            self._remediations = self._remediations[-self._max_records :]
        logger.info(
            "finding_tracker.remediation_added",
            plan_pattern=plan_pattern,
            finding_severity=finding_severity.value,
            days_to_remediate=days_to_remediate,
        )
        return plan

    # -- domain operations --------------------------------------------------

    def analyze_finding_patterns(self) -> dict[str, Any]:
        """Group by finding_severity; return count and avg open_finding_pct per severity."""
        sev_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.finding_severity.value
            sev_data.setdefault(key, []).append(r.open_finding_pct)
        result: dict[str, Any] = {}
        for sev, pcts in sev_data.items():
            result[sev] = {
                "count": len(pcts),
                "avg_open_finding_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_overdue_findings(self) -> list[dict[str, Any]]:
        """Return records where open_finding_pct >= max_open_finding_pct."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.open_finding_pct >= self._max_open_finding_pct:
                results.append(
                    {
                        "record_id": r.id,
                        "finding_id": r.finding_id,
                        "open_finding_pct": r.open_finding_pct,
                        "finding_severity": r.finding_severity.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by team, total open_finding_pct, sort descending."""
        team_pcts: dict[str, float] = {}
        for r in self._records:
            team_pcts[r.team] = team_pcts.get(r.team, 0) + r.open_finding_pct
        results: list[dict[str, Any]] = []
        for team, total in team_pcts.items():
            results.append(
                {
                    "team": team,
                    "total_open_pct": total,
                }
            )
        results.sort(key=lambda x: x["total_open_pct"], reverse=True)
        return results

    def detect_finding_trends(self) -> dict[str, Any]:
        """Split-half on open_finding_pct; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        pcts = [r.open_finding_pct for r in self._records]
        mid = len(pcts) // 2
        first_half = pcts[:mid]
        second_half = pcts[mid:]
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

    def generate_report(self) -> AuditFindingReport:
        by_severity: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_severity[r.finding_severity.value] = by_severity.get(r.finding_severity.value, 0) + 1
            by_status[r.finding_status.value] = by_status.get(r.finding_status.value, 0) + 1
            by_category[r.finding_category.value] = by_category.get(r.finding_category.value, 0) + 1
        overdue_count = sum(
            1 for r in self._records if r.open_finding_pct >= self._max_open_finding_pct
        )
        avg_open = (
            round(sum(r.open_finding_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        critical_ids = [
            r.finding_id for r in self._records if r.open_finding_pct >= self._max_open_finding_pct
        ][:5]
        recs: list[str] = []
        if overdue_count > 0:
            recs.append(
                f"{overdue_count} finding(s) at or above open threshold"
                f" ({self._max_open_finding_pct}%)"
            )
        if self._records and avg_open >= self._max_open_finding_pct:
            recs.append(
                f"Average open finding pct {avg_open}% exceeds threshold"
                f" ({self._max_open_finding_pct}%)"
            )
        if not recs:
            recs.append("Audit finding levels are healthy")
        return AuditFindingReport(
            total_records=len(self._records),
            total_remediations=len(self._remediations),
            overdue_findings=overdue_count,
            avg_open_finding_pct=avg_open,
            by_severity=by_severity,
            by_status=by_status,
            by_category=by_category,
            critical=critical_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._remediations.clear()
        logger.info("finding_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        sev_dist: dict[str, int] = {}
        for r in self._records:
            key = r.finding_severity.value
            sev_dist[key] = sev_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_remediations": len(self._remediations),
            "max_open_finding_pct": self._max_open_finding_pct,
            "severity_distribution": sev_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_findings": len({r.finding_id for r in self._records}),
        }
