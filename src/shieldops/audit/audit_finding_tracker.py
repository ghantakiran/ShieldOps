"""Audit Finding Tracker — track audit findings, remediation progress, and compliance gaps."""

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
    MODERATE = "moderate"
    LOW = "low"
    INFORMATIONAL = "informational"


class FindingCategory(StrEnum):
    ACCESS_CONTROL = "access_control"
    DATA_PROTECTION = "data_protection"
    CONFIGURATION = "configuration"
    MONITORING = "monitoring"
    COMPLIANCE = "compliance"


class FindingStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    REMEDIATED = "remediated"
    ACCEPTED = "accepted"
    CLOSED = "closed"


# --- Models ---


class FindingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_id: str = ""
    finding_severity: FindingSeverity = FindingSeverity.INFORMATIONAL
    finding_category: FindingCategory = FindingCategory.COMPLIANCE
    finding_status: FindingStatus = FindingStatus.OPEN
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FindingRemediation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_id: str = ""
    finding_severity: FindingSeverity = FindingSeverity.INFORMATIONAL
    remediation_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditFindingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_remediations: int = 0
    open_findings: int = 0
    avg_risk_score: float = 0.0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_open: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditFindingTracker:
    """Track audit findings, remediation progress, and compliance gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        max_open_finding_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_open_finding_pct = max_open_finding_pct
        self._records: list[FindingRecord] = []
        self._remediations: list[FindingRemediation] = []
        logger.info(
            "audit_finding.initialized",
            max_records=max_records,
            max_open_finding_pct=max_open_finding_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_finding(
        self,
        finding_id: str,
        finding_severity: FindingSeverity = FindingSeverity.INFORMATIONAL,
        finding_category: FindingCategory = FindingCategory.COMPLIANCE,
        finding_status: FindingStatus = FindingStatus.OPEN,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> FindingRecord:
        record = FindingRecord(
            finding_id=finding_id,
            finding_severity=finding_severity,
            finding_category=finding_category,
            finding_status=finding_status,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "audit_finding.finding_recorded",
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
        severity: FindingSeverity | None = None,
        category: FindingCategory | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FindingRecord]:
        results = list(self._records)
        if severity is not None:
            results = [r for r in results if r.finding_severity == severity]
        if category is not None:
            results = [r for r in results if r.finding_category == category]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_remediation(
        self,
        finding_id: str,
        finding_severity: FindingSeverity = FindingSeverity.INFORMATIONAL,
        remediation_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> FindingRemediation:
        remediation = FindingRemediation(
            finding_id=finding_id,
            finding_severity=finding_severity,
            remediation_score=remediation_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._remediations.append(remediation)
        if len(self._remediations) > self._max_records:
            self._remediations = self._remediations[-self._max_records :]
        logger.info(
            "audit_finding.remediation_added",
            finding_id=finding_id,
            finding_severity=finding_severity.value,
            remediation_score=remediation_score,
        )
        return remediation

    # -- domain operations --------------------------------------------------

    def analyze_finding_distribution(self) -> dict[str, Any]:
        """Group by finding_severity; return count and avg risk_score."""
        sev_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.finding_severity.value
            sev_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for sev, scores in sev_data.items():
            result[sev] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_open_findings(self) -> list[dict[str, Any]]:
        """Return records where finding_status is OPEN."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.finding_status == FindingStatus.OPEN:
                results.append(
                    {
                        "record_id": r.id,
                        "finding_id": r.finding_id,
                        "finding_severity": r.finding_severity.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort descending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_finding_trends(self) -> dict[str, Any]:
        """Split-half comparison on remediation_score; delta threshold 5.0."""
        if len(self._remediations) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [r.remediation_score for r in self._remediations]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "growing"
        else:
            trend = "shrinking"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> AuditFindingReport:
        by_severity: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_severity[r.finding_severity.value] = by_severity.get(r.finding_severity.value, 0) + 1
            by_category[r.finding_category.value] = by_category.get(r.finding_category.value, 0) + 1
            by_status[r.finding_status.value] = by_status.get(r.finding_status.value, 0) + 1
        open_findings = sum(1 for r in self._records if r.finding_status == FindingStatus.OPEN)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        open_list = self.identify_open_findings()
        top_open = [o["finding_id"] for o in open_list[:5]]
        recs: list[str] = []
        if self._records:
            open_pct = round(open_findings / len(self._records) * 100, 2)
            if open_pct > self._max_open_finding_pct:
                recs.append(
                    f"Open finding rate {open_pct}% exceeds threshold "
                    f"({self._max_open_finding_pct}%)"
                )
        if open_findings > 0:
            recs.append(f"{open_findings} open finding(s) — prioritize remediation")
        if not recs:
            recs.append("Audit finding levels are acceptable")
        return AuditFindingReport(
            total_records=len(self._records),
            total_remediations=len(self._remediations),
            open_findings=open_findings,
            avg_risk_score=avg_risk_score,
            by_severity=by_severity,
            by_category=by_category,
            by_status=by_status,
            top_open=top_open,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._remediations.clear()
        logger.info("audit_finding.cleared")
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
            "finding_severity_distribution": sev_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
