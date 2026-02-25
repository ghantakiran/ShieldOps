"""Auto-Remediation Decision Engine — evaluate whether auto-remediation should execute."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DecisionOutcome(StrEnum):
    AUTO_EXECUTE = "auto_execute"
    REQUIRE_APPROVAL = "require_approval"
    DEFER = "defer"
    ESCALATE = "escalate"
    BLOCK = "block"


class RiskLevel(StrEnum):
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


class RemediationType(StrEnum):
    RESTART = "restart"
    SCALE = "scale"
    ROLLBACK = "rollback"
    FAILOVER = "failover"
    PATCH = "patch"


# --- Models ---


class DecisionPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    environment: str = "production"
    max_risk_score: float = 0.8
    allowed_types: list[str] = Field(default_factory=list)
    require_approval_above: float = 0.5
    block_above: float = 0.9
    created_at: float = Field(default_factory=time.time)


class RemediationDecision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    remediation_type: RemediationType = RemediationType.RESTART
    risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.MINIMAL
    outcome: DecisionOutcome = DecisionOutcome.DEFER
    policy_id: str = ""
    rationale: str = ""
    created_at: float = Field(default_factory=time.time)


class RemediationDecisionReport(BaseModel):
    total_policies: int = 0
    total_decisions: int = 0
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    auto_execute_rate_pct: float = 0.0
    block_rate_pct: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutoRemediationDecisionEngine:
    """Evaluate whether auto-remediation should execute, defer, or escalate."""

    def __init__(
        self,
        max_records: int = 200000,
        max_risk_score: float = 0.8,
    ) -> None:
        self._max_records = max_records
        self._max_risk_score = max_risk_score
        self._policies: list[DecisionPolicy] = []
        self._decisions: list[RemediationDecision] = []
        logger.info(
            "remediation_decision.initialized",
            max_records=max_records,
            max_risk_score=max_risk_score,
        )

    # -- internal helpers ------------------------------------------------

    def _score_to_risk_level(self, score: float) -> RiskLevel:
        if score < 0.2:
            return RiskLevel.MINIMAL
        if score < 0.4:
            return RiskLevel.LOW
        if score < 0.6:
            return RiskLevel.MODERATE
        if score < 0.8:
            return RiskLevel.HIGH
        return RiskLevel.EXTREME

    def _determine_outcome(
        self, risk_score: float, policy: DecisionPolicy | None
    ) -> DecisionOutcome:
        if policy is None:
            if risk_score < 0.3:
                return DecisionOutcome.AUTO_EXECUTE
            if risk_score < 0.6:
                return DecisionOutcome.REQUIRE_APPROVAL
            return DecisionOutcome.ESCALATE
        if risk_score >= policy.block_above:
            return DecisionOutcome.BLOCK
        if risk_score >= policy.require_approval_above:
            return DecisionOutcome.REQUIRE_APPROVAL
        if risk_score < 0.3:
            return DecisionOutcome.AUTO_EXECUTE
        return DecisionOutcome.DEFER

    # -- register / get / list policies -----------------------------------

    def register_policy(
        self,
        name: str,
        environment: str = "production",
        max_risk_score: float = 0.8,
        allowed_types: list[str] | None = None,
        require_approval_above: float = 0.5,
        block_above: float = 0.9,
    ) -> DecisionPolicy:
        policy = DecisionPolicy(
            name=name,
            environment=environment,
            max_risk_score=max_risk_score,
            allowed_types=allowed_types or [],
            require_approval_above=require_approval_above,
            block_above=block_above,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "remediation_decision.policy_registered",
            policy_id=policy.id,
            name=name,
            environment=environment,
        )
        return policy

    def get_policy(self, policy_id: str) -> DecisionPolicy | None:
        for p in self._policies:
            if p.id == policy_id:
                return p
        return None

    def list_policies(
        self, environment: str | None = None, limit: int = 50
    ) -> list[DecisionPolicy]:
        results = list(self._policies)
        if environment is not None:
            results = [p for p in results if p.environment == environment]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def evaluate_decision(
        self,
        service: str,
        remediation_type: RemediationType,
        risk_score: float = 0.5,
        policy_id: str = "",
    ) -> RemediationDecision:
        """Evaluate whether a remediation should execute."""
        policy = self.get_policy(policy_id) if policy_id else None
        risk_level = self._score_to_risk_level(risk_score)
        outcome = self._determine_outcome(risk_score, policy)

        # Check if type is allowed by policy
        if policy and policy.allowed_types and remediation_type.value not in policy.allowed_types:
            outcome = DecisionOutcome.BLOCK
            rationale = (
                f"Remediation type '{remediation_type.value}' not allowed by policy '{policy.name}'"
            )
        else:
            rationale = f"Risk score {risk_score} -> {outcome.value}"

        decision = RemediationDecision(
            service=service,
            remediation_type=remediation_type,
            risk_score=risk_score,
            risk_level=risk_level,
            outcome=outcome,
            policy_id=policy_id,
            rationale=rationale,
        )
        self._decisions.append(decision)
        if len(self._decisions) > self._max_records:
            self._decisions = self._decisions[-self._max_records :]
        logger.info(
            "remediation_decision.evaluated",
            decision_id=decision.id,
            service=service,
            outcome=outcome.value,
            risk_score=risk_score,
        )
        return decision

    def get_decision(self, decision_id: str) -> RemediationDecision | None:
        for d in self._decisions:
            if d.id == decision_id:
                return d
        return None

    def list_decisions(
        self,
        service: str | None = None,
        outcome: DecisionOutcome | None = None,
        limit: int = 50,
    ) -> list[RemediationDecision]:
        results = list(self._decisions)
        if service is not None:
            results = [d for d in results if d.service == service]
        if outcome is not None:
            results = [d for d in results if d.outcome == outcome]
        return results[-limit:]

    def calculate_risk_score(
        self,
        service: str,
        remediation_type: RemediationType,
        environment: str = "production",
        blast_radius: int = 1,
    ) -> dict[str, Any]:
        """Calculate a risk score for a proposed remediation."""
        base_scores = {
            RemediationType.RESTART: 0.2,
            RemediationType.SCALE: 0.3,
            RemediationType.ROLLBACK: 0.5,
            RemediationType.FAILOVER: 0.6,
            RemediationType.PATCH: 0.7,
        }
        base = base_scores.get(remediation_type, 0.5)
        env_mult = {"production": 1.5, "staging": 1.0, "development": 0.5}.get(environment, 1.0)
        blast_adj = min(0.3, blast_radius / 100)
        score = round(min(1.0, base * env_mult + blast_adj), 4)
        return {
            "service": service,
            "remediation_type": remediation_type.value,
            "environment": environment,
            "blast_radius": blast_radius,
            "risk_score": score,
            "risk_level": self._score_to_risk_level(score).value,
        }

    def get_decision_trends(self) -> dict[str, Any]:
        """Get trends of decisions over time."""
        by_outcome: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for d in self._decisions:
            by_outcome[d.outcome.value] = by_outcome.get(d.outcome.value, 0) + 1
            by_type[d.remediation_type.value] = by_type.get(d.remediation_type.value, 0) + 1
        return {
            "by_outcome": by_outcome,
            "by_remediation_type": by_type,
            "total_decisions": len(self._decisions),
        }

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> RemediationDecisionReport:
        by_outcome: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for d in self._decisions:
            by_outcome[d.outcome.value] = by_outcome.get(d.outcome.value, 0) + 1
            by_risk[d.risk_level.value] = by_risk.get(d.risk_level.value, 0) + 1
        total = len(self._decisions)
        auto_count = by_outcome.get(DecisionOutcome.AUTO_EXECUTE.value, 0)
        block_count = by_outcome.get(DecisionOutcome.BLOCK.value, 0)
        auto_rate = round(auto_count / total * 100, 2) if total > 0 else 0.0
        block_rate = round(block_count / total * 100, 2) if total > 0 else 0.0
        recs: list[str] = []
        if block_count > 0:
            recs.append(f"{block_count} remediation(s) blocked due to high risk")
        high_risk = by_risk.get(RiskLevel.HIGH.value, 0) + by_risk.get(RiskLevel.EXTREME.value, 0)
        if high_risk > 0:
            recs.append(f"{high_risk} high/extreme risk remediation(s) detected")
        if auto_rate > 80:
            recs.append("High auto-execution rate — verify policy thresholds")
        if not recs:
            recs.append("Remediation decisions within normal parameters")
        return RemediationDecisionReport(
            total_policies=len(self._policies),
            total_decisions=total,
            by_outcome=by_outcome,
            by_risk_level=by_risk,
            auto_execute_rate_pct=auto_rate,
            block_rate_pct=block_rate,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._policies.clear()
        self._decisions.clear()
        logger.info("remediation_decision.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        outcome_dist: dict[str, int] = {}
        for d in self._decisions:
            key = d.outcome.value
            outcome_dist[key] = outcome_dist.get(key, 0) + 1
        return {
            "total_policies": len(self._policies),
            "total_decisions": len(self._decisions),
            "max_risk_score": self._max_risk_score,
            "outcome_distribution": outcome_dist,
            "unique_services": len({d.service for d in self._decisions}),
        }
