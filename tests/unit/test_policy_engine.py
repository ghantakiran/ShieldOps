"""Unit tests for the policy engine."""

from shieldops.models.base import Environment, RiskLevel
from shieldops.policy.opa.client import PolicyEngine


class TestRiskClassification:
    def setup_method(self):
        self.engine = PolicyEngine(opa_url="http://localhost:8181")

    def test_destructive_actions_are_critical(self):
        assert self.engine.classify_risk("drain_node", Environment.DEVELOPMENT) == RiskLevel.CRITICAL
        assert self.engine.classify_risk("delete_namespace", Environment.PRODUCTION) == RiskLevel.CRITICAL
        assert self.engine.classify_risk("modify_network_policy", Environment.STAGING) == RiskLevel.CRITICAL

    def test_production_high_impact_actions(self):
        assert self.engine.classify_risk("rollback_deployment", Environment.PRODUCTION) == RiskLevel.HIGH
        assert self.engine.classify_risk("rotate_credentials", Environment.PRODUCTION) == RiskLevel.HIGH

    def test_production_default_is_medium(self):
        assert self.engine.classify_risk("restart_pod", Environment.PRODUCTION) == RiskLevel.MEDIUM

    def test_staging_high_impact_is_medium(self):
        assert self.engine.classify_risk("rollback_deployment", Environment.STAGING) == RiskLevel.MEDIUM

    def test_staging_default_is_low(self):
        assert self.engine.classify_risk("restart_pod", Environment.STAGING) == RiskLevel.LOW

    def test_dev_default_is_low(self):
        assert self.engine.classify_risk("restart_pod", Environment.DEVELOPMENT) == RiskLevel.LOW
        assert self.engine.classify_risk("rollback_deployment", Environment.DEVELOPMENT) == RiskLevel.LOW
