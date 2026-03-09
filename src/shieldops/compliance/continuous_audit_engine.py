"""Continuous Audit Engine
audit automation, control testing, finding management, remediation tracking."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AuditControlStatus(StrEnum):
    PASSING = "passing"
    FAILING = "failing"
    NOT_TESTED = "not_tested"
    PARTIALLY_PASSING = "partially_passing"
    EXEMPT = "exempt"


class FindingSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class RemediationState(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    REMEDIATED = "remediated"
    ACCEPTED_RISK = "accepted_risk"
    OVERDUE = "overdue"


# --- Models ---


class AuditRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    control_status: AuditControlStatus = AuditControlStatus.NOT_TESTED
    finding_severity: FindingSeverity = FindingSeverity.MEDIUM
    remediation_state: RemediationState = RemediationState.OPEN
    test_score: float = 0.0
    days_since_last_test: int = 0
    finding_count: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    control_status: AuditControlStatus = AuditControlStatus.NOT_TESTED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContinuousAuditReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_test_score: float = 0.0
    pass_rate: float = 0.0
    open_findings: int = 0
    overdue_remediations: int = 0
    by_control_status: dict[str, int] = Field(default_factory=dict)
    by_finding_severity: dict[str, int] = Field(default_factory=dict)
    by_remediation_state: dict[str, int] = Field(default_factory=dict)
    failing_controls: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ContinuousAuditEngine:
    """Continuous audit automation, control testing, finding management, remediation tracking."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[AuditRecord] = []
        self._analyses: list[AuditAnalysis] = []
        logger.info(
            "continuous_audit_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def add_record(
        self,
        control_id: str,
        control_status: AuditControlStatus = AuditControlStatus.NOT_TESTED,
        finding_severity: FindingSeverity = FindingSeverity.MEDIUM,
        remediation_state: RemediationState = RemediationState.OPEN,
        test_score: float = 0.0,
        days_since_last_test: int = 0,
        finding_count: int = 0,
        service: str = "",
        team: str = "",
    ) -> AuditRecord:
        record = AuditRecord(
            control_id=control_id,
            control_status=control_status,
            finding_severity=finding_severity,
            remediation_state=remediation_state,
            test_score=test_score,
            days_since_last_test=days_since_last_test,
            finding_count=finding_count,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "continuous_audit_engine.record_added",
            record_id=record.id,
            control_id=control_id,
            control_status=control_status.value,
        )
        return record

    def get_record(self, record_id: str) -> AuditRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        control_status: AuditControlStatus | None = None,
        finding_severity: FindingSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AuditRecord]:
        results = list(self._records)
        if control_status is not None:
            results = [r for r in results if r.control_status == control_status]
        if finding_severity is not None:
            results = [r for r in results if r.finding_severity == finding_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        control_id: str,
        control_status: AuditControlStatus = AuditControlStatus.NOT_TESTED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AuditAnalysis:
        analysis = AuditAnalysis(
            control_id=control_id,
            control_status=control_status,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "continuous_audit_engine.analysis_added",
            control_id=control_id,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def compute_pass_rate(self) -> dict[str, Any]:
        if not self._records:
            return {"pass_rate": 0.0, "total_controls": 0}
        passing = sum(1 for r in self._records if r.control_status == AuditControlStatus.PASSING)
        partial = sum(
            1 for r in self._records if r.control_status == AuditControlStatus.PARTIALLY_PASSING
        )
        failing = sum(1 for r in self._records if r.control_status == AuditControlStatus.FAILING)
        total = len(self._records)
        return {
            "pass_rate": round((passing + partial * 0.5) / total * 100, 2),
            "passing": passing,
            "partially_passing": partial,
            "failing": failing,
            "not_tested": total - passing - partial - failing,
            "total_controls": total,
        }

    def identify_stale_controls(self, max_days: int = 30) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.days_since_last_test > max_days:
                results.append(
                    {
                        "control_id": r.control_id,
                        "days_since_last_test": r.days_since_last_test,
                        "control_status": r.control_status.value,
                        "test_score": r.test_score,
                    }
                )
        return sorted(results, key=lambda x: x["days_since_last_test"], reverse=True)

    def track_remediation_progress(self) -> dict[str, Any]:
        state_counts: dict[str, int] = {}
        for r in self._records:
            key = r.remediation_state.value
            state_counts[key] = state_counts.get(key, 0) + 1
        total_findings = sum(r.finding_count for r in self._records)
        remediated = state_counts.get("remediated", 0)
        open_count = state_counts.get("open", 0) + state_counts.get("overdue", 0)
        total = len(self._records) or 1
        return {
            "remediation_states": state_counts,
            "total_findings": total_findings,
            "remediation_rate": round(remediated / total * 100, 2),
            "open_count": open_count,
        }

    def prioritize_findings(self) -> list[dict[str, Any]]:
        severity_weight = {
            FindingSeverity.CRITICAL: 5,
            FindingSeverity.HIGH: 4,
            FindingSeverity.MEDIUM: 3,
            FindingSeverity.LOW: 2,
            FindingSeverity.INFORMATIONAL: 1,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.control_status == AuditControlStatus.FAILING:
                weight = severity_weight.get(r.finding_severity, 1)
                age_factor = 1 + r.days_since_last_test * 0.01
                priority = round(weight * r.finding_count * age_factor, 2)
                results.append(
                    {
                        "control_id": r.control_id,
                        "priority_score": priority,
                        "finding_severity": r.finding_severity.value,
                        "finding_count": r.finding_count,
                        "remediation_state": r.remediation_state.value,
                    }
                )
        return sorted(results, key=lambda x: x["priority_score"], reverse=True)

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
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

    def process(self, control_id: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.control_id == control_id]
        if not matching:
            return {"control_id": control_id, "status": "no_data"}
        scores = [r.test_score for r in matching]
        findings = sum(r.finding_count for r in matching)
        return {
            "control_id": control_id,
            "test_count": len(matching),
            "avg_test_score": round(sum(scores) / len(scores), 2),
            "total_findings": findings,
            "latest_status": matching[-1].control_status.value,
        }

    def generate_report(self) -> ContinuousAuditReport:
        by_cs: dict[str, int] = {}
        by_fs: dict[str, int] = {}
        by_rs: dict[str, int] = {}
        for r in self._records:
            by_cs[r.control_status.value] = by_cs.get(r.control_status.value, 0) + 1
            by_fs[r.finding_severity.value] = by_fs.get(r.finding_severity.value, 0) + 1
            by_rs[r.remediation_state.value] = by_rs.get(r.remediation_state.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.test_score < self._threshold)
        scores = [r.test_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        pass_info = self.compute_pass_rate()
        open_findings = sum(
            r.finding_count
            for r in self._records
            if r.remediation_state in (RemediationState.OPEN, RemediationState.OVERDUE)
        )
        overdue = by_rs.get("overdue", 0)
        failing = [
            r.control_id for r in self._records if r.control_status == AuditControlStatus.FAILING
        ][:5]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(f"{gap_count} control(s) below test score threshold ({self._threshold})")
        if overdue > 0:
            recs.append(f"{overdue} overdue remediation(s) — escalate immediately")
        if open_findings > 0:
            recs.append(f"{open_findings} open finding(s) across controls")
        if pass_info["pass_rate"] < self._threshold:
            recs.append(f"Pass rate {pass_info['pass_rate']}% below target {self._threshold}%")
        if not recs:
            recs.append("Continuous audit posture is healthy")
        return ContinuousAuditReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_test_score=avg_score,
            pass_rate=pass_info["pass_rate"],
            open_findings=open_findings,
            overdue_remediations=overdue,
            by_control_status=by_cs,
            by_finding_severity=by_fs,
            by_remediation_state=by_rs,
            failing_controls=failing,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cs_dist: dict[str, int] = {}
        for r in self._records:
            key = r.control_status.value
            cs_dist[key] = cs_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "control_status_distribution": cs_dist,
            "unique_controls": len({r.control_id for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("continuous_audit_engine.cleared")
        return {"status": "cleared"}
