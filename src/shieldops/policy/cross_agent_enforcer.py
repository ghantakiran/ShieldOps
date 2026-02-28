"""Cross-Agent Policy Enforcer — enforce policies across multi-agent operations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PolicyScope(StrEnum):
    SINGLE_AGENT = "single_agent"
    TEAM = "team"
    SWARM = "swarm"
    GLOBAL = "global"
    ENVIRONMENT = "environment"


class EnforcementAction(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    RATE_LIMIT = "rate_limit"
    QUARANTINE = "quarantine"


class ViolationType(StrEnum):
    RESOURCE_CONFLICT = "resource_conflict"
    SCOPE_EXCEEDED = "scope_exceeded"
    RATE_EXCEEDED = "rate_exceeded"
    UNAUTHORIZED_ACTION = "unauthorized_action"
    POLICY_BYPASS = "policy_bypass"


# --- Models ---


class EnforcementRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    policy_scope: PolicyScope = PolicyScope.SINGLE_AGENT
    enforcement_action: EnforcementAction = EnforcementAction.ALLOW
    violation_type: ViolationType = ViolationType.RESOURCE_CONFLICT
    severity_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    policy_scope: PolicyScope = PolicyScope.GLOBAL
    enforcement_action: EnforcementAction = EnforcementAction.DENY
    max_violations: int = 0
    created_at: float = Field(default_factory=time.time)


class PolicyEnforcerReport(BaseModel):
    total_enforcements: int = 0
    total_rules: int = 0
    compliance_rate_pct: float = 0.0
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    violation_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CrossAgentPolicyEnforcer:
    """Enforce policies across multi-agent operations."""

    def __init__(
        self,
        max_records: int = 200000,
        max_violations_per_agent: int = 10,
    ) -> None:
        self._max_records = max_records
        self._max_violations_per_agent = max_violations_per_agent
        self._records: list[EnforcementRecord] = []
        self._rules: list[PolicyRule] = []
        logger.info(
            "cross_agent_enforcer.initialized",
            max_records=max_records,
            max_violations_per_agent=max_violations_per_agent,
        )

    # -- record / get / list ---------------------------------------------

    def record_enforcement(
        self,
        agent_name: str,
        policy_scope: PolicyScope = PolicyScope.SINGLE_AGENT,
        enforcement_action: EnforcementAction = EnforcementAction.ALLOW,
        violation_type: ViolationType = ViolationType.RESOURCE_CONFLICT,
        severity_score: float = 0.0,
        details: str = "",
    ) -> EnforcementRecord:
        record = EnforcementRecord(
            agent_name=agent_name,
            policy_scope=policy_scope,
            enforcement_action=enforcement_action,
            violation_type=violation_type,
            severity_score=severity_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cross_agent_enforcer.recorded",
            record_id=record.id,
            agent_name=agent_name,
            policy_scope=policy_scope.value,
            enforcement_action=enforcement_action.value,
        )
        return record

    def get_enforcement(self, record_id: str) -> EnforcementRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_enforcements(
        self,
        agent_name: str | None = None,
        policy_scope: PolicyScope | None = None,
        limit: int = 50,
    ) -> list[EnforcementRecord]:
        results = list(self._records)
        if agent_name is not None:
            results = [r for r in results if r.agent_name == agent_name]
        if policy_scope is not None:
            results = [r for r in results if r.policy_scope == policy_scope]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        policy_scope: PolicyScope = PolicyScope.GLOBAL,
        enforcement_action: EnforcementAction = EnforcementAction.DENY,
        max_violations: int = 0,
    ) -> PolicyRule:
        rule = PolicyRule(
            rule_name=rule_name,
            policy_scope=policy_scope,
            enforcement_action=enforcement_action,
            max_violations=max_violations,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "cross_agent_enforcer.rule_added",
            rule_name=rule_name,
            policy_scope=policy_scope.value,
            enforcement_action=enforcement_action.value,
        )
        return rule

    # -- domain operations -----------------------------------------------

    def analyze_agent_compliance(self, agent_name: str) -> dict[str, Any]:
        agent_records = [r for r in self._records if r.agent_name == agent_name]
        if not agent_records:
            return {"agent_name": agent_name, "status": "no_data"}
        violations = sum(
            1
            for r in agent_records
            if r.enforcement_action in (EnforcementAction.DENY, EnforcementAction.QUARANTINE)
        )
        compliance_rate = round((1 - violations / len(agent_records)) * 100, 2)
        return {
            "agent_name": agent_name,
            "total_records": len(agent_records),
            "violation_count": violations,
            "compliance_rate_pct": compliance_rate,
            "meets_threshold": violations <= self._max_violations_per_agent,
        }

    def identify_repeat_violators(self) -> list[dict[str, Any]]:
        agent_counts: dict[str, int] = {}
        for r in self._records:
            if r.enforcement_action in (EnforcementAction.DENY, EnforcementAction.QUARANTINE):
                agent_counts[r.agent_name] = agent_counts.get(r.agent_name, 0) + 1
        results: list[dict[str, Any]] = []
        for agent, count in agent_counts.items():
            if count > 1:
                results.append({"agent_name": agent, "violation_count": count})
        results.sort(key=lambda x: x["violation_count"], reverse=True)
        return results

    def rank_by_violation_count(self) -> list[dict[str, Any]]:
        agent_scores: dict[str, list[float]] = {}
        for r in self._records:
            agent_scores.setdefault(r.agent_name, []).append(r.severity_score)
        results: list[dict[str, Any]] = []
        for agent, scores in agent_scores.items():
            results.append(
                {
                    "agent_name": agent,
                    "avg_severity_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_severity_score"], reverse=True)
        return results

    def detect_policy_bypass_attempts(self) -> list[dict[str, Any]]:
        agent_counts: dict[str, int] = {}
        for r in self._records:
            if r.violation_type == ViolationType.POLICY_BYPASS:
                agent_counts[r.agent_name] = agent_counts.get(r.agent_name, 0) + 1
        results: list[dict[str, Any]] = []
        for agent, count in agent_counts.items():
            if count > 3:
                results.append(
                    {
                        "agent_name": agent,
                        "bypass_count": count,
                        "recurring": True,
                    }
                )
        results.sort(key=lambda x: x["bypass_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> PolicyEnforcerReport:
        by_scope: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_scope[r.policy_scope.value] = by_scope.get(r.policy_scope.value, 0) + 1
            by_action[r.enforcement_action.value] = by_action.get(r.enforcement_action.value, 0) + 1
        violations = sum(
            1
            for r in self._records
            if r.enforcement_action in (EnforcementAction.DENY, EnforcementAction.QUARANTINE)
        )
        compliance_rate = (
            round((1 - violations / len(self._records)) * 100, 2) if self._records else 0.0
        )
        recs: list[str] = []
        if violations > 0:
            recs.append(f"{violations} policy violation(s) detected")
        bypass_count = len(self.detect_policy_bypass_attempts())
        if bypass_count > 0:
            recs.append(f"{bypass_count} agent(s) with recurring policy bypass attempts")
        if not recs:
            recs.append("Cross-agent policy compliance meets targets")
        return PolicyEnforcerReport(
            total_enforcements=len(self._records),
            total_rules=len(self._rules),
            compliance_rate_pct=compliance_rate,
            by_scope=by_scope,
            by_action=by_action,
            violation_count=violations,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("cross_agent_enforcer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        scope_dist: dict[str, int] = {}
        for r in self._records:
            key = r.policy_scope.value
            scope_dist[key] = scope_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "max_violations_per_agent": self._max_violations_per_agent,
            "scope_distribution": scope_dist,
            "unique_agents": len({r.agent_name for r in self._records}),
        }
