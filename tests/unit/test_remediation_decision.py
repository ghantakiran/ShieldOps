"""Tests for shieldops.operations.remediation_decision — AutoRemediationDecisionEngine."""

from __future__ import annotations

from shieldops.operations.remediation_decision import (
    AutoRemediationDecisionEngine,
    DecisionOutcome,
    DecisionPolicy,
    RemediationDecision,
    RemediationDecisionReport,
    RemediationType,
    RiskLevel,
)


def _engine(**kw) -> AutoRemediationDecisionEngine:
    return AutoRemediationDecisionEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # DecisionOutcome (5)
    def test_outcome_auto_execute(self):
        assert DecisionOutcome.AUTO_EXECUTE == "auto_execute"

    def test_outcome_require_approval(self):
        assert DecisionOutcome.REQUIRE_APPROVAL == "require_approval"

    def test_outcome_defer(self):
        assert DecisionOutcome.DEFER == "defer"

    def test_outcome_escalate(self):
        assert DecisionOutcome.ESCALATE == "escalate"

    def test_outcome_block(self):
        assert DecisionOutcome.BLOCK == "block"

    # RiskLevel (5)
    def test_risk_minimal(self):
        assert RiskLevel.MINIMAL == "minimal"

    def test_risk_low(self):
        assert RiskLevel.LOW == "low"

    def test_risk_moderate(self):
        assert RiskLevel.MODERATE == "moderate"

    def test_risk_high(self):
        assert RiskLevel.HIGH == "high"

    def test_risk_extreme(self):
        assert RiskLevel.EXTREME == "extreme"

    # RemediationType (5)
    def test_type_restart(self):
        assert RemediationType.RESTART == "restart"

    def test_type_scale(self):
        assert RemediationType.SCALE == "scale"

    def test_type_rollback(self):
        assert RemediationType.ROLLBACK == "rollback"

    def test_type_failover(self):
        assert RemediationType.FAILOVER == "failover"

    def test_type_patch(self):
        assert RemediationType.PATCH == "patch"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_decision_policy_defaults(self):
        p = DecisionPolicy()
        assert p.id
        assert p.name == ""
        assert p.environment == "production"
        assert p.max_risk_score == 0.8
        assert p.allowed_types == []
        assert p.require_approval_above == 0.5
        assert p.block_above == 0.9
        assert p.created_at > 0

    def test_remediation_decision_defaults(self):
        d = RemediationDecision()
        assert d.id
        assert d.service == ""
        assert d.remediation_type == RemediationType.RESTART
        assert d.risk_score == 0.0
        assert d.risk_level == RiskLevel.MINIMAL
        assert d.outcome == DecisionOutcome.DEFER
        assert d.policy_id == ""
        assert d.rationale == ""
        assert d.created_at > 0

    def test_remediation_decision_report_defaults(self):
        r = RemediationDecisionReport()
        assert r.total_policies == 0
        assert r.total_decisions == 0
        assert r.by_outcome == {}
        assert r.by_risk_level == {}
        assert r.auto_execute_rate_pct == 0.0
        assert r.block_rate_pct == 0.0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# register_policy
# ---------------------------------------------------------------------------


class TestRegisterPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.register_policy(name="prod-default")
        assert p.name == "prod-default"
        assert p.environment == "production"
        assert p.max_risk_score == 0.8

    def test_with_params(self):
        eng = _engine()
        p = eng.register_policy(
            name="staging-policy",
            environment="staging",
            max_risk_score=0.6,
            allowed_types=["restart", "scale"],
            require_approval_above=0.4,
            block_above=0.85,
        )
        assert p.environment == "staging"
        assert p.max_risk_score == 0.6
        assert p.allowed_types == ["restart", "scale"]
        assert p.require_approval_above == 0.4
        assert p.block_above == 0.85

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.register_policy(name=f"policy-{i}")
        assert len(eng._policies) == 3


# ---------------------------------------------------------------------------
# get_policy
# ---------------------------------------------------------------------------


