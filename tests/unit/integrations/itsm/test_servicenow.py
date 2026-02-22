"""Tests for the ServiceNow ITSM integration.

Covers:
- ServiceNowClient lifecycle and lazy initialisation
- Incident CRUD (create, read, update, close)
- Change request CRUD (create, read, update)
- State mappings (ShieldOps <-> ServiceNow)
- Urgency mappings
- create_from_shieldops_incident domain mapper
- create_change_from_remediation domain mapper
- Webhook handling and state translation
- Connection test (success + auth failure)
- Error handling (timeout, HTTP errors, 401, 404)
- Pydantic config models
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from shieldops.integrations.itsm.servicenow import (
    SHIELDOPS_TO_SNOW_STATE,
    SNOW_TO_SHIELDOPS_STATE,
    URGENCY_MAP,
    IncidentState,
    ServiceNowAuthError,
    ServiceNowClient,
    ServiceNowConfig,
    ServiceNowError,
    ServiceNowNotFoundError,
    ServiceNowRecord,
)

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def client() -> ServiceNowClient:
    """Pre-configured ServiceNowClient (no real HTTP)."""
    return ServiceNowClient(
        instance_url="https://test.service-now.com",
        username="admin",
        password="secret",  # noqa: S106
        timeout=5.0,
    )


def _mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
    content: bytes = b"",
) -> MagicMock:
    """Build a mock ``httpx.Response``."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.content = content or (b"{}" if json_data is None else b'{"result": {}}')
    resp.text = resp.content.decode()
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


# ============================================================================
# Lifecycle
# ============================================================================


class TestLifecycle:
    def test_client_strips_trailing_slash(self) -> None:
        c = ServiceNowClient(
            instance_url="https://x.service-now.com/",
            username="u",
            password="p",  # noqa: S106
        )
        assert c._instance_url == "https://x.service-now.com"

    def test_lazy_client_starts_none(self, client: ServiceNowClient) -> None:
        assert client._client is None

    def test_ensure_client_creates_httpx(self, client: ServiceNowClient) -> None:
        hc = client._ensure_client()
        assert isinstance(hc, httpx.AsyncClient)
        assert client._client is hc

    def test_ensure_client_reuses_instance(self, client: ServiceNowClient) -> None:
        hc1 = client._ensure_client()
        hc2 = client._ensure_client()
        assert hc1 is hc2

    @pytest.mark.asyncio
    async def test_close_resets_client(self, client: ServiceNowClient) -> None:
        client._ensure_client()
        assert client._client is not None
        await client.close()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_on_uninitialized_is_noop(self, client: ServiceNowClient) -> None:
        await client.close()  # should not raise
        assert client._client is None


# ============================================================================
# Low-level _request
# ============================================================================


class TestRequest:
    @pytest.mark.asyncio
    async def test_request_returns_json(self, client: ServiceNowClient) -> None:
        mock_resp = _mock_response(200, json_data={"result": {"sys_id": "abc"}})
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=mock_resp)
        client._client = mock_hc

        data = await client._request("GET", "/api/now/table/incident/abc")
        assert data == {"result": {"sys_id": "abc"}}

    @pytest.mark.asyncio
    async def test_request_raises_auth_error_on_401(self, client: ServiceNowClient) -> None:
        mock_resp = _mock_response(401)
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=mock_resp)
        client._client = mock_hc

        with pytest.raises(ServiceNowAuthError):
            await client._request("GET", "/api/now/table/incident")

    @pytest.mark.asyncio
    async def test_request_raises_auth_error_on_403(self, client: ServiceNowClient) -> None:
        mock_resp = _mock_response(403)
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=mock_resp)
        client._client = mock_hc

        with pytest.raises(ServiceNowAuthError):
            await client._request("GET", "/api/now/table/incident")

    @pytest.mark.asyncio
    async def test_request_raises_not_found_on_404(self, client: ServiceNowClient) -> None:
        mock_resp = _mock_response(404)
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=mock_resp)
        client._client = mock_hc

        with pytest.raises(ServiceNowNotFoundError):
            await client._request("GET", "/api/now/table/incident/bad")

    @pytest.mark.asyncio
    async def test_request_raises_on_500(self, client: ServiceNowClient) -> None:
        mock_resp = _mock_response(500, content=b"Internal Server Error")
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=mock_resp)
        client._client = mock_hc

        with pytest.raises(ServiceNowError) as exc_info:
            await client._request("GET", "/api/now/table/incident")
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_request_handles_timeout(self, client: ServiceNowClient) -> None:
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        client._client = mock_hc

        with pytest.raises(ServiceNowError, match="timed out"):
            await client._request("GET", "/api/now/table/incident")

    @pytest.mark.asyncio
    async def test_request_handles_connection_error(self, client: ServiceNowClient) -> None:
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        client._client = mock_hc

        with pytest.raises(ServiceNowError, match="HTTP error"):
            await client._request("GET", "/api/now/table/incident")

    @pytest.mark.asyncio
    async def test_request_handles_204_empty_body(self, client: ServiceNowClient) -> None:
        mock_resp = _mock_response(204)
        mock_resp.content = b""
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=mock_resp)
        client._client = mock_hc

        result = await client._request("DELETE", "/api/now/table/incident/abc")
        assert result == {}


