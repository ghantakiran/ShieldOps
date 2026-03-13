"""Cost Governance Policy Engine
enforce budget gates, evaluate policy compliance,
detect policy violations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PolicyType(StrEnum):
    BUDGET_GATE = "budget_gate"
    APPROVAL_THRESHOLD = "approval_threshold"
    PROVISIONING_GUARD = "provisioning_guard"
    TAG_ENFORCEMENT = "tag_enforcement"


class ComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"
    EXEMPT = "exempt"


class EnforcementLevel(StrEnum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"
    LOGGING = "logging"
    DISABLED = "disabled"


# --- Models ---


class GovernanceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    policy_type: PolicyType = PolicyType.BUDGET_GATE
    compliance_status: ComplianceStatus = ComplianceStatus.COMPLIANT
    enforcement_level: EnforcementLevel = EnforcementLevel.ADVISORY
    budget_amount: float = 0.0
    actual_amount: float = 0.0
    team_id: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class GovernanceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    policy_type: PolicyType = PolicyType.BUDGET_GATE
    compliance_status: ComplianceStatus = ComplianceStatus.COMPLIANT
    budget_utilization: float = 0.0
    violation_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class GovernanceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_violations: int = 0
    by_policy_type: dict[str, int] = Field(default_factory=dict)
    by_compliance_status: dict[str, int] = Field(default_factory=dict)
    by_enforcement_level: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostGovernancePolicyEngine:
    """Enforce budget gates, evaluate compliance,
    detect policy violations."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[GovernanceRecord] = []
        self._analyses: dict[str, GovernanceAnalysis] = {}
        logger.info(
            "cost_governance_policy.init",
            max_records=max_records,
        )

    def add_record(
        self,
        policy_id: str = "",
        policy_type: PolicyType = (PolicyType.BUDGET_GATE),
        compliance_status: ComplianceStatus = (ComplianceStatus.COMPLIANT),
        enforcement_level: EnforcementLevel = (EnforcementLevel.ADVISORY),
        budget_amount: float = 0.0,
        actual_amount: float = 0.0,
        team_id: str = "",
        description: str = "",
    ) -> GovernanceRecord:
        record = GovernanceRecord(
            policy_id=policy_id,
            policy_type=policy_type,
            compliance_status=compliance_status,
            enforcement_level=enforcement_level,
            budget_amount=budget_amount,
            actual_amount=actual_amount,
            team_id=team_id,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_governance.record_added",
            record_id=record.id,
            policy_id=policy_id,
        )
        return record

    def process(self, key: str) -> GovernanceAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        util = 0.0
        if rec.budget_amount > 0:
            util = round(
                rec.actual_amount / rec.budget_amount * 100,
                2,
            )
        violations = sum(
            1
            for r in self._records
            if r.policy_id == rec.policy_id and r.compliance_status == ComplianceStatus.VIOLATION
        )
        analysis = GovernanceAnalysis(
            policy_id=rec.policy_id,
            policy_type=rec.policy_type,
            compliance_status=rec.compliance_status,
            budget_utilization=util,
            violation_count=violations,
            description=(f"Policy {rec.policy_id} util {util}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> GovernanceReport:
        by_pt: dict[str, int] = {}
        by_cs: dict[str, int] = {}
        by_el: dict[str, int] = {}
        violations = 0
        for r in self._records:
            k = r.policy_type.value
            by_pt[k] = by_pt.get(k, 0) + 1
            k2 = r.compliance_status.value
            by_cs[k2] = by_cs.get(k2, 0) + 1
            k3 = r.enforcement_level.value
            by_el[k3] = by_el.get(k3, 0) + 1
            if r.compliance_status == ComplianceStatus.VIOLATION:
                violations += 1
        recs: list[str] = []
        if violations > 0:
            recs.append(f"{violations} policy violations require attention")
        if not recs:
            recs.append("All policies compliant")
        return GovernanceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_violations=violations,
            by_policy_type=by_pt,
            by_compliance_status=by_cs,
            by_enforcement_level=by_el,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        pt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.policy_type.value
            pt_dist[k] = pt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "policy_type_distribution": pt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("cost_governance_policy.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def enforce_budget_gates(
        self,
    ) -> list[dict[str, Any]]:
        """Enforce budget gates across teams."""
        team_map: dict[str, dict[str, float]] = {}
        for r in self._records:
            if r.team_id not in team_map:
                team_map[r.team_id] = {
                    "budget": 0.0,
                    "actual": 0.0,
                }
            team_map[r.team_id]["budget"] += r.budget_amount
            team_map[r.team_id]["actual"] += r.actual_amount
        results: list[dict[str, Any]] = []
        for tid, vals in team_map.items():
            util = 0.0
            if vals["budget"] > 0:
                util = round(
                    vals["actual"] / vals["budget"] * 100,
                    2,
                )
            blocked = util > 100
            results.append(
                {
                    "team_id": tid,
                    "budget": round(vals["budget"], 2),
                    "actual": round(vals["actual"], 2),
                    "utilization_pct": util,
                    "gate_blocked": blocked,
                }
            )
        results.sort(
            key=lambda x: x["utilization_pct"],
            reverse=True,
        )
        return results

    def evaluate_policy_compliance(
        self,
    ) -> list[dict[str, Any]]:
        """Evaluate compliance per policy."""
        policy_map: dict[str, dict[str, int]] = {}
        for r in self._records:
            if r.policy_id not in policy_map:
                policy_map[r.policy_id] = {}
            s = r.compliance_status.value
            policy_map[r.policy_id][s] = policy_map[r.policy_id].get(s, 0) + 1
        results: list[dict[str, Any]] = []
        for pid, statuses in policy_map.items():
            total = sum(statuses.values())
            compliant = statuses.get("compliant", 0)
            rate = round(compliant / total * 100, 2)
            results.append(
                {
                    "policy_id": pid,
                    "total_checks": total,
                    "compliance_rate": rate,
                    "by_status": statuses,
                }
            )
        results.sort(
            key=lambda x: x["compliance_rate"],
        )
        return results

    def detect_policy_violations(
        self,
    ) -> list[dict[str, Any]]:
        """Detect policy violations."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_status == ComplianceStatus.VIOLATION:
                results.append(
                    {
                        "policy_id": r.policy_id,
                        "team_id": r.team_id,
                        "type": (r.policy_type.value),
                        "enforcement": (r.enforcement_level.value),
                        "overage": round(
                            r.actual_amount - r.budget_amount,
                            2,
                        ),
                    }
                )
        results.sort(
            key=lambda x: x["overage"],
            reverse=True,
        )
        return results
