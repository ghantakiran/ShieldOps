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


# ── Security Agent Fixtures ──────────────────────────────────────


@pytest.fixture
def mock_cve_source():
    """Mock CVE source that returns test vulnerability findings."""
    source = AsyncMock()
    source.source_name = "test-nvd"
    source.scan.return_value = [
        {
            "cve_id": "CVE-2024-1234",
            "severity": "critical",
            "cvss_score": 9.8,
            "package_name": "openssl",
            "installed_version": "1.1.1",
            "fixed_version": "1.1.1w",
            "affected_resource": "default/api-server",
            "description": "Buffer overflow in OpenSSL",
        },
        {
            "cve_id": "CVE-2024-5678",
            "severity": "high",
            "cvss_score": 7.5,
            "package_name": "curl",
            "installed_version": "7.80.0",
            "fixed_version": "7.88.0",
            "affected_resource": "default/api-server",
            "description": "HTTP/2 header injection",
        },
        {
            "cve_id": "CVE-2024-9999",
            "severity": "medium",
            "cvss_score": 5.0,
            "package_name": "zlib",
            "installed_version": "1.2.11",
            "fixed_version": None,
            "affected_resource": "default/api-server",
            "description": "Memory corruption (no fix yet)",
        },
    ]
    return source


@pytest.fixture
def mock_credential_store():
    """Mock credential store with credentials needing rotation."""
    from datetime import timedelta

    store = AsyncMock()
    store.store_name = "test-vault"
    now = datetime.now(UTC)
    store.list_credentials.return_value = [
        {
            "credential_id": "db-prod-password",
            "credential_type": "database_password",
            "service": "postgres-main",
            "expires_at": now - timedelta(days=1),  # expired
            "last_rotated": now - timedelta(days=91),
        },
        {
            "credential_id": "api-key-stripe",
            "credential_type": "api_key",
            "service": "stripe",
            "expires_at": now + timedelta(days=3),  # expiring soon
            "last_rotated": now - timedelta(days=60),
        },
        {
            "credential_id": "tls-cert-main",
            "credential_type": "tls_certificate",
            "service": "nginx-ingress",
            "expires_at": now + timedelta(days=90),  # healthy
            "last_rotated": now - timedelta(days=30),
        },
    ]
    store.rotate_credential.return_value = {
        "credential_id": "rotated",
        "credential_type": "database_password",
        "service": "postgres-main",
        "success": True,
        "message": "Credential rotated successfully",
        "new_expiry": now + timedelta(days=90),
    }
    return store


@pytest.fixture
def security_llm_responses():
    """Deterministic LLM responses for security agent integration tests."""
    from shieldops.agents.security.prompts import (
        ComplianceAssessmentResult,
        CredentialAssessmentResult,
        SecurityPostureResult,
        VulnerabilityAssessmentResult,
    )

    return {
        VulnerabilityAssessmentResult: VulnerabilityAssessmentResult(
            summary="Critical OpenSSL vulnerability found",
            risk_level="critical",
            top_risks=["CVE-2024-1234: OpenSSL buffer overflow"],
            patch_priority=["CVE-2024-1234", "CVE-2024-5678"],
            recommended_actions=["Patch OpenSSL immediately", "Update curl"],
        ),
        CredentialAssessmentResult: CredentialAssessmentResult(
            summary="1 expired credential, 1 expiring within 7 days",
            urgent_rotations=["db-prod-password"],
            rotation_plan=["db-prod-password", "api-key-stripe"],
            risks=["Expired DB credential could cause auth failures"],
        ),
        ComplianceAssessmentResult: ComplianceAssessmentResult(
            summary="All SOC2 controls passing",
            overall_score=100.0,
            failing_controls=[],
            auto_remediable=[],
            manual_review_needed=[],
        ),
        SecurityPostureResult: SecurityPostureResult(
            overall_score=45.0,
            summary="Poor posture: critical CVEs and expired credentials",
            top_risks=[
                "CVE-2024-1234 on production",
                "Expired database credential",
            ],
            recommended_actions=["Patch OpenSSL", "Rotate DB password"],
        ),
    }
