"""Audit Compliance Reporter — generate compliance reports, track audit gaps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReportType(StrEnum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    ISO_27001 = "iso_27001"
    GDPR = "gdpr"


class ComplianceLevel(StrEnum):
    COMPLIANT = "compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"
    EXEMPT = "exempt"
    UNDER_REVIEW = "under_review"


class AuditScope(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    TARGETED = "targeted"
    FOLLOW_UP = "follow_up"
    CONTINUOUS = "continuous"


# --- Models ---


class ComplianceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    framework: str = ""
    report_type: ReportType = ReportType.SOC2
    compliance_level: ComplianceLevel = ComplianceLevel.UNDER_REVIEW
    audit_scope: AuditScope = AuditScope.FULL
    compliance_score: float = 0.0
    findings_count: int = 0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    report_type: ReportType = ReportType.SOC2
    audit_scope: AuditScope = AuditScope.FULL
    required_evidence_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    compliant_count: int = 0
    avg_compliance_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    non_compliant: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditComplianceReporter:
    """Generate compliance reports, identify gaps, track audit posture."""

    def __init__(
        self,
        max_records: int = 200000,
        min_compliance_score: float = 85.0,
    ) -> None:
        self._max_records = max_records
        self._min_compliance_score = min_compliance_score
        self._records: list[ComplianceRecord] = []
        self._rules: list[ComplianceRule] = []
        logger.info(
            "compliance_reporter.initialized",
            max_records=max_records,
            min_compliance_score=min_compliance_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_compliance(
        self,
        framework: str,
        report_type: ReportType = ReportType.SOC2,
        compliance_level: ComplianceLevel = ComplianceLevel.UNDER_REVIEW,
        audit_scope: AuditScope = AuditScope.FULL,
        compliance_score: float = 0.0,
        findings_count: int = 0,
        team: str = "",
    ) -> ComplianceRecord:
        record = ComplianceRecord(
            framework=framework,
            report_type=report_type,
            compliance_level=compliance_level,
            audit_scope=audit_scope,
            compliance_score=compliance_score,
            findings_count=findings_count,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "compliance_reporter.compliance_recorded",
            record_id=record.id,
            framework=framework,
            report_type=report_type.value,
            compliance_level=compliance_level.value,
        )
        return record

    def get_compliance(self, record_id: str) -> ComplianceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_compliance_records(
        self,
        report_type: ReportType | None = None,
        compliance_level: ComplianceLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ComplianceRecord]:
        results = list(self._records)
        if report_type is not None:
            results = [r for r in results if r.report_type == report_type]
        if compliance_level is not None:
            results = [r for r in results if r.compliance_level == compliance_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        control_id: str,
        report_type: ReportType = ReportType.SOC2,
        audit_scope: AuditScope = AuditScope.FULL,
        required_evidence_count: int = 0,
        description: str = "",
    ) -> ComplianceRule:
        rule = ComplianceRule(
            control_id=control_id,
            report_type=report_type,
            audit_scope=audit_scope,
            required_evidence_count=required_evidence_count,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "compliance_reporter.rule_added",
            control_id=control_id,
            report_type=report_type.value,
            required_evidence_count=required_evidence_count,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_compliance_gaps(self) -> dict[str, Any]:
        """Group by report_type; return count and avg compliance_score per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.report_type.value
            type_data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for rtype, scores in type_data.items():
            result[rtype] = {
                "count": len(scores),
                "avg_compliance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_non_compliant(self) -> list[dict[str, Any]]:
        """Return records where compliance_level == NON_COMPLIANT."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_level == ComplianceLevel.NON_COMPLIANT:
                results.append(
                    {
                        "record_id": r.id,
                        "framework": r.framework,
                        "compliance_score": r.compliance_score,
                        "findings_count": r.findings_count,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_compliance_score(self) -> list[dict[str, Any]]:
        """Group by team, avg compliance score, sort ascending (worst first)."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.compliance_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_compliance_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["avg_compliance_score"],
        )
        return results

    def detect_compliance_trends(self) -> dict[str, Any]:
        """Split-half on compliance_score; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [r.compliance_score for r in self._records]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> AuditComplianceReport:
        by_type: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_type[r.report_type.value] = by_type.get(r.report_type.value, 0) + 1
            by_level[r.compliance_level.value] = by_level.get(r.compliance_level.value, 0) + 1
            by_scope[r.audit_scope.value] = by_scope.get(r.audit_scope.value, 0) + 1
        compliant_count = sum(
            1 for r in self._records if r.compliance_level == ComplianceLevel.COMPLIANT
        )
        avg_score = (
            round(
                sum(r.compliance_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        non_compliant = [
            r.framework
            for r in self._records
            if r.compliance_level == ComplianceLevel.NON_COMPLIANT
        ]
        recs: list[str] = []
        if avg_score < self._min_compliance_score and self._records:
            recs.append(
                f"Average compliance score {avg_score}% is below "
                f"threshold ({self._min_compliance_score}%)"
            )
        if non_compliant:
            recs.append(
                f"{len(non_compliant)} non-compliant framework(s) detected — review findings"
            )
        if not recs:
            recs.append("Compliance posture is acceptable")
        return AuditComplianceReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            compliant_count=compliant_count,
            avg_compliance_score=avg_score,
            by_type=by_type,
            by_level=by_level,
            by_scope=by_scope,
            non_compliant=non_compliant,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("compliance_reporter.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.report_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "min_compliance_score": self._min_compliance_score,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_frameworks": len({r.framework for r in self._records}),
        }
