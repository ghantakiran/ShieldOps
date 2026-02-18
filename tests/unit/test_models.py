"""Unit tests for core data models."""

from datetime import UTC, datetime

from shieldops.models.base import (
    AlertContext,
    Environment,
    HealthStatus,
    Hypothesis,
    RemediationAction,
    Resource,
    RiskLevel,
)


class TestResource:
    def test_create_resource(self):
        resource = Resource(
            id="default/api-server",
            name="api-server",
            resource_type="pod",
            environment=Environment.PRODUCTION,
            provider="kubernetes",
            namespace="default",
            labels={"app": "api"},
        )
        assert resource.id == "default/api-server"
        assert resource.provider == "kubernetes"
        assert resource.environment == Environment.PRODUCTION

    def test_resource_defaults(self):
        resource = Resource(
            id="i-123",
            name="web-server",
            resource_type="instance",
            environment=Environment.DEVELOPMENT,
            provider="aws",
        )
        assert resource.namespace is None
        assert resource.labels == {}
        assert resource.metadata == {}


class TestHealthStatus:
    def test_healthy_resource(self):
        status = HealthStatus(
            resource_id="default/api-server",
            healthy=True,
            status="Running",
            last_checked=datetime.now(UTC),
        )
        assert status.healthy is True

    def test_unhealthy_resource(self):
        status = HealthStatus(
            resource_id="default/api-server",
            healthy=False,
            status="CrashLoopBackOff",
            message="Container restarting repeatedly",
            last_checked=datetime.now(UTC),
            metrics={"restart_count": 15.0},
        )
        assert status.healthy is False
        assert status.metrics["restart_count"] == 15.0


class TestHypothesis:
    def test_hypothesis_confidence_bounds(self):
        h = Hypothesis(
            id="h-1",
            description="OOM kill due to memory leak",
            confidence=0.92,
            evidence=["Container exit code 137", "Memory usage 98%"],
            affected_resources=["default/api-server"],
            reasoning_chain=["Checked logs", "Analyzed metrics"],
        )
        assert 0.0 <= h.confidence <= 1.0
        assert len(h.evidence) == 2


class TestRemediationAction:
    def test_create_action(self):
        action = RemediationAction(
            id="action-1",
            action_type="restart_pod",
            target_resource="default/api-server",
            environment=Environment.DEVELOPMENT,
            risk_level=RiskLevel.LOW,
            description="Restart crash-looping pod",
        )
        assert action.risk_level == RiskLevel.LOW
        assert action.rollback_capable is True


class TestAlertContext:
    def test_create_alert(self):
        alert = AlertContext(
            alert_id="alert-123",
            alert_name="KubePodCrashLooping",
            severity="critical",
            source="prometheus",
            resource_id="default/api-server",
            triggered_at=datetime.now(UTC),
            description="Pod has restarted 15 times in the last hour",
        )
        assert alert.severity == "critical"
        assert alert.source == "prometheus"