# ============================================================================
# Incident CRUD
# ============================================================================


class TestIncidentCRUD:
    @pytest.mark.asyncio
    async def test_create_incident(self, client: ServiceNowClient) -> None:
        expected = {
            "result": {
                "sys_id": "inc001",
                "number": "INC0010001",
                "short_description": "Server down",
            }
        }
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=_mock_response(201, expected))
        client._client = mock_hc

        result = await client.create_incident(
            short_description="Server down",
            description="Web server is not responding",
            urgency=2,
            impact=2,
            category="Hardware",
        )
        assert result["sys_id"] == "inc001"
        assert result["number"] == "INC0010001"

        # Verify request payload
        call_kwargs = mock_hc.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["short_description"] == "Server down"
        assert body["urgency"] == "2"
        assert body["category"] == "Hardware"

    @pytest.mark.asyncio
    async def test_create_incident_minimal(self, client: ServiceNowClient) -> None:
        expected = {"result": {"sys_id": "inc002", "number": "INC0010002"}}
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=_mock_response(201, expected))
        client._client = mock_hc

        result = await client.create_incident(
            short_description="Alert",
            description="Something happened",
        )
        assert result["sys_id"] == "inc002"

        call_kwargs = mock_hc.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        # Optional fields should not be present
        assert "category" not in body
        assert "assignment_group" not in body
        assert "caller_id" not in body

    @pytest.mark.asyncio
    async def test_get_incident(self, client: ServiceNowClient) -> None:
        expected = {"result": {"sys_id": "inc001", "state": "1", "number": "INC0010001"}}
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=_mock_response(200, expected))
        client._client = mock_hc

        result = await client.get_incident("inc001")
        assert result["sys_id"] == "inc001"
        assert result["state"] == "1"

    @pytest.mark.asyncio
    async def test_update_incident(self, client: ServiceNowClient) -> None:
        expected = {"result": {"sys_id": "inc001", "state": "2"}}
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=_mock_response(200, expected))
        client._client = mock_hc

        result = await client.update_incident("inc001", {"state": "2"})
        assert result["state"] == "2"

        call_kwargs = mock_hc.request.call_args
        assert call_kwargs[0][0] == "PATCH"

    @pytest.mark.asyncio
    async def test_close_incident(self, client: ServiceNowClient) -> None:
        expected = {
            "result": {
                "sys_id": "inc001",
                "state": "7",
                "close_code": "Solved",
            }
        }
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=_mock_response(200, expected))
        client._client = mock_hc

        result = await client.close_incident(
            "inc001", close_code="Solved", close_notes="Fixed by ShieldOps"
        )
        assert result["state"] == "7"

        call_kwargs = mock_hc.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["state"] == str(IncidentState.CLOSED)
        assert body["close_code"] == "Solved"
        assert body["close_notes"] == "Fixed by ShieldOps"

    @pytest.mark.asyncio
    async def test_close_incident_default_notes(self, client: ServiceNowClient) -> None:
        expected = {"result": {"sys_id": "inc001", "state": "7"}}
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=_mock_response(200, expected))
        client._client = mock_hc

        await client.close_incident("inc001")

        call_kwargs = mock_hc.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["close_notes"] == "Closed by ShieldOps automation"


