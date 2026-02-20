"""Tests for Pydantic response models."""

from __future__ import annotations

from datetime import datetime

from shieldops_sdk.models import (
    Agent,
    Investigation,
    PaginatedResponse,
    Remediation,
    SecurityScan,
    Vulnerability,
)


class TestPaginatedResponse:
    def test_pagination_response_model(self) -> None:
        page: PaginatedResponse[Investigation] = PaginatedResponse[Investigation](
            items=[
                Investigation(
                    investigation_id="inv-1",
                    alert_id="a1",
                    status="complete",
                    confidence=0.88,
                ),
            ],
            total=100,
            limit=10,
            offset=0,
        )
        assert page.total == 100
        assert len(page.items) == 1
        assert page.has_more is True

    def test_pagination_no_more(self) -> None:
        page: PaginatedResponse[Investigation] = PaginatedResponse[Investigation](
            items=[],
            total=5,
            limit=10,
            offset=0,
        )
        assert page.has_more is False


class TestInvestigationModel:
    def test_investigation_model_parsing(self) -> None:
        data = {
            "investigation_id": "inv-42",
            "alert_id": "alert-7",
            "alert_name": "HighCPU",
            "status": "complete",
            "severity": "critical",
            "confidence": 0.97,
            "hypotheses_count": 4,
            "duration_ms": 3200,
            "created_at": "2025-06-15T10:30:00Z",
        }
        inv = Investigation(**data)
        assert inv.investigation_id == "inv-42"
        assert inv.confidence == 0.97
        assert inv.severity == "critical"
        assert isinstance(inv.created_at, datetime)

    def test_investigation_defaults(self) -> None:
        inv = Investigation(investigation_id="x", alert_id="a")
        assert inv.status == "pending"
        assert inv.confidence == 0.0
        assert inv.error is None


class TestVulnerabilityModel:
    def test_vulnerability_model_parsing(self) -> None:
        data = {
            "id": "vuln-001",
            "cve_id": "CVE-2024-12345",
            "severity": "critical",
            "status": "triaged",
            "affected_resource": "api-server:latest",
            "scanner_type": "trivy",
            "created_at": "2025-03-01T08:00:00+00:00",
        }
        vuln = Vulnerability(**data)
        assert vuln.id == "vuln-001"
        assert vuln.cve_id == "CVE-2024-12345"
        assert vuln.status == "triaged"
        assert isinstance(vuln.created_at, datetime)


class TestRemediationModel:
    def test_remediation_from_alias(self) -> None:
        """The API returns 'remediation_id' but our model aliases it to 'id'."""
        data = {
            "remediation_id": "rem-77",
            "action_type": "scale_up",
            "target_resource": "worker-pool",
            "environment": "staging",
            "status": "pending_approval",
            "risk_level": "high",
        }
        rem = Remediation(**data)
        assert rem.id == "rem-77"
        assert rem.risk_level == "high"


class TestSecurityScanModel:
    def test_security_scan_parsing(self) -> None:
        scan = SecurityScan(
            scan_id="scan-10",
            scan_type="full",
            status="complete",
            environment="production",
            compliance_score=87.5,
            critical_cves=2,
        )
        assert scan.compliance_score == 87.5
        assert scan.critical_cves == 2


class TestAgentModel:
    def test_agent_from_alias(self) -> None:
        data = {
            "agent_id": "agent-inv-1",
            "agent_type": "investigation",
            "status": "active",
            "environment": "production",
            "last_heartbeat": "2025-06-15T12:00:00Z",
        }
        agent = Agent(**data)
        assert agent.id == "agent-inv-1"
        assert agent.agent_type == "investigation"
        assert isinstance(agent.last_heartbeat, datetime)
