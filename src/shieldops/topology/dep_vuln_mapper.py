"""Dependency Vulnerability Mapper — map and analyze dependency vulnerabilities by severity."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

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


class DependencyType(StrEnum):
    DIRECT = "direct"
    TRANSITIVE = "transitive"
    DEV_ONLY = "dev_only"
    OPTIONAL = "optional"
    PEER = "peer"


class RemediationStatus(StrEnum):
    PATCHED = "patched"
    PENDING = "pending"
    NO_FIX = "no_fix"
    MITIGATED = "mitigated"
    ACCEPTED = "accepted"


# --- Models ---


class VulnMappingRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    dependency_name: str = ""
    vuln_id: str = ""
    severity: VulnSeverity = VulnSeverity.MEDIUM
    dependency_type: DependencyType = DependencyType.DIRECT
    remediation_status: RemediationStatus = RemediationStatus.PENDING
    risk_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class VulnDependencyDetail(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    dependency_name: str = ""
    vuln_id: str = ""
    affected_version: str = ""
    fixed_version: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DepVulnMapperReport(BaseModel):
    total_mappings: int = 0
    total_details: int = 0
    avg_risk_score: float = 0.0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_remediation_status: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DependencyVulnerabilityMapper:
    """Map and analyze dependency vulnerabilities by severity and remediation status."""

    def __init__(
        self,
        max_records: int = 200000,
        max_critical_vulns: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_critical_vulns = max_critical_vulns
        self._records: list[VulnMappingRecord] = []
        self._details: list[VulnDependencyDetail] = []
        logger.info(
            "dep_vuln_mapper.initialized",
            max_records=max_records,
            max_critical_vulns=max_critical_vulns,
        )

    # -- record / get / list ---------------------------------------------

    def record_mapping(
        self,
        dependency_name: str,
        vuln_id: str = "",
        severity: VulnSeverity = VulnSeverity.MEDIUM,
        dependency_type: DependencyType = DependencyType.DIRECT,
        remediation_status: RemediationStatus = RemediationStatus.PENDING,
        risk_score: float = 0.0,
        details: str = "",
    ) -> VulnMappingRecord:
        record = VulnMappingRecord(
            dependency_name=dependency_name,
            vuln_id=vuln_id,
            severity=severity,
            dependency_type=dependency_type,
            remediation_status=remediation_status,
            risk_score=risk_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dep_vuln_mapper.mapping_recorded",
            record_id=record.id,
            dependency_name=dependency_name,
            severity=severity.value,
        )
        return record

    def get_mapping(self, record_id: str) -> VulnMappingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_mappings(
        self,
        dependency_name: str | None = None,
        severity: VulnSeverity | None = None,
        limit: int = 50,
    ) -> list[VulnMappingRecord]:
        results = list(self._records)
        if dependency_name is not None:
            results = [r for r in results if r.dependency_name == dependency_name]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        return results[-limit:]

    def add_dependency_detail(
        self,
        dependency_name: str,
        vuln_id: str = "",
        affected_version: str = "",
        fixed_version: str = "",
        description: str = "",
    ) -> VulnDependencyDetail:
        detail = VulnDependencyDetail(
            dependency_name=dependency_name,
            vuln_id=vuln_id,
            affected_version=affected_version,
            fixed_version=fixed_version,
            description=description,
        )
        self._details.append(detail)
        if len(self._details) > self._max_records:
            self._details = self._details[-self._max_records :]
        logger.info(
            "dep_vuln_mapper.detail_added",
            dependency_name=dependency_name,
            vuln_id=vuln_id,
        )
        return detail

    # -- domain operations -----------------------------------------------

    def analyze_vuln_by_severity(self, severity: VulnSeverity) -> dict[str, Any]:
        """Analyze vulnerabilities for a specific severity level."""
        records = [r for r in self._records if r.severity == severity]
        if not records:
            return {"severity": severity.value, "status": "no_data"}
        avg_risk = round(sum(r.risk_score for r in records) / len(records), 2)
        pending = sum(1 for r in records if r.remediation_status == RemediationStatus.PENDING)
        return {
            "severity": severity.value,
            "total": len(records),
            "avg_risk_score": avg_risk,
            "pending_remediation": pending,
            "within_limits": len(records) <= self._max_critical_vulns,
        }

    def identify_critical_dependencies(self) -> list[dict[str, Any]]:
        """Find dependencies with critical or high severity vulnerabilities."""
        critical_sevs = {VulnSeverity.CRITICAL, VulnSeverity.HIGH}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.severity in critical_sevs:
                results.append(
                    {
                        "dependency_name": r.dependency_name,
                        "vuln_id": r.vuln_id,
                        "severity": r.severity.value,
                        "risk_score": r.risk_score,
                        "remediation_status": r.remediation_status.value,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Rank dependencies by risk score descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "dependency_name": r.dependency_name,
                    "vuln_id": r.vuln_id,
                    "risk_score": r.risk_score,
                    "severity": r.severity.value,
                    "remediation_status": r.remediation_status.value,
                }
            )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def detect_vuln_trends(self) -> list[dict[str, Any]]:
        """Detect vulnerability trends per dependency using sufficient historical data."""
        dep_records: dict[str, list[VulnMappingRecord]] = {}
        for r in self._records:
            dep_records.setdefault(r.dependency_name, []).append(r)
        results: list[dict[str, Any]] = []
        for name, recs in dep_records.items():
            if len(recs) > 3:
                scores = [r.risk_score for r in recs]
                trend = "increasing" if scores[-1] > scores[0] else "decreasing"
                results.append(
                    {
                        "dependency_name": name,
                        "record_count": len(recs),
                        "risk_trend": trend,
                    }
                )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> DepVulnMapperReport:
        by_severity: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
            by_status[r.remediation_status.value] = by_status.get(r.remediation_status.value, 0) + 1
        avg_risk = (
            round(sum(r.risk_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        critical_sevs = {VulnSeverity.CRITICAL, VulnSeverity.HIGH}
        critical_count = sum(1 for r in self._records if r.severity in critical_sevs)
        recs: list[str] = []
        if critical_count > self._max_critical_vulns:
            recs.append(
                f"{critical_count} critical/high vulns exceeds limit of"
                f" {int(self._max_critical_vulns)}"
            )
        elif critical_count > 0:
            recs.append(f"{critical_count} critical/high severity vulnerability(ies) detected")
        pending = sum(1 for r in self._records if r.remediation_status == RemediationStatus.PENDING)
        if pending > 0:
            recs.append(f"{pending} vulnerability(ies) pending remediation")
        if not recs:
            recs.append("Dependency vulnerability posture within acceptable limits")
        return DepVulnMapperReport(
            total_mappings=len(self._records),
            total_details=len(self._details),
            avg_risk_score=avg_risk,
            by_severity=by_severity,
            by_remediation_status=by_status,
            critical_count=critical_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._details.clear()
        logger.info("dep_vuln_mapper.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        severity_dist: dict[str, int] = {}
        for r in self._records:
            key = r.severity.value
            severity_dist[key] = severity_dist.get(key, 0) + 1
        return {
            "total_mappings": len(self._records),
            "total_details": len(self._details),
            "max_critical_vulns": self._max_critical_vulns,
            "severity_distribution": severity_dist,
            "unique_dependencies": len({r.dependency_name for r in self._records}),
        }