# ============================================================================
# Change Request CRUD
# ============================================================================


class TestChangeRequestCRUD:
    @pytest.mark.asyncio
    async def test_create_change_request(self, client: ServiceNowClient) -> None:
        expected = {
            "result": {
                "sys_id": "chg001",
                "number": "CHG0010001",
                "type": "normal",
            }
        }
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=_mock_response(201, expected))
        client._client = mock_hc

        result = await client.create_change_request(
            short_description="Scale up web tier",
            description="Increase replica count from 3 to 5",
            type="normal",
            risk="moderate",
            impact=2,
            assignment_group="SRE",
        )
        assert result["sys_id"] == "chg001"

        call_kwargs = mock_hc.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["type"] == "normal"
        assert body["risk"] == "moderate"
        assert body["assignment_group"] == "SRE"

    @pytest.mark.asyncio
    async def test_get_change_request(self, client: ServiceNowClient) -> None:
        expected = {"result": {"sys_id": "chg001", "number": "CHG0010001"}}
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=_mock_response(200, expected))
        client._client = mock_hc

        result = await client.get_change_request("chg001")
        assert result["sys_id"] == "chg001"

    @pytest.mark.asyncio
    async def test_update_change_request(self, client: ServiceNowClient) -> None:
        expected = {"result": {"sys_id": "chg001", "state": "implement"}}
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=_mock_response(200, expected))
        client._client = mock_hc

        result = await client.update_change_request("chg001", {"state": "implement"})
        assert result["state"] == "implement"


# ============================================================================
# Domain mappers
# ============================================================================


class TestCreateFromShieldOpsIncident:
    @pytest.mark.asyncio
    async def test_maps_severity_to_urgency(self, client: ServiceNowClient) -> None:
        expected = {"result": {"sys_id": "inc099", "number": "INC0099", "urgency": "1"}}
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=_mock_response(201, expected))
        client._client = mock_hc

        incident = {
            "title": "Database connection pool exhausted",
            "description": "All connections used",
            "severity": "critical",
            "environment": "production",
            "service": "api-gateway",
            "incident_id": "shield-001",
        }
        result = await client.create_from_shieldops_incident(incident)
        assert result["sys_id"] == "inc099"

        call_kwargs = mock_hc.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["urgency"] == "1"  # critical -> 1
        assert body["impact"] == "1"
        assert "[ShieldOps]" in body["short_description"]
        assert "shield-001" in body["description"]

    @pytest.mark.asyncio
    async def test_defaults_for_missing_fields(self, client: ServiceNowClient) -> None:
        expected = {"result": {"sys_id": "inc100"}}
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=_mock_response(201, expected))
        client._client = mock_hc

        result = await client.create_from_shieldops_incident({})
        assert result["sys_id"] == "inc100"

        call_kwargs = mock_hc.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["urgency"] == "3"  # default medium
        assert "[ShieldOps] Incident" in body["short_description"]


class TestCreateChangeFromRemediation:
    @pytest.mark.asyncio
    async def test_maps_remediation_to_change(self, client: ServiceNowClient) -> None:
        expected = {"result": {"sys_id": "chg099", "number": "CHG0099"}}
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=_mock_response(201, expected))
        client._client = mock_hc

        remediation = {
            "name": "Scale up web tier",
            "description": "Increase replica count",
            "risk_level": "high",
            "environment": "production",
            "target": "k8s/web-deployment",
            "remediation_id": "rem-001",
            "playbook": "scale-up",
        }
        result = await client.create_change_from_remediation(remediation)
        assert result["sys_id"] == "chg099"

        call_kwargs = mock_hc.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["risk"] == "high"
        assert body["impact"] == "2"  # high -> 2
        assert "[ShieldOps]" in body["short_description"]
        assert "rem-001" in body["description"]
        assert "scale-up" in body["description"]

    @pytest.mark.asyncio
    async def test_defaults_for_empty_remediation(self, client: ServiceNowClient) -> None:
        expected = {"result": {"sys_id": "chg100"}}
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=_mock_response(201, expected))
        client._client = mock_hc

        result = await client.create_change_from_remediation({})
        assert result["sys_id"] == "chg100"

        call_kwargs = mock_hc.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["risk"] == "moderate"  # default
        assert body["type"] == "normal"


