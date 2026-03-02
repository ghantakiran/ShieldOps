"""Cost Governance Enforcer — enforce cost governance policies and track violations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ViolationType(StrEnum):
    BUDGET_EXCEEDED = "budget_exceeded"
    UNAPPROVED_RESOURCE = "unapproved_resource"
    MISSING_APPROVAL = "missing_approval"
    TAG_NONCOMPLIANT = "tag_noncompliant"
    RATE_EXCEEDED = "rate_exceeded"


class EnforcementAction(StrEnum):
    ALERT = "alert"
    BLOCK = "block"
    QUARANTINE = "quarantine"
    REQUIRE_APPROVAL = "require_approval"
    AUTO_REMEDIATE = "auto_remediate"


class PolicyScope(StrEnum):
    ORGANIZATION = "organization"
    DEPARTMENT = "department"
    TEAM = "team"
    PROJECT = "project"
    INDIVIDUAL = "individual"


# --- Models ---


class GovernanceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    violation_type: ViolationType = ViolationType.BUDGET_EXCEEDED
    enforcement_action: EnforcementAction = EnforcementAction.ALERT
    policy_scope: PolicyScope = PolicyScope.ORGANIZATION
    violation_count: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class GovernanceViolation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    violation_type: ViolationType = ViolationType.BUDGET_EXCEEDED
    violation_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostGovernanceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_violations: int = 0
    high_violation_count: int = 0
    avg_violation_count: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    top_violators: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostGovernanceEnforcer:
    """Enforce cost governance policies, track violations, detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        max_violation_rate: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_violation_rate = max_violation_rate
        self._records: list[GovernanceRecord] = []
        self._violations: list[GovernanceViolation] = []
        logger.info(
            "cost_governance_enforcer.initialized",
            max_records=max_records,
            max_violation_rate=max_violation_rate,
        )

    # -- record / get / list ------------------------------------------------

    def record_governance(
        self,
        policy_name: str,
        violation_type: ViolationType = ViolationType.BUDGET_EXCEEDED,
        enforcement_action: EnforcementAction = EnforcementAction.ALERT,
        policy_scope: PolicyScope = PolicyScope.ORGANIZATION,
        violation_count: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> GovernanceRecord:
        record = GovernanceRecord(
            policy_name=policy_name,
            violation_type=violation_type,
            enforcement_action=enforcement_action,
            policy_scope=policy_scope,
            violation_count=violation_count,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_governance_enforcer.governance_recorded",
            record_id=record.id,
            policy_name=policy_name,
            violation_type=violation_type.value,
            enforcement_action=enforcement_action.value,
        )
        return record

    def get_governance(self, record_id: str) -> GovernanceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_governance_records(
        self,
        violation_type: ViolationType | None = None,
        enforcement_action: EnforcementAction | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[GovernanceRecord]:
        results = list(self._records)
        if violation_type is not None:
            results = [r for r in results if r.violation_type == violation_type]
        if enforcement_action is not None:
            results = [r for r in results if r.enforcement_action == enforcement_action]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_violation(
        self,
        policy_name: str,
        violation_type: ViolationType = ViolationType.BUDGET_EXCEEDED,
        violation_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> GovernanceViolation:
        violation = GovernanceViolation(
            policy_name=policy_name,
            violation_type=violation_type,
            violation_score=violation_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._violations.append(violation)
        if len(self._violations) > self._max_records:
            self._violations = self._violations[-self._max_records :]
        logger.info(
            "cost_governance_enforcer.violation_added",
            policy_name=policy_name,
            violation_type=violation_type.value,
            violation_score=violation_score,
        )
        return violation

    # -- domain operations --------------------------------------------------

    def analyze_violation_distribution(self) -> dict[str, Any]:
        """Group by violation_type; return count and avg violation_count."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.violation_type.value
            type_data.setdefault(key, []).append(r.violation_count)
        result: dict[str, Any] = {}
        for vtype, counts in type_data.items():
            result[vtype] = {
                "count": len(counts),
                "avg_violation_count": round(sum(counts) / len(counts), 2),
            }
        return result

    def identify_high_violation_policies(self) -> list[dict[str, Any]]:
        """Return records where violation_count > max_violation_rate."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.violation_count > self._max_violation_rate:
                results.append(
                    {
                        "record_id": r.id,
                        "policy_name": r.policy_name,
                        "violation_type": r.violation_type.value,
                        "enforcement_action": r.enforcement_action.value,
                        "violation_count": r.violation_count,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["violation_count"], reverse=True)
        return results

    def rank_by_violation_rate(self) -> list[dict[str, Any]]:
        """Group by service, avg violation_count, sort desc (highest first)."""
        svc_counts: dict[str, list[float]] = {}
        for r in self._records:
            svc_counts.setdefault(r.service, []).append(r.violation_count)
        results: list[dict[str, Any]] = []
        for svc, counts in svc_counts.items():
            results.append(
                {
                    "service": svc,
                    "avg_violation_count": round(sum(counts) / len(counts), 2),
                    "governance_count": len(counts),
                }
            )
        results.sort(key=lambda x: x["avg_violation_count"], reverse=True)
        return results

    def detect_governance_trends(self) -> dict[str, Any]:
        """Split-half comparison on violation_score; delta 5.0."""
        if len(self._violations) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [v.violation_score for v in self._violations]
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

    def generate_report(self) -> CostGovernanceReport:
        by_type: dict[str, int] = {}
        by_action: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_type[r.violation_type.value] = by_type.get(r.violation_type.value, 0) + 1
            by_action[r.enforcement_action.value] = by_action.get(r.enforcement_action.value, 0) + 1
            by_scope[r.policy_scope.value] = by_scope.get(r.policy_scope.value, 0) + 1
        high_violation_count = sum(
            1 for r in self._records if r.violation_count > self._max_violation_rate
        )
        avg_violation = (
            round(
                sum(r.violation_count for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high_viol = self.identify_high_violation_policies()
        top_violators = [p["policy_name"] for p in high_viol]
        recs: list[str] = []
        if high_viol:
            recs.append(
                f"{len(high_viol)} high-violation policy(ies) detected — review governance rules"
            )
        above = sum(1 for r in self._records if r.violation_count > self._max_violation_rate)
        if above > 0:
            recs.append(
                f"{above} policy(ies) above max violation rate ({self._max_violation_rate})"
            )
        if not recs:
            recs.append("Cost governance violation levels are acceptable")
        return CostGovernanceReport(
            total_records=len(self._records),
            total_violations=len(self._violations),
            high_violation_count=high_violation_count,
            avg_violation_count=avg_violation,
            by_type=by_type,
            by_action=by_action,
            by_scope=by_scope,
            top_violators=top_violators,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._violations.clear()
        logger.info("cost_governance_enforcer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.violation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_violations": len(self._violations),
            "max_violation_rate": self._max_violation_rate,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