class TestGetPolicy:
    def test_found(self):
        eng = _engine()
        p = eng.register_policy(name="prod-default")
        result = eng.get_policy(p.id)
        assert result is not None
        assert result.name == "prod-default"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_policy("nonexistent") is None


# ---------------------------------------------------------------------------
# list_policies
# ---------------------------------------------------------------------------


class TestListPolicies:
    def test_list_all(self):
        eng = _engine()
        eng.register_policy(name="prod-default")
        eng.register_policy(name="staging-policy", environment="staging")
        assert len(eng.list_policies()) == 2

    def test_filter_by_environment(self):
        eng = _engine()
        eng.register_policy(name="prod-default", environment="production")
        eng.register_policy(name="staging-policy", environment="staging")
        results = eng.list_policies(environment="staging")
        assert len(results) == 1
        assert results[0].environment == "staging"

    def test_respects_limit(self):
        eng = _engine()
        for i in range(10):
            eng.register_policy(name=f"policy-{i}")
        results = eng.list_policies(limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# evaluate_decision
# ---------------------------------------------------------------------------


class TestEvaluateDecision:
    def test_low_risk_auto_execute(self):
        eng = _engine()
        d = eng.evaluate_decision(
            service="api-gw",
            remediation_type=RemediationType.RESTART,
            risk_score=0.1,
        )
        assert d.outcome == DecisionOutcome.AUTO_EXECUTE
        assert d.risk_level == RiskLevel.MINIMAL
        assert d.service == "api-gw"

    def test_high_risk_escalate_no_policy(self):
        eng = _engine()
        d = eng.evaluate_decision(
            service="api-gw",
            remediation_type=RemediationType.FAILOVER,
            risk_score=0.7,
        )
        assert d.outcome == DecisionOutcome.ESCALATE
        assert d.risk_level == RiskLevel.HIGH

    def test_policy_blocks_disallowed_type(self):
        eng = _engine()
        p = eng.register_policy(
            name="restricted",
            allowed_types=["restart", "scale"],
        )
        d = eng.evaluate_decision(
            service="api-gw",
            remediation_type=RemediationType.ROLLBACK,
            risk_score=0.3,
            policy_id=p.id,
        )
        assert d.outcome == DecisionOutcome.BLOCK
        assert "not allowed" in d.rationale


# ---------------------------------------------------------------------------
# get_decision
# ---------------------------------------------------------------------------


class TestGetDecision:
    def test_found(self):
        eng = _engine()
        d = eng.evaluate_decision(
            service="api-gw",
            remediation_type=RemediationType.RESTART,
            risk_score=0.1,
        )
        result = eng.get_decision(d.id)
        assert result is not None
        assert result.service == "api-gw"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_decision("nonexistent") is None


# ---------------------------------------------------------------------------
# list_decisions
# ---------------------------------------------------------------------------


class TestListDecisions:
    def test_list_all(self):
        eng = _engine()
        eng.evaluate_decision(
            service="api-gw", remediation_type=RemediationType.RESTART, risk_score=0.1
        )
        eng.evaluate_decision(
            service="payment-svc", remediation_type=RemediationType.SCALE, risk_score=0.4
        )
        assert len(eng.list_decisions()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.evaluate_decision(
            service="api-gw", remediation_type=RemediationType.RESTART, risk_score=0.1
        )
        eng.evaluate_decision(
            service="payment-svc", remediation_type=RemediationType.SCALE, risk_score=0.4
        )
        results = eng.list_decisions(service="api-gw")
        assert len(results) == 1
        assert results[0].service == "api-gw"

    def test_filter_by_outcome(self):
        eng = _engine()
        eng.evaluate_decision(
            service="api-gw", remediation_type=RemediationType.RESTART, risk_score=0.1
        )
        eng.evaluate_decision(
            service="payment-svc", remediation_type=RemediationType.FAILOVER, risk_score=0.7
        )
        results = eng.list_decisions(outcome=DecisionOutcome.AUTO_EXECUTE)
        assert len(results) == 1
        assert results[0].outcome == DecisionOutcome.AUTO_EXECUTE


# ---------------------------------------------------------------------------
# calculate_risk_score
# ---------------------------------------------------------------------------


class TestCalculateRiskScore:
    def test_restart_production(self):
        eng = _engine()
        result = eng.calculate_risk_score(
            service="api-gw",
            remediation_type=RemediationType.RESTART,
            environment="production",
            blast_radius=1,
        )
        # base=0.2, env_mult=1.5, blast_adj=0.01 -> 0.2*1.5+0.01=0.31
        assert result["risk_score"] == 0.31
        assert result["risk_level"] == "low"
        assert result["service"] == "api-gw"

    def test_patch_staging(self):
        eng = _engine()
        result = eng.calculate_risk_score(
            service="api-gw",
            remediation_type=RemediationType.PATCH,
            environment="staging",
            blast_radius=10,
        )
        # base=0.7, env_mult=1.0, blast_adj=0.1 -> 0.7*1.0+0.1=0.8
        assert result["risk_score"] == 0.8
        assert result["risk_level"] == "extreme"

    def test_high_blast_radius_capped(self):
        eng = _engine()
        result = eng.calculate_risk_score(
            service="api-gw",
            remediation_type=RemediationType.RESTART,
            environment="development",
            blast_radius=500,
        )
        # base=0.2, env_mult=0.5, blast_adj=min(0.3,5.0)=0.3 -> 0.2*0.5+0.3=0.4
        assert result["risk_score"] == 0.4
        assert result["risk_level"] == "moderate"


# ---------------------------------------------------------------------------
# get_decision_trends
# ---------------------------------------------------------------------------


class TestGetDecisionTrends:
    def test_with_decisions(self):
        eng = _engine()
        eng.evaluate_decision(
            service="api-gw", remediation_type=RemediationType.RESTART, risk_score=0.1
        )
        eng.evaluate_decision(
            service="payment-svc", remediation_type=RemediationType.SCALE, risk_score=0.4
        )
        trends = eng.get_decision_trends()
        assert trends["total_decisions"] == 2
        assert len(trends["by_outcome"]) > 0
        assert len(trends["by_remediation_type"]) == 2

    def test_empty(self):
        eng = _engine()
        trends = eng.get_decision_trends()
        assert trends["total_decisions"] == 0
        assert trends["by_outcome"] == {}
        assert trends["by_remediation_type"] == {}


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.register_policy(name="prod-default")
        eng.evaluate_decision(
            service="api-gw",
            remediation_type=RemediationType.RESTART,
            risk_score=0.1,
        )
        eng.evaluate_decision(
            service="payment-svc",
            remediation_type=RemediationType.FAILOVER,
            risk_score=0.7,
        )
        report = eng.generate_report()
        assert isinstance(report, RemediationDecisionReport)
        assert report.total_policies == 1
        assert report.total_decisions == 2
        assert len(report.by_outcome) > 0
        assert len(report.by_risk_level) > 0
        assert report.auto_execute_rate_pct > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_policies == 0
        assert report.total_decisions == 0
        assert "Remediation decisions within normal parameters" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.register_policy(name="prod-default")
        eng.evaluate_decision(
            service="api-gw",
            remediation_type=RemediationType.RESTART,
            risk_score=0.1,
        )
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._policies) == 0
        assert len(eng._decisions) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_policies"] == 0
        assert stats["total_decisions"] == 0
        assert stats["outcome_distribution"] == {}
        assert stats["unique_services"] == 0

    def test_populated(self):
        eng = _engine()
        eng.register_policy(name="prod-default")
        eng.evaluate_decision(
            service="api-gw",
            remediation_type=RemediationType.RESTART,
            risk_score=0.1,
        )
        stats = eng.get_stats()
        assert stats["total_policies"] == 1
        assert stats["total_decisions"] == 1
        assert stats["max_risk_score"] == 0.8
        assert stats["unique_services"] == 1
        assert len(stats["outcome_distribution"]) > 0