# ============================================================================
# Webhook handling
# ============================================================================


class TestWebhookHandling:
    @pytest.mark.asyncio
    async def test_webhook_state_translation_new(self, client: ServiceNowClient) -> None:
        payload = {
            "sys_id": "inc001",
            "number": "INC0010001",
            "state": "1",
            "table": "incident",
            "action": "update",
        }
        result = await client.handle_webhook(payload)
        assert result["event_type"] == "servicenow.incident.update"
        assert result["shieldops_state"] == "open"
        assert result["sys_id"] == "inc001"

    @pytest.mark.asyncio
    async def test_webhook_state_translation_in_progress(self, client: ServiceNowClient) -> None:
        payload = {"sys_id": "inc002", "state": "2", "table": "incident", "action": "update"}
        result = await client.handle_webhook(payload)
        assert result["shieldops_state"] == "investigating"

    @pytest.mark.asyncio
    async def test_webhook_state_translation_resolved(self, client: ServiceNowClient) -> None:
        payload = {"sys_id": "inc003", "state": "6", "table": "incident", "action": "update"}
        result = await client.handle_webhook(payload)
        assert result["shieldops_state"] == "resolved"

    @pytest.mark.asyncio
    async def test_webhook_state_translation_closed(self, client: ServiceNowClient) -> None:
        payload = {"sys_id": "inc004", "state": "7", "table": "incident", "action": "update"}
        result = await client.handle_webhook(payload)
        assert result["shieldops_state"] == "closed"

    @pytest.mark.asyncio
    async def test_webhook_unknown_state_returns_none(self, client: ServiceNowClient) -> None:
        payload = {"sys_id": "inc005", "state": "99", "table": "incident", "action": "update"}
        result = await client.handle_webhook(payload)
        assert result["shieldops_state"] is None

    @pytest.mark.asyncio
    async def test_webhook_invalid_state_value(self, client: ServiceNowClient) -> None:
        payload = {"sys_id": "inc006", "state": "not_a_number", "table": "incident"}
        result = await client.handle_webhook(payload)
        assert result["shieldops_state"] is None

    @pytest.mark.asyncio
    async def test_webhook_no_state_field(self, client: ServiceNowClient) -> None:
        payload = {"sys_id": "inc007", "table": "change_request", "action": "insert"}
        result = await client.handle_webhook(payload)
        assert result["shieldops_state"] is None
        assert result["event_type"] == "servicenow.change_request.insert"

    @pytest.mark.asyncio
    async def test_webhook_preserves_full_payload(self, client: ServiceNowClient) -> None:
        payload = {"sys_id": "inc008", "state": "1", "custom_field": "value"}
        result = await client.handle_webhook(payload)
        assert result["payload"]["custom_field"] == "value"


# ============================================================================
# Connection test
# ============================================================================


class TestConnectionTest:
    @pytest.mark.asyncio
    async def test_connection_success(self, client: ServiceNowClient) -> None:
        mock_resp = _mock_response(200, {"result": []})
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=mock_resp)
        client._client = mock_hc

        result = await client.test_connection()
        assert result["connected"] is True
        assert result["instance_url"] == "https://test.service-now.com"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_connection_auth_failure(self, client: ServiceNowClient) -> None:
        mock_resp = _mock_response(401)
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(return_value=mock_resp)
        client._client = mock_hc

        result = await client.test_connection()
        assert result["connected"] is False
        assert "Authentication failed" in result["error"]

    @pytest.mark.asyncio
    async def test_connection_generic_error(self, client: ServiceNowClient) -> None:
        mock_hc = AsyncMock(spec=httpx.AsyncClient)
        mock_hc.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        client._client = mock_hc

        result = await client.test_connection()
        assert result["connected"] is False
        assert result["error"]  # non-empty error message


