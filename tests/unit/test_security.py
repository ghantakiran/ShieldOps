"""Comprehensive tests for the Security Agent.

Tests cover:
- SecurityToolkit (tools.py)
- Node functions (nodes.py)
- Graph construction and routing (graph.py)
- SecurityRunner (runner.py)
- API endpoints (routes/security.py)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.security.models import (
    CVEFinding,
    ComplianceControl,
    CredentialStatus,
    SecurityPosture,
    SecurityScanState,
    SecurityStep,
)
from shieldops.agents.security.prompts import (
    ComplianceAssessmentResult,
    CredentialAssessmentResult,
    SecurityPostureResult,
    VulnerabilityAssessmentResult,
)
from shieldops.agents.security.tools import SecurityToolkit
from shieldops.models.base import Environment


# --- Fixtures ---


@pytest.fixture
def scan_state():
    return SecurityScanState(
        scan_id="sec-test-001",
        scan_type="full",
        target_resources=["default/api-server"],
        target_environment=Environment.PRODUCTION,
        compliance_frameworks=["soc2"],
    )


@pytest.fixture
def state_with_cves(scan_state):
    """State after vulnerability scanning."""
    scan_state.scan_start = datetime.now(timezone.utc)
    scan_state.cve_findings = [
        CVEFinding(
            cve_id="CVE-2024-1234",
            severity="critical",
            cvss_score=9.8,
            package_name="openssl",
            installed_version="1.1.1",
            fixed_version="1.1.1w",
            affected_resource="default/api-server",
            description="Buffer overflow in OpenSSL",
        ),
        CVEFinding(
            cve_id="CVE-2024-5678",
            severity="high",
            cvss_score=7.5,
            package_name="curl",
            installed_version="7.80.0",
            fixed_version="7.88.0",
            affected_resource="default/api-server",
        ),
    ]
    scan_state.critical_cve_count = 1
    scan_state.patches_available = 2
    scan_state.reasoning_chain = [
        SecurityStep(
            step_number=1, action="scan_vulnerabilities",
            input_summary="Scanning 1 resource",
            output_summary="2 CVEs found, 1 critical",
            duration_ms=100, tool_used="cve_scanner",
        ),
        SecurityStep(
            step_number=2, action="assess_findings",
            input_summary="Assessing 2 CVEs",
            output_summary="Critical: openssl CVE",
            duration_ms=200, tool_used="llm",
        ),
    ]
    return scan_state


@pytest.fixture
def state_with_credentials(state_with_cves):
    """State after credential check."""
    state_with_cves.credential_statuses = [
        CredentialStatus(
            credential_id="db-prod-password",
            credential_type="database_password",
            service="postgresql",
            environment=Environment.PRODUCTION,
            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
            days_until_expiry=3,
            needs_rotation=True,
        ),
    ]
    state_with_cves.credentials_needing_rotation = 1
    state_with_cves.reasoning_chain.append(
        SecurityStep(
            step_number=3, action="check_credentials",
            input_summary="Checking production credentials",
            output_summary="1 credential expiring soon",
            duration_ms=50, tool_used="credential_store + llm",
        ),
    )
    return state_with_cves


@pytest.fixture
def mock_cve_source():
    source = AsyncMock()
    source.source_name = "nvd"
    source.scan = AsyncMock(return_value=[
        {
            "cve_id": "CVE-2024-1234",
            "severity": "critical",
            "cvss_score": 9.8,
            "package_name": "openssl",
            "installed_version": "1.1.1",
            "fixed_version": "1.1.1w",
            "affected_resource": "default/api-server",
            "description": "Buffer overflow",
        },
    ])
    return source


@pytest.fixture
def mock_credential_store():
    store = AsyncMock()
    store.store_name = "vault"
    now = datetime.now(timezone.utc)
    store.list_credentials = AsyncMock(return_value=[
        {
            "credential_id": "db-prod-password",
            "credential_type": "database_password",
            "service": "postgresql",
            "expires_at": now + timedelta(days=3),
            "last_rotated": now - timedelta(days=83),
        },
        {
            "credential_id": "api-key-stripe",
            "credential_type": "api_key",
            "service": "stripe",
            "expires_at": now + timedelta(days=30),
            "last_rotated": now - timedelta(days=60),
        },
    ])
    return store


# ============================================================================
# SecurityToolkit tests
# ============================================================================


class TestSecurityToolkit:
    @pytest.mark.asyncio
    async def test_scan_cves(self, mock_cve_source):
        toolkit = SecurityToolkit(cve_sources=[mock_cve_source])
        result = await toolkit.scan_cves(["default/api-server"])

        assert result["total_findings"] == 1
        assert result["critical_count"] == 1
        assert result["sources_queried"] == ["nvd"]

    @pytest.mark.asyncio
    async def test_scan_cves_no_sources(self):
        toolkit = SecurityToolkit()
        result = await toolkit.scan_cves(["default/api-server"])
        assert result["total_findings"] == 0

    @pytest.mark.asyncio
    async def test_scan_cves_source_failure(self):
        source = AsyncMock()
        source.source_name = "failing"
        source.scan = AsyncMock(side_effect=ConnectionError("Timeout"))
        toolkit = SecurityToolkit(cve_sources=[source])

        result = await toolkit.scan_cves(["default/pod"])
        assert result["total_findings"] == 0

    @pytest.mark.asyncio
    async def test_check_credentials(self, mock_credential_store):
        toolkit = SecurityToolkit(credential_stores=[mock_credential_store])
        result = await toolkit.check_credentials()

        assert result["total_credentials"] == 2
        assert result["expiring_soon_count"] == 1
        assert result["healthy_count"] == 1

    @pytest.mark.asyncio
    async def test_check_credentials_no_stores(self):
        toolkit = SecurityToolkit()
        result = await toolkit.check_credentials()
        assert result["total_credentials"] == 0

    @pytest.mark.asyncio
    async def test_check_compliance(self):
        toolkit = SecurityToolkit()
        result = await toolkit.check_compliance("soc2")

        # No router = empty result
        assert result["framework"] == "soc2"
        assert result["controls_checked"] == 0

    @pytest.mark.asyncio
    async def test_check_compliance_with_router(self):
        router = MagicMock()
        toolkit = SecurityToolkit(connector_router=router)
        result = await toolkit.check_compliance("soc2")

        assert result["framework"] == "soc2"
        assert result["controls_checked"] == 6  # SOC2 has 6 controls defined

    def test_get_framework_controls_soc2(self):
        controls = SecurityToolkit._get_framework_controls("soc2")
        assert len(controls) == 6
        assert controls[0]["id"] == "SOC2-CC6.1"

    def test_get_framework_controls_pci(self):
        controls = SecurityToolkit._get_framework_controls("pci_dss")
        assert len(controls) == 5

    def test_get_framework_controls_unknown(self):
        controls = SecurityToolkit._get_framework_controls("unknown")
        assert controls == []

    @pytest.mark.asyncio
    async def test_get_resource_list_no_router(self):
        toolkit = SecurityToolkit()
        result = await toolkit.get_resource_list(Environment.PRODUCTION)
        assert result == []


# ============================================================================
# Node tests
# ============================================================================


class TestScanVulnerabilitiesNode:
    @pytest.mark.asyncio
    async def test_scan_with_cve_source(self, scan_state, mock_cve_source):
        from shieldops.agents.security.nodes import scan_vulnerabilities, set_toolkit

        toolkit = SecurityToolkit(cve_sources=[mock_cve_source])
        set_toolkit(toolkit)

        result = await scan_vulnerabilities(scan_state)

        assert result["current_step"] == "scan_vulnerabilities"
        assert len(result["cve_findings"]) == 1
        assert result["critical_cve_count"] == 1
        assert result["scan_start"] is not None

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_scan_empty_sources(self, scan_state):
        from shieldops.agents.security.nodes import scan_vulnerabilities, set_toolkit

        toolkit = SecurityToolkit()
        set_toolkit(toolkit)

        result = await scan_vulnerabilities(scan_state)

        assert len(result["cve_findings"]) == 0
        assert result["critical_cve_count"] == 0

        set_toolkit(None)


class TestAssessFindingsNode:
    @pytest.mark.asyncio
    async def test_assess_with_cves(self, state_with_cves):
        from shieldops.agents.security.nodes import assess_findings

        mock_result = VulnerabilityAssessmentResult(
            summary="Critical OpenSSL vulnerability requires immediate patching",
            risk_level="critical",
            top_risks=["CVE-2024-1234: OpenSSL buffer overflow"],
            patch_priority=["CVE-2024-1234", "CVE-2024-5678"],
            recommended_actions=["Patch openssl to 1.1.1w"],
        )

        with patch(
            "shieldops.agents.security.nodes.llm_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await assess_findings(state_with_cves)

        assert result["current_step"] == "assess_findings"

    @pytest.mark.asyncio
    async def test_assess_no_cves(self, scan_state):
        from shieldops.agents.security.nodes import assess_findings

        scan_state.reasoning_chain = [
            SecurityStep(
                step_number=1, action="scan", input_summary="",
                output_summary="", duration_ms=0,
            ),
        ]
        result = await assess_findings(scan_state)
        assert result["current_step"] == "assess_findings"

    @pytest.mark.asyncio
    async def test_assess_llm_failure(self, state_with_cves):
        from shieldops.agents.security.nodes import assess_findings

        with patch(
            "shieldops.agents.security.nodes.llm_structured",
            new_callable=AsyncMock,
            side_effect=Exception("LLM down"),
        ):
            result = await assess_findings(state_with_cves)

        # Should still complete without crashing
        assert result["current_step"] == "assess_findings"


class TestCheckCredentialsNode:
    @pytest.mark.asyncio
    async def test_check_with_expiring(self, state_with_cves, mock_credential_store):
        from shieldops.agents.security.nodes import check_credentials, set_toolkit

        toolkit = SecurityToolkit(credential_stores=[mock_credential_store])
        set_toolkit(toolkit)

        mock_result = CredentialAssessmentResult(
            summary="1 database credential expiring in 3 days",
            urgent_rotations=["db-prod-password"],
            rotation_plan=["1. Rotate db-prod-password"],
            risks=["Database access may be disrupted"],
        )

        with patch(
            "shieldops.agents.security.nodes.llm_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await check_credentials(state_with_cves)

        assert result["credentials_needing_rotation"] == 1
        assert len(result["credential_statuses"]) == 1

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_check_no_stores(self, state_with_cves):
        from shieldops.agents.security.nodes import check_credentials, set_toolkit

        toolkit = SecurityToolkit()
        set_toolkit(toolkit)

        result = await check_credentials(state_with_cves)
        assert result["credentials_needing_rotation"] == 0

        set_toolkit(None)


class TestEvaluateComplianceNode:
    @pytest.mark.asyncio
    async def test_evaluate_with_framework(self, state_with_credentials):
        from shieldops.agents.security.nodes import evaluate_compliance, set_toolkit

        router = MagicMock()
        toolkit = SecurityToolkit(connector_router=router)
        set_toolkit(toolkit)

        mock_result = ComplianceAssessmentResult(
            summary="Good compliance posture",
            overall_score=95.0,
            failing_controls=[],
            auto_remediable=[],
            manual_review_needed=[],
        )

        with patch(
            "shieldops.agents.security.nodes.llm_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await evaluate_compliance(state_with_credentials)

        assert result["compliance_score"] == 95.0
        assert len(result["compliance_controls"]) > 0

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_evaluate_no_router(self, state_with_credentials):
        from shieldops.agents.security.nodes import evaluate_compliance, set_toolkit

        toolkit = SecurityToolkit()
        set_toolkit(toolkit)

        result = await evaluate_compliance(state_with_credentials)
        assert result["compliance_score"] == 0.0

        set_toolkit(None)


class TestSynthesizePostureNode:
    @pytest.mark.asyncio
    async def test_synthesize_full(self, state_with_credentials):
        from shieldops.agents.security.nodes import synthesize_posture

        state_with_credentials.compliance_score = 90.0
        state_with_credentials.compliance_controls = [
            ComplianceControl(
                control_id="SOC2-CC6.1",
                framework="soc2",
                title="Logical access",
                status="passing",
                severity="critical",
            ),
        ]

        mock_result = SecurityPostureResult(
            overall_score=72.0,
            summary="Moderate security posture with critical CVE requiring attention",
            top_risks=["CVE-2024-1234 in OpenSSL", "Database credential expiring"],
            recommended_actions=["Patch OpenSSL", "Rotate database credential"],
        )

        with patch(
            "shieldops.agents.security.nodes.llm_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await synthesize_posture(state_with_credentials)

        assert result["posture"] is not None
        assert result["posture"].overall_score == 72.0
        assert result["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_synthesize_llm_failure(self, state_with_credentials):
        from shieldops.agents.security.nodes import synthesize_posture

        state_with_credentials.compliance_score = 100.0

        with patch(
            "shieldops.agents.security.nodes.llm_structured",
            new_callable=AsyncMock,
            side_effect=Exception("LLM unavailable"),
        ):
            result = await synthesize_posture(state_with_credentials)

        # Falls back to raw score calculation
        assert result["posture"] is not None
        assert result["posture"].overall_score > 0


# ============================================================================
# Graph routing tests
# ============================================================================


class TestGraphRouting:
    def test_should_check_credentials_full_scan(self, scan_state):
        from shieldops.agents.security.graph import should_check_credentials

        assert should_check_credentials(scan_state) == "check_credentials"

    def test_should_skip_credentials_cve_only(self, scan_state):
        from shieldops.agents.security.graph import should_check_credentials

        scan_state.scan_type = "cve_only"
        assert should_check_credentials(scan_state) == "synthesize_posture"

    def test_should_skip_credentials_on_error(self, scan_state):
        from shieldops.agents.security.graph import should_check_credentials

        scan_state.error = "scan failed"
        assert should_check_credentials(scan_state) == "synthesize_posture"

    def test_should_evaluate_compliance_full(self, scan_state):
        from shieldops.agents.security.graph import should_evaluate_compliance

        assert should_evaluate_compliance(scan_state) == "evaluate_compliance"

    def test_should_skip_compliance_cve_only(self, scan_state):
        from shieldops.agents.security.graph import should_evaluate_compliance

        scan_state.scan_type = "cve_only"
        assert should_evaluate_compliance(scan_state) == "synthesize_posture"

    def test_should_skip_compliance_credentials_only(self, scan_state):
        from shieldops.agents.security.graph import should_evaluate_compliance

        scan_state.scan_type = "credentials_only"
        assert should_evaluate_compliance(scan_state) == "synthesize_posture"


class TestGraphConstruction:
    def test_create_security_graph(self):
        from shieldops.agents.security.graph import create_security_graph

        graph = create_security_graph()
        compiled = graph.compile()
        assert compiled is not None


# ============================================================================
# Runner tests
# ============================================================================


class TestSecurityRunner:
    def test_runner_init(self):
        from shieldops.agents.security.runner import SecurityRunner

        runner = SecurityRunner()
        assert runner._scans == {}

    @pytest.mark.asyncio
    async def test_scan_returns_state(self):
        from shieldops.agents.security.runner import SecurityRunner

        runner = SecurityRunner()

        mock_state = SecurityScanState(
            scan_id="sec-mock",
            scan_type="full",
            target_environment=Environment.PRODUCTION,
            current_step="complete",
            scan_start=datetime.now(timezone.utc),
            posture=SecurityPosture(overall_score=85.0),
        )
        runner._app = AsyncMock()
        runner._app.ainvoke = AsyncMock(return_value=mock_state.model_dump())

        result = await runner.scan()

        assert result.current_step == "complete"
        assert len(runner._scans) == 1

    @pytest.mark.asyncio
    async def test_scan_handles_error(self):
        from shieldops.agents.security.runner import SecurityRunner

        runner = SecurityRunner()
        runner._app = AsyncMock()
        runner._app.ainvoke = AsyncMock(side_effect=RuntimeError("Graph failed"))

        result = await runner.scan()

        assert result.error == "Graph failed"
        assert result.current_step == "failed"

    def test_list_scans_empty(self):
        from shieldops.agents.security.runner import SecurityRunner

        runner = SecurityRunner()
        assert runner.list_scans() == []

    def test_get_scan_not_found(self):
        from shieldops.agents.security.runner import SecurityRunner

        runner = SecurityRunner()
        assert runner.get_scan("nonexistent") is None


# ============================================================================
# API endpoint tests
# ============================================================================


class TestSecurityAPI:
    @pytest.fixture
    def mock_runner(self):
        from shieldops.agents.security.runner import SecurityRunner

        runner = MagicMock(spec=SecurityRunner)
        runner.list_scans.return_value = [
            {
                "scan_id": "sec-abc123",
                "scan_type": "full",
                "environment": "production",
                "status": "complete",
                "cve_count": 5,
                "critical_cves": 1,
                "credentials_at_risk": 2,
                "compliance_score": 90.0,
                "posture_score": 75.0,
                "duration_ms": 5000,
                "error": None,
            },
        ]

        state = SecurityScanState(
            scan_id="sec-abc123",
            scan_type="full",
            target_environment=Environment.PRODUCTION,
            current_step="complete",
            cve_findings=[
                CVEFinding(
                    cve_id="CVE-2024-1234",
                    severity="critical",
                    cvss_score=9.8,
                    package_name="openssl",
                    installed_version="1.1.1",
                    fixed_version="1.1.1w",
                    affected_resource="default/api-server",
                ),
            ],
            compliance_controls=[
                ComplianceControl(
                    control_id="SOC2-CC6.1",
                    framework="soc2",
                    title="Logical access",
                    status="passing",
                    severity="critical",
                ),
            ],
            compliance_score=90.0,
            posture=SecurityPosture(
                overall_score=75.0,
                critical_cves=1,
                compliance_scores={"soc2": 90.0},
            ),
        )
        runner.get_scan.return_value = state
        runner.scan = AsyncMock(return_value=state)
        return runner

    @pytest.fixture
    async def client(self, mock_runner):
        from httpx import ASGITransport, AsyncClient

        from shieldops.api.app import create_app
        from shieldops.api.routes.security import set_runner

        set_runner(mock_runner)
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

        set_runner(None)

    @pytest.mark.asyncio
    async def test_list_scans(self, client):
        response = await client.get("/api/v1/security/scans")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_get_scan(self, client):
        response = await client.get("/api/v1/security/scans/sec-abc123")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_scan_not_found(self, client, mock_runner):
        mock_runner.get_scan.return_value = None
        response = await client.get("/api/v1/security/scans/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_trigger_scan_async(self, client):
        response = await client.post(
            "/api/v1/security/scans",
            json={"environment": "production", "scan_type": "full"},
        )
        assert response.status_code == 202
        assert response.json()["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_trigger_scan_sync(self, client):
        response = await client.post(
            "/api/v1/security/scans/sync",
            json={"environment": "production", "scan_type": "cve_only"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_posture(self, client):
        response = await client.get("/api/v1/security/posture")
        assert response.status_code == 200
        data = response.json()
        assert data["overall_score"] == 75.0

    @pytest.mark.asyncio
    async def test_get_posture_no_scans(self, client, mock_runner):
        mock_runner.list_scans.return_value = []
        response = await client.get("/api/v1/security/posture")
        assert response.status_code == 200
        assert "message" in response.json()

    @pytest.mark.asyncio
    async def test_list_cves(self, client):
        response = await client.get("/api/v1/security/cves")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["cves"][0]["cve_id"] == "CVE-2024-1234"

    @pytest.mark.asyncio
    async def test_list_cves_filter_severity(self, client):
        response = await client.get("/api/v1/security/cves?severity=critical")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_compliance_status(self, client):
        response = await client.get("/api/v1/security/compliance/soc2")
        assert response.status_code == 200
        data = response.json()
        assert data["framework"] == "soc2"
        assert data["score"] == 90.0
        assert len(data["controls"]) == 1


# ============================================================================
# Security models tests
# ============================================================================


class TestSecurityModels:
    def test_cve_finding(self):
        cve = CVEFinding(
            cve_id="CVE-2024-1234",
            severity="critical",
            cvss_score=9.8,
            package_name="openssl",
            installed_version="1.1.1",
            affected_resource="default/api-server",
        )
        assert cve.cvss_score == 9.8
        assert cve.fixed_version is None

    def test_credential_status(self):
        cred = CredentialStatus(
            credential_id="db-password",
            credential_type="database_password",
            service="postgresql",
            environment=Environment.PRODUCTION,
            needs_rotation=True,
        )
        assert cred.needs_rotation is True

    def test_compliance_control(self):
        control = ComplianceControl(
            control_id="SOC2-CC6.1",
            framework="soc2",
            title="Logical access security",
            status="passing",
            severity="critical",
        )
        assert control.status == "passing"

    def test_security_posture(self):
        posture = SecurityPosture(
            overall_score=85.0,
            critical_cves=1,
            high_cves=3,
        )
        assert posture.overall_score == 85.0
        assert posture.top_risks == []

    def test_security_step(self):
        step = SecurityStep(
            step_number=1,
            action="scan_cves",
            input_summary="Scanning",
            output_summary="5 CVEs found",
            duration_ms=100,
        )
        assert step.tool_used is None

    def test_scan_state_defaults(self):
        state = SecurityScanState()
        assert state.scan_id == ""
        assert state.scan_type == "full"
        assert state.cve_findings == []
        assert state.credential_statuses == []
        assert state.compliance_controls == []
        assert state.posture is None
        assert state.current_step == "init"
        assert state.error is None
