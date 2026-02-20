"""Tests for individual resource classes (sync)."""

from __future__ import annotations

import httpx
import pytest
import respx

from shieldops_sdk import ShieldOpsClient
from shieldops_sdk.exceptions import NotFoundError, ServerError, ValidationError

BASE = "http://localhost:8000/api/v1"


class TestSecurityResource:
    @respx.mock
    def test_list_scans(self) -> None:
        respx.get(f"{BASE}/security/scans").mock(
            return_value=httpx.Response(
                200,
                json={
                    "scans": [
                        {
                            "scan_id": "scan-1",
                            "scan_type": "full",
                            "status": "complete",
                            "environment": "production",
                            "compliance_score": 91.0,
                            "critical_cves": 0,
                        },
                    ],
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                },
            )
        )
        with ShieldOpsClient(api_key="k") as client:
            page = client.security.list_scans()
        assert page.total == 1
        assert page.items[0].scan_id == "scan-1"

    @respx.mock
    def test_get_scan_not_found(self) -> None:
        respx.get(f"{BASE}/security/scans/scan-missing").mock(
            return_value=httpx.Response(404, json={"detail": "Scan not found"})
        )
        with ShieldOpsClient(api_key="k") as client:
            with pytest.raises(NotFoundError):
                client.security.get_scan("scan-missing")

    @respx.mock
    def test_get_posture(self) -> None:
        respx.get(f"{BASE}/security/posture").mock(
            return_value=httpx.Response(
                200,
                json={
                    "overall_score": 85.0,
                    "critical_cves": 1,
                    "pending_patches": 3,
                },
            )
        )
        with ShieldOpsClient(api_key="k") as client:
            posture = client.security.get_posture()
        assert posture["overall_score"] == 85.0


class TestVulnerabilitiesResource:
    @respx.mock
    def test_list_vulnerabilities(self) -> None:
        respx.get(f"{BASE}/vulnerabilities").mock(
            return_value=httpx.Response(
                200,
                json={
                    "vulnerabilities": [
                        {
                            "id": "v-1",
                            "cve_id": "CVE-2024-0001",
                            "severity": "high",
                            "status": "new",
                            "affected_resource": "db-server",
                        },
                    ],
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                },
            )
        )
        with ShieldOpsClient(api_key="k") as client:
            page = client.vulnerabilities.list()
        assert page.total == 1
        assert page.items[0].cve_id == "CVE-2024-0001"

    @respx.mock
    def test_update_status_validation_error(self) -> None:
        respx.put(f"{BASE}/vulnerabilities/v-1/status").mock(
            return_value=httpx.Response(
                422,
                json={"detail": "Invalid status value"},
            )
        )
        with ShieldOpsClient(api_key="k") as client:
            with pytest.raises(ValidationError):
                client.vulnerabilities.update_status("v-1", status="bogus")


class TestAgentsResource:
    @respx.mock
    def test_list_agents(self) -> None:
        respx.get(f"{BASE}/agents").mock(
            return_value=httpx.Response(
                200,
                json={
                    "agents": [
                        {
                            "agent_id": "agent-1",
                            "agent_type": "investigation",
                            "status": "active",
                            "environment": "production",
                        },
                    ],
                    "total": 1,
                },
            )
        )
        with ShieldOpsClient(api_key="k") as client:
            agents = client.agents.list()
        assert len(agents) == 1
        assert agents[0].agent_type == "investigation"

    @respx.mock
    def test_enable_agent(self) -> None:
        respx.post(f"{BASE}/agents/agent-1/enable").mock(
            return_value=httpx.Response(
                200,
                json={
                    "agent_id": "agent-1",
                    "action": "enabled",
                },
            )
        )
        with ShieldOpsClient(api_key="k") as client:
            result = client.agents.enable("agent-1")
        assert result["action"] == "enabled"


class TestServerError:
    @respx.mock
    def test_server_error_raises(self) -> None:
        respx.get(f"{BASE}/investigations").mock(
            return_value=httpx.Response(500, json={"detail": "Internal server error"})
        )
        with ShieldOpsClient(api_key="k") as client:
            with pytest.raises(ServerError) as exc_info:
                client.investigations.list()
            assert exc_info.value.status_code == 500
