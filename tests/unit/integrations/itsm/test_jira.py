"""Comprehensive tests for the Jira bidirectional sync integration.

Covers:
- JiraClient: create_issue, get_issue, update_issue, add_comment
- Incident-to-issue mapping (create_from_incident)
- Status sync (ShieldOps -> Jira)
- Webhook handling (status change, comment, issue created, unhandled)
- Priority mapping, status mapping, field mapping
- Connection test (test_connection)
- Error handling (auth failure, not found, network error, server error)
- Pydantic models (JiraConfig, JiraIssue)
- ADF text extraction and issue parsing
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from shieldops.integrations.itsm.jira import (
    DEFAULT_PRIORITY_TO_JIRA,
    DEFAULT_STATUS_FROM_JIRA,
    DEFAULT_STATUS_TO_JIRA,
    JiraAuthError,
    JiraClient,
    JiraConfig,
    JiraError,
    JiraIssue,
    JiraNotFoundError,
    _extract_text_from_adf,
)

# =========================================================================
# Helpers
# =========================================================================


def _make_client(
    base_url: str = "https://test.atlassian.net",
    email: str = "bot@example.com",
    api_token: str = "fake-token",  # noqa: S107
    project_key: str = "OPS",
    **kwargs: Any,
) -> JiraClient:
    """Build a JiraClient with test credentials."""
    return JiraClient(
        base_url=base_url,
        email=email,
        api_token=api_token,
        project_key=project_key,
        **kwargs,
    )


def _jira_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
    text: str | None = None,
) -> httpx.Response:
    """Build a mock httpx.Response for Jira API calls.

    Pass *json_data* for JSON responses or *text* for error bodies.
    Do not pass both -- httpx.Response does not support it.
    """
    kwargs: dict[str, Any] = {
        "status_code": status_code,
        "request": httpx.Request("GET", "https://test.atlassian.net/rest/api/3/test"),
    }
    if json_data is not None:
        kwargs["json"] = json_data
    elif text is not None:
        kwargs["text"] = text
    else:
        kwargs["json"] = {}
    return httpx.Response(**kwargs)


def _patch_httpx_client(response: httpx.Response) -> Any:
    """Create a context-manager patch for httpx.AsyncClient.

    The returned mock's ``request`` method resolves to *response*.
    """
    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=response)

    ctx = patch("shieldops.integrations.itsm.jira.httpx.AsyncClient")
    return ctx, mock_client


def _transitions_response(transitions: list[dict[str, Any]]) -> httpx.Response:
    """Build a /transitions response."""
    return _jira_response(json_data={"transitions": transitions})


def _issue_response(
    key: str = "OPS-42",
    summary: str = "Test issue",
    status: str = "To Do",
    priority: str = "Medium",
) -> httpx.Response:
    """Build a typical GET /issue response."""
    return _jira_response(
        json_data={
            "key": key,
            "id": "10042",
            "self": f"https://test.atlassian.net/rest/api/3/issue/{key}",
            "fields": {
                "summary": summary,
                "status": {"name": status},
                "priority": {"name": priority},
                "issuetype": {"name": "Bug"},
                "assignee": {"displayName": "Agent Bot"},
                "labels": ["shieldops"],
                "created": "2025-01-15T10:00:00.000+0000",
                "updated": "2025-01-15T12:00:00.000+0000",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Some description"}],
                        }
                    ],
                },
            },
        }
    )


# =========================================================================
# Pydantic Models
# =========================================================================


class TestJiraConfig:
    """Verify JiraConfig validation and defaults."""

    def test_minimal_config(self) -> None:
        config = JiraConfig(
            base_url="https://test.atlassian.net",
            email="user@example.com",
            api_token="tok",
        )
        assert config.project_key == "OPS"
        assert config.status_to_jira == DEFAULT_STATUS_TO_JIRA
        assert config.status_from_jira == DEFAULT_STATUS_FROM_JIRA
        assert config.priority_mapping == DEFAULT_PRIORITY_TO_JIRA

    def test_trailing_slash_stripped(self) -> None:
        config = JiraConfig(
            base_url="https://test.atlassian.net/",
            email="u@e.com",
            api_token="t",
        )
        assert config.base_url == "https://test.atlassian.net"

    def test_custom_mappings(self) -> None:
        config = JiraConfig(
            base_url="https://x.atlassian.net",
            email="u@e.com",
            api_token="t",
            status_to_jira={"open": "Open"},
            priority_mapping={"critical": "Blocker"},
        )
        assert config.status_to_jira == {"open": "Open"}
        assert config.priority_mapping == {"critical": "Blocker"}


class TestJiraIssue:
    """Verify JiraIssue model."""

    def test_from_dict(self) -> None:
        issue = JiraIssue(
            key="OPS-1",
            summary="Test",
            status="To Do",
        )
        assert issue.key == "OPS-1"
        assert issue.assignee is None
        assert issue.labels == []

    def test_full_issue(self) -> None:
        issue = JiraIssue(
            key="OPS-99",
            summary="Full issue",
            status="In Progress",
            priority="High",
            assignee="Alice",
            issue_type="Bug",
            labels=["shieldops", "env-prod"],
        )
        assert issue.assignee == "Alice"
        assert len(issue.labels) == 2


# =========================================================================
# Client Construction
# =========================================================================


class TestJiraClientInit:
    """Verify client construction and auth header generation."""

    def test_base_url_trailing_slash_stripped(self) -> None:
        client = _make_client(base_url="https://foo.atlassian.net/")
        assert client.base_url == "https://foo.atlassian.net"

    def test_auth_header_is_basic_base64(self) -> None:
        import base64

        client = _make_client(email="user@test.com", api_token="secret123")
        expected = base64.b64encode(b"user@test.com:secret123").decode()
        assert client._auth_header == f"Basic {expected}"

    def test_default_mappings(self) -> None:
        client = _make_client()
        assert client.status_to_jira == DEFAULT_STATUS_TO_JIRA
        assert client.status_from_jira == DEFAULT_STATUS_FROM_JIRA
        assert client.priority_mapping == DEFAULT_PRIORITY_TO_JIRA

    def test_custom_mappings_override(self) -> None:
        client = _make_client(
            status_to_jira={"open": "Backlog"},
            priority_mapping={"critical": "Blocker"},
        )
        assert client.status_to_jira == {"open": "Backlog"}
        assert client.priority_mapping == {"critical": "Blocker"}


# =========================================================================
# HTTP Request Layer
# =========================================================================


class TestRequest:
    """Test the internal _request method for error mapping."""

    async def test_401_raises_auth_error(self) -> None:
        client = _make_client()
        resp = _jira_response(status_code=401, text="Unauthorized")

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(JiraAuthError) as exc_info:
                await client._request("GET", "/rest/api/3/myself")
            assert exc_info.value.status_code == 401

    async def test_403_raises_auth_error(self) -> None:
        client = _make_client()
        resp = _jira_response(status_code=403, text="Forbidden")

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(JiraAuthError):
                await client._request("GET", "/rest/api/3/myself")

    async def test_404_raises_not_found(self) -> None:
        client = _make_client()
        resp = _jira_response(status_code=404, text="Not Found")

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(JiraNotFoundError) as exc_info:
                await client._request("GET", "/rest/api/3/issue/NOPE-999")
            assert exc_info.value.status_code == 404

    async def test_500_raises_jira_error(self) -> None:
        client = _make_client()
        resp = _jira_response(status_code=500, text="Internal Server Error")

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(JiraError) as exc_info:
                await client._request("GET", "/rest/api/3/issue/OPS-1")
            assert exc_info.value.status_code == 500

    async def test_204_returns_empty_dict(self) -> None:
        client = _make_client()
        resp = httpx.Response(
            status_code=204,
            request=httpx.Request("PUT", "https://test.atlassian.net/rest/api/3/issue/OPS-1"),
        )

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client._request("PUT", "/rest/api/3/issue/OPS-1")
            assert result == {}

    async def test_200_returns_json(self) -> None:
        client = _make_client()
        resp = _jira_response(json_data={"key": "OPS-1"})

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client._request("GET", "/rest/api/3/issue/OPS-1")
            assert result == {"key": "OPS-1"}


# =========================================================================
# Create Issue
# =========================================================================


class TestCreateIssue:
    """Test JiraClient.create_issue."""

    async def test_creates_issue_with_correct_payload(self) -> None:
        client = _make_client()
        resp = _jira_response(
            status_code=201,
            json_data={"key": "OPS-10", "id": "10010", "self": "https://..."},
        )

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.create_issue(
                summary="Server down",
                description="API server not responding",
                issue_type="Bug",
                priority="High",
                labels=["production", "critical"],
            )

        assert result["key"] == "OPS-10"

        # Verify the payload sent to Jira
        call_kwargs = mock.request.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        fields = payload["fields"]
        assert fields["project"]["key"] == "OPS"
        assert fields["summary"] == "Server down"
        assert fields["issuetype"]["name"] == "Bug"
        assert fields["priority"]["name"] == "High"
        assert fields["labels"] == ["production", "critical"]

    async def test_creates_issue_with_custom_fields(self) -> None:
        client = _make_client()
        resp = _jira_response(json_data={"key": "OPS-11", "id": "10011"})

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.create_issue(
                summary="Custom",
                description="test",
                custom_fields={"customfield_10001": "value1"},
            )

        assert result["key"] == "OPS-11"
        call_kwargs = mock.request.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["fields"]["customfield_10001"] == "value1"


# =========================================================================
# Get Issue
# =========================================================================


class TestGetIssue:
    """Test JiraClient.get_issue."""

    async def test_returns_issue_data(self) -> None:
        client = _make_client()
        resp = _issue_response(key="OPS-42")

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.get_issue("OPS-42")

        assert result["key"] == "OPS-42"
        assert result["fields"]["summary"] == "Test issue"

    async def test_not_found_raises(self) -> None:
        client = _make_client()
        resp = _jira_response(status_code=404, text="Not Found")

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(JiraNotFoundError):
                await client.get_issue("NOPE-999")


# =========================================================================
# Update Issue
# =========================================================================


class TestUpdateIssue:
    """Test JiraClient.update_issue with fields, status, and comment."""

    async def test_update_fields_only(self) -> None:
        client = _make_client()
        resp = _jira_response(status_code=204)

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.update_issue(
                "OPS-42",
                fields={"summary": "Updated title"},
            )

        assert result["fields_updated"] is True

    async def test_update_status_with_valid_transition(self) -> None:
        client = _make_client()

        # First call: GET transitions; Second call: POST transition
        transitions_resp = _transitions_response(
            [
                {"id": "31", "name": "Start Progress", "to": {"name": "In Progress"}},
                {"id": "41", "name": "Done", "to": {"name": "Done"}},
            ]
        )
        transition_post_resp = _jira_response(status_code=204)

        call_count = 0
        responses = [transitions_resp, transition_post_resp]

        async def side_effect(*args: Any, **kwargs: Any) -> httpx.Response:
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=side_effect)

        with patch("shieldops.integrations.itsm.jira.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.update_issue("OPS-42", status="In Progress")

        assert result["transitioned_to"] == "In Progress"

    async def test_update_status_no_matching_transition(self) -> None:
        client = _make_client()

        transitions_resp = _transitions_response(
            [
                {"id": "31", "name": "Start", "to": {"name": "In Progress"}},
            ]
        )

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=transitions_resp)

        with patch("shieldops.integrations.itsm.jira.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.update_issue("OPS-42", status="Blocked")

        assert "transition_error" in result

    async def test_update_with_comment(self) -> None:
        client = _make_client()
        comment_resp = _jira_response(json_data={"id": "1001"})

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=comment_resp)

        with patch("shieldops.integrations.itsm.jira.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.update_issue("OPS-42", comment="Investigation complete")

        assert result["comment_added"] is True


# =========================================================================
# Add Comment
# =========================================================================


class TestAddComment:
    """Test JiraClient.add_comment."""

    async def test_sends_adf_comment(self) -> None:
        client = _make_client()
        resp = _jira_response(json_data={"id": "2001"})

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.add_comment("OPS-42", "Root cause: memory leak")

        assert result["id"] == "2001"

        # Verify ADF structure
        call_kwargs = mock.request.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        body = payload["body"]
        assert body["type"] == "doc"
        assert body["content"][0]["content"][0]["text"] == "Root cause: memory leak"


# =========================================================================
# Create from Incident
# =========================================================================


class TestCreateFromIncident:
    """Test the incident-to-Jira-issue mapping."""

    async def test_basic_incident(self) -> None:
        client = _make_client()
        resp = _jira_response(json_data={"key": "OPS-20", "id": "10020"})

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=resp)

        with patch("shieldops.integrations.itsm.jira.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.create_from_incident(
                {
                    "title": "High CPU on web-01",
                    "severity": "high",
                    "service": "api-gateway",
                    "environment": "production",
                    "incident_id": "INC-001",
                    "description": "CPU at 98% for 15 minutes",
                }
            )

        assert result["key"] == "OPS-20"

        # Verify the mapped fields
        call_kwargs = mock_client.request.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        fields = payload["fields"]
        assert "[ShieldOps][api-gateway]" in fields["summary"]
        assert fields["priority"]["name"] == "High"
        assert fields["issuetype"]["name"] == "Bug"
        assert "shieldops" in fields["labels"]
        assert "env-production" in fields["labels"]

    async def test_incident_with_alert_name_fallback(self) -> None:
        client = _make_client()
        resp = _jira_response(json_data={"key": "OPS-21", "id": "10021"})

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=resp)

        with patch("shieldops.integrations.itsm.jira.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.create_from_incident(
                {
                    "alert_name": "Disk space warning",
                    "severity": "low",
                }
            )

        assert result["key"] == "OPS-21"
        call_kwargs = mock_client.request.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["fields"]["priority"]["name"] == "Low"

    async def test_incident_with_no_title(self) -> None:
        client = _make_client()
        resp = _jira_response(json_data={"key": "OPS-22", "id": "10022"})

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=resp)

        with patch("shieldops.integrations.itsm.jira.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.create_from_incident({})

        assert result["key"] == "OPS-22"
        call_kwargs = mock_client.request.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "ShieldOps Incident" in payload["fields"]["summary"]

    async def test_incident_security_type_maps_to_bug(self) -> None:
        client = _make_client()
        resp = _jira_response(json_data={"key": "OPS-23", "id": "10023"})

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=resp)

        with patch("shieldops.integrations.itsm.jira.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await client.create_from_incident(
                {
                    "title": "CVE detected",
                    "type": "security",
                    "severity": "critical",
                }
            )

        call_kwargs = mock_client.request.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["fields"]["issuetype"]["name"] == "Bug"
        assert payload["fields"]["priority"]["name"] == "Highest"

    async def test_incident_with_field_mapping(self) -> None:
        client = _make_client(
            field_mapping={"team": "customfield_10100"},
        )
        resp = _jira_response(json_data={"key": "OPS-24", "id": "10024"})

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=resp)

        with patch("shieldops.integrations.itsm.jira.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await client.create_from_incident(
                {
                    "title": "DB slow",
                    "team": "platform",
                    "severity": "medium",
                }
            )

        call_kwargs = mock_client.request.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["fields"]["customfield_10100"] == "platform"


# =========================================================================
# Status Sync
# =========================================================================


class TestSyncStatus:
    """Test ShieldOps -> Jira status synchronization."""

    async def test_maps_open_to_todo(self) -> None:
        client = _make_client()

        transitions_resp = _transitions_response(
            [
                {"id": "11", "name": "To Do", "to": {"name": "To Do"}},
            ]
        )
        transition_post_resp = _jira_response(status_code=204)

        call_count = 0
        responses = [transitions_resp, transition_post_resp]

        async def side_effect(*args: Any, **kwargs: Any) -> httpx.Response:
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=side_effect)

        with patch("shieldops.integrations.itsm.jira.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.sync_status("OPS-50", "open")

        assert result["transitioned_to"] == "To Do"

    async def test_unmapped_status_returns_error(self) -> None:
        client = _make_client()
        result = await client.sync_status("OPS-50", "unknown_status")
        assert "error" in result
        assert "No Jira mapping" in result["error"]

    async def test_maps_resolved_to_done(self) -> None:
        client = _make_client()

        transitions_resp = _transitions_response(
            [
                {"id": "51", "name": "Done", "to": {"name": "Done"}},
            ]
        )
        transition_post_resp = _jira_response(status_code=204)

        call_count = 0
        responses = [transitions_resp, transition_post_resp]

        async def side_effect(*args: Any, **kwargs: Any) -> httpx.Response:
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=side_effect)

        with patch("shieldops.integrations.itsm.jira.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.sync_status("OPS-50", "resolved")

        assert result["transitioned_to"] == "Done"


# =========================================================================
# Webhook Handling
# =========================================================================


class TestWebhookHandler:
    """Test incoming Jira webhook processing."""

    async def test_status_change_webhook(self) -> None:
        client = _make_client()
        payload = {
            "webhookEvent": "jira:issue_updated",
            "issue": {
                "key": "OPS-100",
                "fields": {"summary": "Flaky test"},
            },
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "To Do",
                        "toString": "In Progress",
                    }
                ]
            },
        }

        result = await client.handle_webhook(payload)

        assert result["event_type"] == "jira:issue_updated"
        assert result["issue_key"] == "OPS-100"
        assert result["action"] == "issue_updated"
        assert result["status_change"]["from_jira"] == "To Do"
        assert result["status_change"]["to_jira"] == "In Progress"
        assert result["shieldops_status"] == "investigating"

    async def test_status_change_to_done_maps_resolved(self) -> None:
        client = _make_client()
        payload = {
            "webhookEvent": "jira:issue_updated",
            "issue": {"key": "OPS-101", "fields": {}},
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "In Progress",
                        "toString": "Done",
                    }
                ]
            },
        }

        result = await client.handle_webhook(payload)
        assert result["shieldops_status"] == "resolved"

    async def test_status_change_unmapped_jira_status(self) -> None:
        client = _make_client()
        payload = {
            "webhookEvent": "jira:issue_updated",
            "issue": {"key": "OPS-102", "fields": {}},
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "To Do",
                        "toString": "Custom Status",
                    }
                ]
            },
        }

        result = await client.handle_webhook(payload)
        assert result["shieldops_status"] is None

    async def test_non_status_update_webhook(self) -> None:
        client = _make_client()
        payload = {
            "webhookEvent": "jira:issue_updated",
            "issue": {"key": "OPS-103", "fields": {}},
            "changelog": {
                "items": [
                    {
                        "field": "priority",
                        "fromString": "Medium",
                        "toString": "High",
                    }
                ]
            },
        }

        result = await client.handle_webhook(payload)
        assert result["action"] == "issue_updated"
        assert "status_change" not in result

    async def test_issue_created_webhook(self) -> None:
        client = _make_client()
        payload = {
            "webhookEvent": "jira:issue_created",
            "issue": {
                "key": "OPS-200",
                "fields": {
                    "summary": "New issue",
                    "status": {"name": "To Do"},
                },
            },
        }

        result = await client.handle_webhook(payload)

        assert result["event_type"] == "jira:issue_created"
        assert result["action"] == "issue_created"
        assert result["summary"] == "New issue"
        assert result["status"] == "To Do"

    async def test_comment_created_webhook_adf(self) -> None:
        client = _make_client()
        payload = {
            "webhookEvent": "comment_created",
            "issue": {"key": "OPS-300", "fields": {}},
            "comment": {
                "id": "5001",
                "author": {"displayName": "Alice Engineer"},
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "Checked the logs."},
                                {"type": "text", "text": "No anomalies found."},
                            ],
                        }
                    ],
                },
            },
        }

        result = await client.handle_webhook(payload)

        assert result["action"] == "comment_added"
        assert result["comment_id"] == "5001"
        assert result["comment_body"] == "Checked the logs. No anomalies found."
        assert result["comment_author"] == "Alice Engineer"

    async def test_comment_created_webhook_plain_string(self) -> None:
        client = _make_client()
        payload = {
            "webhookEvent": "comment_created",
            "issue": {"key": "OPS-301", "fields": {}},
            "comment": {
                "id": "5002",
                "author": {"displayName": "Bob"},
                "body": "Simple text comment",
            },
        }

        result = await client.handle_webhook(payload)
        assert result["comment_body"] == "Simple text comment"

    async def test_unhandled_webhook_event(self) -> None:
        client = _make_client()
        payload = {
            "webhookEvent": "jira:issue_deleted",
            "issue": {"key": "OPS-400", "fields": {}},
        }

        result = await client.handle_webhook(payload)
        assert result["action"] == "unhandled"

    async def test_empty_webhook_payload(self) -> None:
        client = _make_client()
        result = await client.handle_webhook({})
        assert result["event_type"] == ""
        assert result["issue_key"] == ""
        assert result["action"] == "unhandled"


# =========================================================================
# Connection Test
# =========================================================================


class TestConnectionTest:
    """Test JiraClient.test_connection."""

    async def test_successful_connection(self) -> None:
        client = _make_client()
        resp = _jira_response(
            json_data={
                "accountId": "abc123",
                "displayName": "ShieldOps Bot",
                "emailAddress": "bot@example.com",
            }
        )

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.test_connection()

        assert result["connected"] is True
        assert result["account_id"] == "abc123"
        assert result["display_name"] == "ShieldOps Bot"

    async def test_auth_failure(self) -> None:
        client = _make_client()
        resp = _jira_response(status_code=401, text="Bad credentials")

        ctx, mock = _patch_httpx_client(resp)
        with ctx as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(JiraAuthError):
                await client.test_connection()

    async def test_network_error(self) -> None:
        client = _make_client()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("shieldops.integrations.itsm.jira.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(httpx.ConnectError):
                await client.test_connection()


# =========================================================================
# Issue Parsing
# =========================================================================


class TestParseIssue:
    """Test JiraClient.parse_issue and ADF extraction."""

    def test_parses_full_issue(self) -> None:
        client = _make_client()
        raw = _issue_response(key="OPS-42").json()

        parsed = client.parse_issue(raw)

        assert isinstance(parsed, JiraIssue)
        assert parsed.key == "OPS-42"
        assert parsed.summary == "Test issue"
        assert parsed.status == "To Do"
        assert parsed.priority == "Medium"
        assert parsed.assignee == "Agent Bot"
        assert parsed.issue_type == "Bug"
        assert "shieldops" in parsed.labels
        assert parsed.description == "Some description"

    def test_parses_minimal_issue(self) -> None:
        client = _make_client()
        raw = {"key": "MIN-1", "fields": {"summary": "Minimal", "status": {"name": "Open"}}}

        parsed = client.parse_issue(raw)
        assert parsed.key == "MIN-1"
        assert parsed.assignee is None
        assert parsed.description == ""

    def test_parses_issue_without_assignee(self) -> None:
        client = _make_client()
        raw = {
            "key": "OPS-99",
            "fields": {
                "summary": "No assignee",
                "status": {"name": "To Do"},
                "priority": {"name": "Low"},
                "assignee": None,
            },
        }
        parsed = client.parse_issue(raw)
        assert parsed.assignee is None


# =========================================================================
# ADF Text Extraction
# =========================================================================


class TestExtractTextFromAdf:
    """Test the _extract_text_from_adf utility."""

    def test_extracts_simple_paragraph(self) -> None:
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hello world"}],
                }
            ],
        }
        assert _extract_text_from_adf(adf) == "Hello world"

    def test_extracts_multiple_paragraphs(self) -> None:
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "First"}],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Second"}],
                },
            ],
        }
        assert _extract_text_from_adf(adf) == "First Second"

    def test_returns_empty_for_none(self) -> None:
        assert _extract_text_from_adf(None) == ""

    def test_returns_empty_for_empty_dict(self) -> None:
        assert _extract_text_from_adf({}) == ""


# =========================================================================
# Priority Mapping
# =========================================================================


class TestPriorityMapping:
    """Verify default priority mappings."""

    def test_critical_maps_to_highest(self) -> None:
        assert DEFAULT_PRIORITY_TO_JIRA["critical"] == "Highest"

    def test_high_maps_to_high(self) -> None:
        assert DEFAULT_PRIORITY_TO_JIRA["high"] == "High"

    def test_medium_maps_to_medium(self) -> None:
        assert DEFAULT_PRIORITY_TO_JIRA["medium"] == "Medium"

    def test_low_maps_to_low(self) -> None:
        assert DEFAULT_PRIORITY_TO_JIRA["low"] == "Low"


# =========================================================================
# Status Mapping
# =========================================================================


class TestStatusMapping:
    """Verify default bidirectional status mappings."""

    def test_to_jira_mappings(self) -> None:
        assert DEFAULT_STATUS_TO_JIRA["open"] == "To Do"
        assert DEFAULT_STATUS_TO_JIRA["investigating"] == "In Progress"
        assert DEFAULT_STATUS_TO_JIRA["resolved"] == "Done"
        assert DEFAULT_STATUS_TO_JIRA["escalated"] == "In Review"

    def test_from_jira_mappings(self) -> None:
        assert DEFAULT_STATUS_FROM_JIRA["To Do"] == "open"
        assert DEFAULT_STATUS_FROM_JIRA["In Progress"] == "investigating"
        assert DEFAULT_STATUS_FROM_JIRA["Done"] == "resolved"
        assert DEFAULT_STATUS_FROM_JIRA["In Review"] == "escalated"

    def test_bidirectional_consistency(self) -> None:
        """Each to-jira mapping should have a matching from-jira mapping."""
        for shieldops_status, jira_status in DEFAULT_STATUS_TO_JIRA.items():
            assert DEFAULT_STATUS_FROM_JIRA[jira_status] == shieldops_status
