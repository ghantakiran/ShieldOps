"""Policy Enforcement Monitor — track policy enforcement actions and violations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EnforcementAction(StrEnum):
    BLOCK = "block"
    WARN = "warn"
    AUDIT = "audit"
    REMEDIATE = "remediate"
    EXEMPT = "exempt"


class EnforcementScope(StrEnum):
    ORGANIZATION = "organization"
    TEAM = "team"
    SERVICE = "service"
    ENVIRONMENT = "environment"
    RESOURCE = "resource"


class PolicyCategory(StrEnum):
    SECURITY = "security"
    COMPLIANCE = "compliance"
    COST = "cost"
    OPERATIONAL = "operational"
    GOVERNANCE = "governance"


# --- Models ---


class EnforcementRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    action: EnforcementAction = EnforcementAction.AUDIT
    scope: EnforcementScope = EnforcementScope.SERVICE
    category: PolicyCategory = PolicyCategory.SECURITY
    target: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class EnforcementViolation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    scope: EnforcementScope = EnforcementScope.SERVICE
    category: PolicyCategory = PolicyCategory.SECURITY
    target: str = ""
    violation_count: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyEnforcerReport(BaseModel):
    total_enforcements: int = 0
    total_violations: int = 0
    violation_rate_pct: float = 0.0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    frequent_violation_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PolicyEnforcementMonitor:
    """Track policy enforcement actions and violations."""

    def __init__(
        self,
        max_records: int = 200000,
        max_violation_rate_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_violation_rate_pct = max_violation_rate_pct
        self._records: list[EnforcementRecord] = []
        self._violations: list[EnforcementViolation] = []
        logger.info(
            "policy_enforcer.initialized",
            max_records=max_records,
            max_violation_rate_pct=max_violation_rate_pct,
        )

    # -- record / get / list -------------------------------------------

    def record_enforcement(
        self,
        policy_name: str,
        action: EnforcementAction = EnforcementAction.AUDIT,
        scope: EnforcementScope = EnforcementScope.SERVICE,
        category: PolicyCategory = PolicyCategory.SECURITY,
        target: str = "",
        details: str = "",
    ) -> EnforcementRecord:
        record = EnforcementRecord(
            policy_name=policy_name,
            action=action,
            scope=scope,
            category=category,
            target=target,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "policy_enforcer.enforcement_recorded",
            record_id=record.id,
            policy_name=policy_name,
            action=action.value,
            category=category.value,
        )
        return record

    def get_enforcement(self, record_id: str) -> EnforcementRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_enforcements(
        self,
        policy_name: str | None = None,
        action: EnforcementAction | None = None,
        limit: int = 50,
    ) -> list[EnforcementRecord]:
        results = list(self._records)
        if policy_name is not None:
            results = [r for r in results if r.policy_name == policy_name]
        if action is not None:
            results = [r for r in results if r.action == action]
        return results[-limit:]

    def add_violation(
        self,
        policy_name: str,
        scope: EnforcementScope = EnforcementScope.SERVICE,
        category: PolicyCategory = PolicyCategory.SECURITY,
        target: str = "",
        violation_count: int = 0,
        details: str = "",
    ) -> EnforcementViolation:
        violation = EnforcementViolation(
            policy_name=policy_name,
            scope=scope,
            category=category,
            target=target,
            violation_count=violation_count,
            details=details,
        )
        self._violations.append(violation)
        if len(self._violations) > self._max_records:
            self._violations = self._violations[-self._max_records :]
        logger.info(
            "policy_enforcer.violation_added",
            policy_name=policy_name,
            scope=scope.value,
            category=category.value,
        )
        return violation

    # -- domain operations --------------------------------------------

    def analyze_enforcement_by_policy(self, policy_name: str) -> dict[str, Any]:
        """Analyze enforcement activity for a specific policy."""
        records = [r for r in self._records if r.policy_name == policy_name]
        if not records:
            return {"policy_name": policy_name, "status": "no_data"}
        block_count = sum(1 for r in records if r.action == EnforcementAction.BLOCK)
        block_rate = round(block_count / len(records) * 100, 2)
        violations = [v for v in self._violations if v.policy_name == policy_name]
        return {
            "policy_name": policy_name,
            "total_enforcements": len(records),
            "block_count": block_count,
            "block_rate_pct": block_rate,
            "total_violations": len(violations),
            "meets_threshold": block_rate <= self._max_violation_rate_pct,
        }

    def identify_frequent_violations(self) -> list[dict[str, Any]]:
        """Find policies with repeated violations."""
        violation_counts: dict[str, int] = {}
        for v in self._violations:
            violation_counts[v.policy_name] = violation_counts.get(v.policy_name, 0) + 1
        results: list[dict[str, Any]] = []
        for policy, count in violation_counts.items():
            if count > 1:
                results.append(
                    {
                        "policy_name": policy,
                        "violation_count": count,
                    }
                )
        results.sort(key=lambda x: x["violation_count"], reverse=True)
        return results

    def rank_by_violation_count(self) -> list[dict[str, Any]]:
        """Rank policies by total enforcement count descending."""
        freq: dict[str, int] = {}
        for r in self._records:
            freq[r.policy_name] = freq.get(r.policy_name, 0) + 1
        results: list[dict[str, Any]] = []
        for policy, count in freq.items():
            results.append(
                {
                    "policy_name": policy,
                    "enforcement_count": count,
                }
            )
        results.sort(key=lambda x: x["enforcement_count"], reverse=True)
        return results

    def detect_enforcement_trends(self) -> list[dict[str, Any]]:
        """Detect policies with >3 BLOCK enforcement actions."""
        block_counts: dict[str, int] = {}
        for r in self._records:
            if r.action == EnforcementAction.BLOCK:
                block_counts[r.policy_name] = block_counts.get(r.policy_name, 0) + 1
        results: list[dict[str, Any]] = []
        for policy, count in block_counts.items():
            if count > 3:
                results.append(
                    {
                        "policy_name": policy,
                        "block_count": count,
                        "trend_detected": True,
                    }
                )
        results.sort(key=lambda x: x["block_count"], reverse=True)
        return results

    # -- report / stats -----------------------------------------------

    def generate_report(self) -> PolicyEnforcerReport:
        by_action: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_action[r.action.value] = by_action.get(r.action.value, 0) + 1
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
        total = len(self._records)
        block_count = sum(1 for r in self._records if r.action == EnforcementAction.BLOCK)
        violation_rate = round(block_count / total * 100, 2) if total else 0.0
        frequent = sum(1 for _ in self.identify_frequent_violations())
        recs: list[str] = []
        if violation_rate > self._max_violation_rate_pct:
            recs.append(
                f"Violation rate {violation_rate}% exceeds "
                f"{self._max_violation_rate_pct}% threshold"
            )
        if frequent > 0:
            recs.append(f"{frequent} policy/policies with frequent violations")
        trends = len(self.detect_enforcement_trends())
        if trends > 0:
            recs.append(f"{trends} policy/policies detected with enforcement trends")
        if not recs:
            recs.append("Policy enforcement within acceptable limits")
        return PolicyEnforcerReport(
            total_enforcements=total,
            total_violations=len(self._violations),
            violation_rate_pct=violation_rate,
            by_action=by_action,
            by_category=by_category,
            frequent_violation_count=frequent,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._violations.clear()
        logger.info("policy_enforcer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        action_dist: dict[str, int] = {}
        for r in self._records:
            key = r.action.value
            action_dist[key] = action_dist.get(key, 0) + 1
        return {
            "total_enforcements": len(self._records),
            "total_violations": len(self._violations),
            "max_violation_rate_pct": self._max_violation_rate_pct,
            "action_distribution": action_dist,
            "unique_policies": len({r.policy_name for r in self._records}),
        }
