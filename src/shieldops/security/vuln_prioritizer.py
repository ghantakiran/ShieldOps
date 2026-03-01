"""Vulnerability Prioritizer — prioritize vulns, rules, and trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VulnSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class ExploitMaturity(StrEnum):
    WEAPONIZED = "weaponized"
    POC_AVAILABLE = "poc_available"
    THEORETICAL = "theoretical"
    UNPROVEN = "unproven"
    NOT_APPLICABLE = "not_applicable"


class RemediationStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PATCHED = "patched"
    MITIGATED = "mitigated"
    ACCEPTED = "accepted"


# --- Models ---


class VulnRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cve_id: str = ""
    vuln_severity: VulnSeverity = VulnSeverity.LOW
    exploit_maturity: ExploitMaturity = ExploitMaturity.UNPROVEN
    remediation_status: RemediationStatus = RemediationStatus.OPEN
    cvss_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class VulnPriorityRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cve_pattern: str = ""
    vuln_severity: VulnSeverity = VulnSeverity.LOW
    max_age_days: int = 0
    auto_escalate: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class VulnPriorityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    critical_count: int = 0
    avg_cvss_score: float = 0.0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_maturity: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    urgent_vulns: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class VulnerabilityPrioritizer:
    """Prioritize vulnerabilities, identify urgent issues, and detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        critical_cvss_threshold: float = 9.0,
    ) -> None:
        self._max_records = max_records
        self._critical_cvss_threshold = critical_cvss_threshold
        self._records: list[VulnRecord] = []
        self._rules: list[VulnPriorityRule] = []
        logger.info(
            "vuln_prioritizer.initialized",
            max_records=max_records,
            critical_cvss_threshold=critical_cvss_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_vuln(
        self,
        cve_id: str,
        vuln_severity: VulnSeverity = VulnSeverity.LOW,
        exploit_maturity: ExploitMaturity = ExploitMaturity.UNPROVEN,
        remediation_status: RemediationStatus = RemediationStatus.OPEN,
        cvss_score: float = 0.0,
        team: str = "",
    ) -> VulnRecord:
        record = VulnRecord(
            cve_id=cve_id,
            vuln_severity=vuln_severity,
            exploit_maturity=exploit_maturity,
            remediation_status=remediation_status,
            cvss_score=cvss_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "vuln_prioritizer.vuln_recorded",
            record_id=record.id,
            cve_id=cve_id,
            vuln_severity=vuln_severity.value,
            cvss_score=cvss_score,
        )
        return record

    def get_vuln(self, record_id: str) -> VulnRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_vulns(
        self,
        severity: VulnSeverity | None = None,
        maturity: ExploitMaturity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[VulnRecord]:
        results = list(self._records)
        if severity is not None:
            results = [r for r in results if r.vuln_severity == severity]
        if maturity is not None:
            results = [r for r in results if r.exploit_maturity == maturity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        cve_pattern: str,
        vuln_severity: VulnSeverity = VulnSeverity.LOW,
        max_age_days: int = 0,
        auto_escalate: bool = False,
        description: str = "",
    ) -> VulnPriorityRule:
        rule = VulnPriorityRule(
            cve_pattern=cve_pattern,
            vuln_severity=vuln_severity,
            max_age_days=max_age_days,
            auto_escalate=auto_escalate,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "vuln_prioritizer.rule_added",
            cve_pattern=cve_pattern,
            vuln_severity=vuln_severity.value,
            max_age_days=max_age_days,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_severity_distribution(self) -> dict[str, Any]:
        """Group by severity; return count and avg cvss per severity."""
        sev_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.vuln_severity.value
            sev_data.setdefault(key, []).append(r.cvss_score)
        result: dict[str, Any] = {}
        for sev, scores in sev_data.items():
            result[sev] = {
                "count": len(scores),
                "avg_cvss": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_urgent_vulns(self) -> list[dict[str, Any]]:
        """Return records where severity == CRITICAL or cvss >= threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if (
                r.vuln_severity == VulnSeverity.CRITICAL
                or r.cvss_score >= self._critical_cvss_threshold
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "cve_id": r.cve_id,
                        "vuln_severity": r.vuln_severity.value,
                        "cvss_score": r.cvss_score,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_cvss(self) -> list[dict[str, Any]]:
        """Group by team, avg cvss_score, sort descending."""
        team_data: dict[str, list[float]] = {}
        for r in self._records:
            team_data.setdefault(r.team, []).append(r.cvss_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_data.items():
            results.append(
                {
                    "team": team,
                    "vuln_count": len(scores),
                    "avg_cvss": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_cvss"], reverse=True)
        return results

    def detect_vuln_trends(self) -> dict[str, Any]:
        """Split-half on max_age_days; delta threshold 5.0."""
        if len(self._rules) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        ages = [ru.max_age_days for ru in self._rules]
        mid = len(ages) // 2
        first_half = ages[:mid]
        second_half = ages[mid:]
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

    def generate_report(self) -> VulnPriorityReport:
        by_severity: dict[str, int] = {}
        by_maturity: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_severity[r.vuln_severity.value] = by_severity.get(r.vuln_severity.value, 0) + 1
            by_maturity[r.exploit_maturity.value] = by_maturity.get(r.exploit_maturity.value, 0) + 1
            by_status[r.remediation_status.value] = by_status.get(r.remediation_status.value, 0) + 1
        critical_count = sum(1 for r in self._records if r.vuln_severity == VulnSeverity.CRITICAL)
        scores = [r.cvss_score for r in self._records]
        avg_cvss = round(sum(scores) / len(scores), 2) if scores else 0.0
        urgent = self.identify_urgent_vulns()
        urgent_cves = [u["cve_id"] for u in urgent[:5]]
        recs: list[str] = []
        if critical_count > 0:
            recs.append(
                f"{critical_count} critical vulnerability(ies) detected — immediate action required"
            )
        if avg_cvss >= self._critical_cvss_threshold and self._records:
            recs.append(
                f"Average CVSS score {avg_cvss} exceeds threshold ({self._critical_cvss_threshold})"
            )
        if not recs:
            recs.append("Vulnerability levels are acceptable")
        return VulnPriorityReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            critical_count=critical_count,
            avg_cvss_score=avg_cvss,
            by_severity=by_severity,
            by_maturity=by_maturity,
            by_status=by_status,
            urgent_vulns=urgent_cves,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("vuln_prioritizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        sev_dist: dict[str, int] = {}
        for r in self._records:
            key = r.vuln_severity.value
            sev_dist[key] = sev_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "critical_cvss_threshold": self._critical_cvss_threshold,
            "severity_distribution": sev_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_cves": len({r.cve_id for r in self._records}),
        }