# ============================================================================
# State and urgency mappings
# ============================================================================


class TestStateMappings:
    def test_shieldops_to_snow_open(self) -> None:
        assert SHIELDOPS_TO_SNOW_STATE["open"] == 1

    def test_shieldops_to_snow_investigating(self) -> None:
        assert SHIELDOPS_TO_SNOW_STATE["investigating"] == 2

    def test_shieldops_to_snow_resolved(self) -> None:
        assert SHIELDOPS_TO_SNOW_STATE["resolved"] == 6

    def test_shieldops_to_snow_closed(self) -> None:
        assert SHIELDOPS_TO_SNOW_STATE["closed"] == 7

    def test_snow_to_shieldops_roundtrip(self) -> None:
        """Every ShieldOps state maps to SNOW and back."""
        for shield_state, snow_int in SHIELDOPS_TO_SNOW_STATE.items():
            assert SNOW_TO_SHIELDOPS_STATE[snow_int] == shield_state

    def test_snow_on_hold_maps_to_investigating(self) -> None:
        assert SNOW_TO_SHIELDOPS_STATE[IncidentState.ON_HOLD] == "investigating"

    def test_incident_state_enum_values(self) -> None:
        assert IncidentState.NEW == 1
        assert IncidentState.IN_PROGRESS == 2
        assert IncidentState.ON_HOLD == 3
        assert IncidentState.RESOLVED == 6
        assert IncidentState.CLOSED == 7


class TestUrgencyMapping:
    def test_critical_maps_to_1(self) -> None:
        assert URGENCY_MAP["critical"] == 1

    def test_high_maps_to_2(self) -> None:
        assert URGENCY_MAP["high"] == 2

    def test_medium_maps_to_3(self) -> None:
        assert URGENCY_MAP["medium"] == 3

    def test_low_maps_to_4(self) -> None:
        assert URGENCY_MAP["low"] == 4


# ============================================================================
# Pydantic models
# ============================================================================


class TestPydanticModels:
    def test_config_strips_trailing_slash(self) -> None:
        config = ServiceNowConfig(
            instance_url="https://x.service-now.com/",
            username="u",
            password="p",  # noqa: S106
        )
        assert config.instance_url == "https://x.service-now.com"

    def test_config_defaults(self) -> None:
        config = ServiceNowConfig(
            instance_url="https://x.service-now.com",
            username="u",
            password="p",  # noqa: S106
        )
        assert config.incident_table == "incident"
        assert config.change_table == "change_request"
        assert config.urgency_mapping == URGENCY_MAP
        assert config.state_mapping == SHIELDOPS_TO_SNOW_STATE

    def test_record_defaults(self) -> None:
        record = ServiceNowRecord()
        assert record.sys_id == ""
        assert record.number == ""
        assert record.state == ""

    def test_record_populated(self) -> None:
        record = ServiceNowRecord(
            sys_id="abc123",
            number="INC0010001",
            short_description="Test",
            state="1",
            priority="2",
            created_on="2025-01-01",
            updated_on="2025-01-02",
        )
        assert record.sys_id == "abc123"
        assert record.number == "INC0010001"


# ============================================================================
# Exception hierarchy
# ============================================================================


class TestExceptions:
    def test_servicenow_error_has_status_code(self) -> None:
        err = ServiceNowError("fail", status_code=500)
        assert err.status_code == 500
        assert str(err) == "fail"

    def test_auth_error_is_servicenow_error(self) -> None:
        err = ServiceNowAuthError("auth fail", status_code=401)
        assert isinstance(err, ServiceNowError)
        assert err.status_code == 401

    def test_not_found_error_is_servicenow_error(self) -> None:
        err = ServiceNowNotFoundError("missing", status_code=404)
        assert isinstance(err, ServiceNowError)
        assert err.status_code == 404
