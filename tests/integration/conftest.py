"""Integration test fixtures — shared across all e2e tests.

Provides mock connectors, observability sources, policy engine,
approval workflow, and LLM patches for end-to-end agent testing.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import (
    ActionResult,
    AlertContext,
    Environment,
    ExecutionStatus,
    HealthStatus,
    RemediationAction,
    RiskLevel,
    Snapshot,
)
from shieldops.policy.approval.workflow import ApprovalWorkflow
from shieldops.policy.opa.client import PolicyDecision

# ── Mock Connector ────────────────────────────────────────────────


@pytest.fixture
def mock_connector():
    """A fully mocked infrastructure connector."""
    connector = AsyncMock()
    # Method names must match what toolkits actually call
    connector.get_health.return_value = HealthStatus(
        resource_id="default/api-server",
        healthy=True,
        status="running",
        last_checked=datetime.now(UTC),
    )
    connector.execute_action.return_value = ActionResult(
        action_id="exec-001",
        status=ExecutionStatus.SUCCESS,
        message="Pod restarted successfully",
        started_at=datetime.now(UTC),
    )
    connector.create_snapshot.return_value = Snapshot(
        id="snap-001",
        resource_id="default/api-server",
        snapshot_type="deployment",
        state={"replicas": 2, "image": "api:v1.2.3"},
        created_at=datetime.now(UTC),
    )
    connector.get_events.return_value = []
    connector.rollback.return_value = ActionResult(
        action_id="rollback-001",
        status=ExecutionStatus.SUCCESS,
        message="Rollback completed",
        started_at=datetime.now(UTC),
    )
    return connector


@pytest.fixture
def mock_connector_router(mock_connector):
    """ConnectorRouter that returns mock connector for all providers."""
    router = MagicMock(spec=ConnectorRouter)
    router.get.return_value = mock_connector
    router.providers = ["kubernetes", "aws", "gcp", "azure", "linux"]
    return router


# ── Mock Observability Sources ────────────────────────────────────


@pytest.fixture
def mock_log_source():
    source = AsyncMock()
    source.source_name = "test-logs"
    source.query_logs.return_value = [
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": "error",
            "message": "OOMKilled: container exceeded 512Mi limit",
        },
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": "error",
            "message": "Container exit code 137",
        },
    ]
    source.search_patterns.return_value = {}
    return source


@pytest.fixture
def mock_metric_source():
    source = AsyncMock()
    source.source_name = "test-metrics"
    source.query_instant.return_value = []
    source.detect_anomalies.return_value = []
    return source


@pytest.fixture
def mock_trace_source():
    source = AsyncMock()
    source.source_name = "test-traces"
    source.search_traces.return_value = []
    source.find_bottleneck.return_value = None
    return source


# ── Policy & Approval ────────────────────────────────────────────


@pytest.fixture
def mock_policy_engine():
    engine = AsyncMock()
    engine.evaluate.return_value = PolicyDecision(
        allowed=True,
        reasons=["Action allowed by test policy"],
    )
    # classify_risk is called synchronously — must be a regular MagicMock
    engine.classify_risk = MagicMock(return_value=RiskLevel.MEDIUM)
    engine.close = AsyncMock()
    return engine


@pytest.fixture
def mock_policy_engine_deny():
    """Policy engine that denies all actions."""
    engine = AsyncMock()
    engine.evaluate.return_value = PolicyDecision(
        allowed=False,
        reasons=["Action denied: blast radius exceeded"],
    )
    engine.classify_risk = MagicMock(return_value=RiskLevel.MEDIUM)
    engine.close = AsyncMock()
    return engine


@pytest.fixture
def approval_workflow():
    return ApprovalWorkflow(timeout_seconds=2, escalation_timeout_seconds=3)


@pytest.fixture
def auto_approve_workflow():
    """Workflow that auto-approves within 0.1s."""
    workflow = ApprovalWorkflow(timeout_seconds=5)

    original_request = workflow.request_approval

    async def auto_approve_request(request):
        async def _approve():
            await asyncio.sleep(0.1)
            workflow.approve(request.request_id, "auto-test-approver")

        asyncio.create_task(_approve())
        return await original_request(request)

    workflow.request_approval = auto_approve_request
    return workflow


# ── Alert Contexts ───────────────────────────────────────────────


@pytest.fixture
def crash_loop_alert():
    return AlertContext(
        alert_id="alert-e2e-001",
        alert_name="KubePodCrashLooping",
        severity="critical",
        source="prometheus",
        resource_id="default/api-server",
        labels={"app": "api", "environment": "production"},
        triggered_at=datetime.now(UTC),
        description="Pod api-server has restarted 15 times in the last hour",
    )


@pytest.fixture
def high_cpu_alert():
    return AlertContext(
        alert_id="alert-e2e-002",
        alert_name="HighCPUUsage",
        severity="warning",
        source="prometheus",
        resource_id="default/worker-pool",
        labels={"app": "worker", "environment": "production"},
        triggered_at=datetime.now(UTC),
        description="CPU usage above 95% for 10 minutes",
    )


# ── Remediation Actions ──────────────────────────────────────────


@pytest.fixture
def restart_pod_action():
    return RemediationAction(
        id="act-e2e-001",
        action_type="restart_pod",
        target_resource="default/api-server",
        environment=Environment.PRODUCTION,
        risk_level=RiskLevel.MEDIUM,
        parameters={"grace_period": 30},
        description="Restart crash-looping pod",
    )


@pytest.fixture
def high_risk_action():
    return RemediationAction(
        id="act-e2e-002",
        action_type="rollback_deployment",
        target_resource="default/api-server",
        environment=Environment.PRODUCTION,
        risk_level=RiskLevel.HIGH,
        parameters={"revision": 3},
        description="Rollback deployment to previous revision",
    )


@pytest.fixture
def critical_action():
    return RemediationAction(
        id="act-e2e-003",
        action_type="scale_cluster",
        target_resource="production/main-cluster",
        environment=Environment.PRODUCTION,
        risk_level=RiskLevel.CRITICAL,
        parameters={"replicas": 10},
        description="Scale production cluster",
    )
