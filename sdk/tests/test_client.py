"""Tests for the synchronous ShieldOpsClient."""

from __future__ import annotations

import httpx
import pytest
import respx

from shieldops_sdk import ShieldOpsClient
from shieldops_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)

BASE = "http://localhost:8000/api/v1"


# ---------------------------------------------------------------------------
# Client initialisation
# ---------------------------------------------------------------------------


class TestClientInit:
    def test_client_init_with_api_key(self) -> None:
        client = ShieldOpsClient(api_key="test-key-123")
        assert client._http.headers["X-API-Key"] == "test-key-123"
        assert "Authorization" not in client._http.headers
        client.close()

    def test_client_init_with_token(self) -> None:
        client = ShieldOpsClient(token="jwt.token.here")
        assert client._http.headers["Authorization"] == "Bearer jwt.token.here"
        assert "X-API-Key" not in client._http.headers
        client.close()

    def test_client_init_defaults(self) -> None:
        client = ShieldOpsClient()
        assert str(client._http.base_url) == f"{BASE}/"
        assert client._http.headers["User-Agent"] == "shieldops-sdk/0.1.0"
        client.close()

    def test_client_context_manager(self) -> None:
        with ShieldOpsClient(api_key="k") as client:
            assert client.investigations is not None
            assert client.remediations is not None
            assert client.security is not None
            assert client.vulnerabilities is not None
            assert client.agents is not None
        # After exiting the context manager the transport should be closed.
        assert client._http.is_closed


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @respx.mock
    def test_health_check(self) -> None:
        respx.get("http://localhost:8000/health").mock(
            return_value=httpx.Response(200, json={"status": "healthy", "version": "1.0.0"})
        )
        with ShieldOpsClient() as client:
            result = client.health()
        assert result["status"] == "healthy"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @respx.mock
    def test_auth_error_raises(self) -> None:
        respx.get(f"{BASE}/investigations").mock(
            return_value=httpx.Response(401, json={"detail": "Invalid token"})
        )
        with ShieldOpsClient(token="bad") as client:
            with pytest.raises(AuthenticationError) as exc_info:
                client.investigations.list()
            assert exc_info.value.status_code == 401
            assert "Invalid token" in str(exc_info.value)

    @respx.mock
    def test_get_remediation_not_found_raises(self) -> None:
        respx.get(f"{BASE}/remediations/rem-nonexistent").mock(
            return_value=httpx.Response(404, json={"detail": "Remediation not found"})
        )
        with ShieldOpsClient(api_key="k") as client:
            with pytest.raises(NotFoundError) as exc_info:
                client.remediations.get("rem-nonexistent")
            assert exc_info.value.status_code == 404

    @respx.mock
    def test_rate_limit_error_includes_retry_after(self) -> None:
        respx.get(f"{BASE}/investigations").mock(
            return_value=httpx.Response(
                429,
                json={"detail": "Rate limit exceeded", "retry_after": 30},
                headers={"Retry-After": "30"},
            )
        )
        with ShieldOpsClient(api_key="k") as client:
            with pytest.raises(RateLimitError) as exc_info:
                client.investigations.list()
            assert exc_info.value.retry_after == 30
            assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# Investigations
# ---------------------------------------------------------------------------


class TestInvestigations:
    @respx.mock
    def test_list_investigations(self) -> None:
        respx.get(f"{BASE}/investigations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "investigations": [
                        {
                            "investigation_id": "inv-001",
                            "alert_id": "alert-1",
                            "alert_name": "HighCPU",
                            "status": "complete",
                            "confidence": 0.92,
                            "hypotheses_count": 3,
                            "duration_ms": 1500,
                        },
                        {
                            "investigation_id": "inv-002",
                            "alert_id": "alert-2",
                            "alert_name": "DiskFull",
                            "status": "running",
                            "confidence": 0.0,
                            "hypotheses_count": 0,
                            "duration_ms": 0,
                        },
                    ],
                    "total": 2,
                    "limit": 50,
                    "offset": 0,
                },
            )
        )
        with ShieldOpsClient(api_key="k") as client:
            page = client.investigations.list()
        assert page.total == 2
        assert len(page.items) == 2
        assert page.items[0].investigation_id == "inv-001"
        assert page.items[0].confidence == 0.92
        assert not page.has_more

    @respx.mock
    def test_get_investigation(self) -> None:
        respx.get(f"{BASE}/investigations/inv-001").mock(
            return_value=httpx.Response(
                200,
                json={
                    "investigation_id": "inv-001",
                    "alert_id": "alert-1",
                    "alert_name": "HighCPU",
                    "status": "complete",
                    "confidence": 0.95,
                    "hypotheses_count": 5,
                    "duration_ms": 2300,
                },
            )
        )
        with ShieldOpsClient(api_key="k") as client:
            inv = client.investigations.get("inv-001")
        assert inv.investigation_id == "inv-001"
        assert inv.status == "complete"

    @respx.mock
    def test_create_investigation(self) -> None:
        respx.post(f"{BASE}/investigations").mock(
            return_value=httpx.Response(
                202,
                json={
                    "status": "accepted",
                    "alert_id": "alert-99",
                    "message": "Investigation started.",
                },
            )
        )
        with ShieldOpsClient(api_key="k") as client:
            result = client.investigations.create(
                alert_id="alert-99",
                alert_name="OOMKill",
                severity="critical",
            )
        assert result["status"] == "accepted"


# ---------------------------------------------------------------------------
# Remediations
# ---------------------------------------------------------------------------


class TestRemediations:
    @respx.mock
    def test_list_remediations(self) -> None:
        respx.get(f"{BASE}/remediations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "remediations": [
                        {
                            "remediation_id": "rem-001",
                            "action_type": "restart_service",
                            "target_resource": "web-api",
                            "environment": "production",
                            "status": "complete",
                            "risk_level": "low",
                        },
                    ],
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                },
            )
        )
        with ShieldOpsClient(api_key="k") as client:
            page = client.remediations.list()
        assert page.total == 1
        assert page.items[0].action_type == "restart_service"
