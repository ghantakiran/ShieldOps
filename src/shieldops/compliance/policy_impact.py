"""Policy Impact Scorer — analyze impact of policy changes on services and compliance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PolicyDomain(StrEnum):
    SECURITY = "security"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    ACCESS_CONTROL = "access_control"


class ImpactSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class ImpactScope(StrEnum):
    ORGANIZATION_WIDE = "organization_wide"
    DEPARTMENT = "department"
    TEAM = "team"
    SERVICE = "service"
    INDIVIDUAL = "individual"


# --- Models ---


class PolicyImpactRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    domain: PolicyDomain = PolicyDomain.SECURITY
    severity: ImpactSeverity = ImpactSeverity.MEDIUM
    scope: ImpactScope = ImpactScope.SERVICE
    affected_services_count: int = 0
    risk_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyConflict(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_a: str = ""
    policy_b: str = ""
    conflict_type: str = ""
    severity: ImpactSeverity = ImpactSeverity.MEDIUM
    resolution: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyImpactReport(BaseModel):
    total_impacts: int = 0
    total_conflicts: int = 0
    avg_risk_score: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    high_impact_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PolicyImpactScorer:
    """Analyze impact of policy changes on services and compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        max_conflict_count: int = 50,
    ) -> None:
        self._max_records = max_records
        self._max_conflict_count = max_conflict_count
        self._records: list[PolicyImpactRecord] = []
        self._conflicts: list[PolicyConflict] = []
        logger.info(
            "policy_impact.initialized",
            max_records=max_records,
            max_conflict_count=max_conflict_count,
        )

    # -- internal helpers ------------------------------------------------

    def _risk_to_severity(self, risk_score: float) -> ImpactSeverity:
        if risk_score >= 90:
            return ImpactSeverity.CRITICAL
        if risk_score >= 70:
            return ImpactSeverity.HIGH
        if risk_score >= 50:
            return ImpactSeverity.MEDIUM
        if risk_score >= 30:
            return ImpactSeverity.LOW
        return ImpactSeverity.NEGLIGIBLE

    # -- record / get / list ---------------------------------------------

    def record_impact(
        self,
        policy_name: str,
        domain: PolicyDomain = PolicyDomain.SECURITY,
        severity: ImpactSeverity | None = None,
        scope: ImpactScope = ImpactScope.SERVICE,
        affected_services_count: int = 0,
        risk_score: float = 0.0,
        details: str = "",
    ) -> PolicyImpactRecord:
        if severity is None:
            severity = self._risk_to_severity(risk_score)
        record = PolicyImpactRecord(
            policy_name=policy_name,
            domain=domain,
            severity=severity,
            scope=scope,
            affected_services_count=affected_services_count,
            risk_score=risk_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "policy_impact.impact_recorded",
            record_id=record.id,
            policy_name=policy_name,
            domain=domain.value,
            severity=severity.value,
        )
        return record

    def get_impact(self, record_id: str) -> PolicyImpactRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_impacts(
        self,
        policy_name: str | None = None,
        domain: PolicyDomain | None = None,
        limit: int = 50,
    ) -> list[PolicyImpactRecord]:
        results = list(self._records)
        if policy_name is not None:
            results = [r for r in results if r.policy_name == policy_name]
        if domain is not None:
            results = [r for r in results if r.domain == domain]
        return results[-limit:]

    def record_conflict(
        self,
        policy_a: str,
        policy_b: str,
        conflict_type: str = "",
        severity: ImpactSeverity = ImpactSeverity.MEDIUM,
        resolution: str = "",
    ) -> PolicyConflict:
        conflict = PolicyConflict(
            policy_a=policy_a,
            policy_b=policy_b,
            conflict_type=conflict_type,
            severity=severity,
            resolution=resolution,
        )
        self._conflicts.append(conflict)
        if len(self._conflicts) > self._max_conflict_count:
            self._conflicts = self._conflicts[-self._max_conflict_count :]
        logger.info(
            "policy_impact.conflict_recorded",
            policy_a=policy_a,
            policy_b=policy_b,
            conflict_type=conflict_type,
        )
        return conflict

    # -- domain operations -----------------------------------------------

    def analyze_policy_impact(self, policy_name: str) -> dict[str, Any]:
        """Analyze impact for a specific policy."""
        records = [r for r in self._records if r.policy_name == policy_name]
        if not records:
            return {"policy_name": policy_name, "status": "no_data"}
        latest = records[-1]
        avg_risk = round(sum(r.risk_score for r in records) / len(records), 2)
        return {
            "policy_name": policy_name,
            "total_records": len(records),
            "domain": latest.domain.value,
            "severity": latest.severity.value,
            "scope": latest.scope.value,
            "avg_risk_score": avg_risk,
            "affected_services_count": latest.affected_services_count,
        }

    def identify_high_impact_policies(
        self,
    ) -> list[dict[str, Any]]:
        """Find policies with severity >= HIGH."""
        high = {ImpactSeverity.CRITICAL, ImpactSeverity.HIGH}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.severity in high:
                results.append(
                    {
                        "policy_name": r.policy_name,
                        "domain": r.domain.value,
                        "severity": r.severity.value,
                        "scope": r.scope.value,
                        "risk_score": r.risk_score,
                        "affected_services_count": r.affected_services_count,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_by_affected_scope(self) -> list[dict[str, Any]]:
        """Rank by affected_services_count descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "policy_name": r.policy_name,
                    "domain": r.domain.value,
                    "severity": r.severity.value,
                    "scope": r.scope.value,
                    "affected_services_count": r.affected_services_count,
                    "risk_score": r.risk_score,
                }
            )
        results.sort(key=lambda x: x["affected_services_count"], reverse=True)
        return results

    def detect_policy_conflicts(self) -> list[dict[str, Any]]:
        """Return all conflicts."""
        results: list[dict[str, Any]] = []
        for c in self._conflicts:
            results.append(
                {
                    "policy_a": c.policy_a,
                    "policy_b": c.policy_b,
                    "conflict_type": c.conflict_type,
                    "severity": c.severity.value,
                    "resolution": c.resolution,
                }
            )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> PolicyImpactReport:
        by_domain: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_domain[r.domain.value] = by_domain.get(r.domain.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
        avg_risk = (
            round(
                sum(r.risk_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high_impact = sum(
            1 for r in self._records if r.severity in (ImpactSeverity.CRITICAL, ImpactSeverity.HIGH)
        )
        recs: list[str] = []
        if high_impact > 0:
            recs.append(f"{high_impact} high/critical impact policy change(s) detected")
        if self._conflicts:
            recs.append(f"{len(self._conflicts)} policy conflict(s) require resolution")
        if not recs:
            recs.append("Policy impact levels within acceptable range")
        return PolicyImpactReport(
            total_impacts=len(self._records),
            total_conflicts=len(self._conflicts),
            avg_risk_score=avg_risk,
            by_domain=by_domain,
            by_severity=by_severity,
            high_impact_count=high_impact,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._conflicts.clear()
        logger.info("policy_impact.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            key = r.domain.value
            domain_dist[key] = domain_dist.get(key, 0) + 1
        return {
            "total_impacts": len(self._records),
            "total_conflicts": len(self._conflicts),
            "max_conflict_count": self._max_conflict_count,
            "domain_distribution": domain_dist,
            "unique_policies": len({r.policy_name for r in self._records}),
        }
