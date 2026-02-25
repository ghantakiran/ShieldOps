"""Policy Violation Tracker — track and trend runtime OPA policy violations across agent actions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ViolationSeverity(StrEnum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ViolatorType(StrEnum):
    AGENT = "agent"
    SERVICE = "service"
    TEAM = "team"
    AUTOMATED_PIPELINE = "automated_pipeline"
    MANUAL_USER = "manual_user"


class PolicyDomain(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    DATA_ACCESS = "data_access"
    DEPLOYMENT = "deployment"
    SECURITY = "security"
    COST_CONTROL = "cost_control"


# --- Models ---


class PolicyViolation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    violator_name: str = ""
    violator_type: ViolatorType = ViolatorType.AGENT
    severity: ViolationSeverity = ViolationSeverity.LOW
    domain: PolicyDomain = PolicyDomain.INFRASTRUCTURE
    description: str = ""
    resolved: bool = False
    created_at: float = Field(default_factory=time.time)


class ViolationTrend(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    period_label: str = ""
    violation_count: int = 0
    severity_breakdown: dict[str, int] = Field(default_factory=dict)
    trend_direction: str = "stable"
    created_at: float = Field(default_factory=time.time)


class ViolationReport(BaseModel):
    total_violations: int = 0
    total_resolved: int = 0
    total_unresolved: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_violator_type: dict[str, int] = Field(default_factory=dict)
    repeat_offenders: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PolicyViolationTracker:
    """Track and trend runtime OPA policy violations across agent actions."""

    def __init__(
        self,
        max_records: int = 500000,
        repeat_threshold: int = 5,
    ) -> None:
        self._max_records = max_records
        self._repeat_threshold = repeat_threshold
        self._items: list[PolicyViolation] = []
        self._trends: list[ViolationTrend] = []
        logger.info(
            "policy_violation_tracker.initialized",
            max_records=max_records,
            repeat_threshold=repeat_threshold,
        )

    # -- record / get / list -----------------------------------------

    def record_violation(
        self,
        policy_name: str,
        violator_name: str,
        violator_type: ViolatorType = ViolatorType.AGENT,
        severity: ViolationSeverity = ViolationSeverity.LOW,
        domain: PolicyDomain = PolicyDomain.INFRASTRUCTURE,
        description: str = "",
        **kw: Any,
    ) -> PolicyViolation:
        violation = PolicyViolation(
            policy_name=policy_name,
            violator_name=violator_name,
            violator_type=violator_type,
            severity=severity,
            domain=domain,
            description=description,
            **kw,
        )
        self._items.append(violation)
        if len(self._items) > self._max_records:
            self._items = self._items[-self._max_records :]
        logger.info(
            "policy_violation_tracker.violation_recorded",
            violation_id=violation.id,
            policy_name=policy_name,
            violator_name=violator_name,
        )
        return violation

    def get_violation(self, violation_id: str) -> PolicyViolation | None:
        for v in self._items:
            if v.id == violation_id:
                return v
        return None

    def list_violations(
        self,
        policy_name: str | None = None,
        severity: ViolationSeverity | None = None,
        domain: PolicyDomain | None = None,
        limit: int = 50,
    ) -> list[PolicyViolation]:
        results = list(self._items)
        if policy_name is not None:
            results = [r for r in results if r.policy_name == policy_name]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        if domain is not None:
            results = [r for r in results if r.domain == domain]
        return results[-limit:]

    # -- trends ------------------------------------------------------

    def compute_trend(
        self,
        policy_name: str,
        period_label: str = "current",
    ) -> ViolationTrend:
        """Compute violation trend for a policy."""
        violations = [v for v in self._items if v.policy_name == policy_name]
        sev_breakdown: dict[str, int] = {}
        for v in violations:
            key = v.severity.value
            sev_breakdown[key] = sev_breakdown.get(key, 0) + 1
        # Simple trend: compare first half vs second half
        if len(violations) < 2:
            direction = "stable"
        else:
            mid = len(violations) // 2
            first_count = mid
            second_count = len(violations) - mid
            if second_count > first_count * 1.2:
                direction = "increasing"
            elif second_count < first_count * 0.8:
                direction = "decreasing"
            else:
                direction = "stable"
        trend = ViolationTrend(
            policy_name=policy_name,
            period_label=period_label,
            violation_count=len(violations),
            severity_breakdown=sev_breakdown,
            trend_direction=direction,
        )
        self._trends.append(trend)
        logger.info(
            "policy_violation_tracker.trend_computed",
            trend_id=trend.id,
            policy_name=policy_name,
        )
        return trend

    def list_trends(
        self,
        policy_name: str | None = None,
        limit: int = 50,
    ) -> list[ViolationTrend]:
        results = list(self._trends)
        if policy_name is not None:
            results = [r for r in results if r.policy_name == policy_name]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def identify_repeat_offenders(self) -> list[dict[str, Any]]:
        """Identify violators who exceed the repeat threshold."""
        by_violator: dict[str, int] = {}
        for v in self._items:
            by_violator[v.violator_name] = by_violator.get(v.violator_name, 0) + 1
        offenders = [
            {"violator_name": name, "violation_count": count}
            for name, count in sorted(by_violator.items(), key=lambda x: x[1], reverse=True)
            if count >= self._repeat_threshold
        ]
        return offenders

    def get_policy_effectiveness(
        self,
        policy_name: str,
    ) -> dict[str, Any]:
        """Evaluate how effective a policy is based on violation trends."""
        violations = [v for v in self._items if v.policy_name == policy_name]
        if not violations:
            return {
                "policy_name": policy_name,
                "total_violations": 0,
                "effectiveness": "unknown",
            }
        resolved = sum(1 for v in violations if v.resolved)
        resolution_rate = round(resolved / len(violations) * 100, 2)
        effectiveness = (
            "highly_effective"
            if resolution_rate >= 80
            else "moderately_effective"
            if resolution_rate >= 50
            else "needs_improvement"
        )
        return {
            "policy_name": policy_name,
            "total_violations": len(violations),
            "resolved": resolved,
            "resolution_rate_pct": resolution_rate,
            "effectiveness": effectiveness,
        }

    def get_violator_profile(
        self,
        violator_name: str,
    ) -> dict[str, Any]:
        """Get a detailed profile of a violator."""
        violations = [v for v in self._items if v.violator_name == violator_name]
        if not violations:
            return {
                "violator_name": violator_name,
                "total_violations": 0,
                "found": False,
            }
        by_policy: dict[str, int] = {}
        for v in violations:
            by_policy[v.policy_name] = by_policy.get(v.policy_name, 0) + 1
        by_severity: dict[str, int] = {}
        for v in violations:
            key = v.severity.value
            by_severity[key] = by_severity.get(key, 0) + 1
        return {
            "violator_name": violator_name,
            "total_violations": len(violations),
            "by_policy": by_policy,
            "by_severity": by_severity,
            "found": True,
        }

    # -- report / stats ----------------------------------------------

    def generate_violation_report(self) -> ViolationReport:
        by_severity: dict[str, int] = {}
        for v in self._items:
            key = v.severity.value
            by_severity[key] = by_severity.get(key, 0) + 1
        by_domain: dict[str, int] = {}
        for v in self._items:
            key = v.domain.value
            by_domain[key] = by_domain.get(key, 0) + 1
        by_violator_type: dict[str, int] = {}
        for v in self._items:
            key = v.violator_type.value
            by_violator_type[key] = by_violator_type.get(key, 0) + 1
        resolved = sum(1 for v in self._items if v.resolved)
        offenders = self.identify_repeat_offenders()
        offender_names = [o["violator_name"] for o in offenders[:5]]
        recs: list[str] = []
        critical = by_severity.get("critical", 0)
        if critical > 0:
            recs.append(f"{critical} critical violation(s) require immediate attention")
        if offenders:
            recs.append(f"{len(offenders)} repeat offender(s) identified")
        if not recs:
            recs.append("Policy violations within acceptable range")
        return ViolationReport(
            total_violations=len(self._items),
            total_resolved=resolved,
            total_unresolved=len(self._items) - resolved,
            by_severity=by_severity,
            by_domain=by_domain,
            by_violator_type=by_violator_type,
            repeat_offenders=offender_names,
            recommendations=recs,
        )

    def clear_data(self) -> int:
        count = len(self._items)
        self._items.clear()
        self._trends.clear()
        logger.info("policy_violation_tracker.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        sev_dist: dict[str, int] = {}
        for v in self._items:
            key = v.severity.value
            sev_dist[key] = sev_dist.get(key, 0) + 1
        return {
            "total_violations": len(self._items),
            "total_trends": len(self._trends),
            "repeat_threshold": self._repeat_threshold,
            "severity_distribution": sev_dist,
        }
