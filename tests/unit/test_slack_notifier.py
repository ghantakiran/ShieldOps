"""Comprehensive tests for the Slack notification channel.

Covers:
- SlackNotifier: send, send_escalation, Block Kit layout, severity emoji,
  message truncation, auth headers, HTTP errors, error responses
- NotificationChannel protocol compliance
- App wiring: Slack channel registered when bot_token is set
"""

from contextlib import ExitStack
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from shieldops.integrations.notifications.base import NotificationChannel
from shieldops.integrations.notifications.slack import (
    _SLACK_TEXT_LIMIT,
    SLACK_POST_MESSAGE_URL,
    SlackNotifier,
)

# =========================================================================
# Helpers
# =========================================================================


def _slack_response(
    ok: bool = True,
    error: str | None = None,
) -> httpx.Response:
    """Build a minimal httpx.Response mimicking Slack's JSON envelope."""
    body: dict[str, Any] = {"ok": ok}
    if error:
        body["error"] = error
    return httpx.Response(
        status_code=200,
        request=httpx.Request("POST", SLACK_POST_MESSAGE_URL),
        json=body,
    )


def _extract_payload(mock_client: AsyncMock) -> dict[str, Any]:
    """Pull the JSON payload from the most recent mock post call."""
    call_kwargs = mock_client.post.call_args
    return call_kwargs.kwargs.get("json") or call_kwargs[1]["json"]


def _extract_headers(mock_client: AsyncMock) -> dict[str, str]:
    """Pull headers from the most recent mock post call."""
    call_kwargs = mock_client.post.call_args
    return call_kwargs.kwargs.get("headers") or call_kwargs[1]["headers"]


def _patch_httpx(mock_client: AsyncMock):
    """Return a context manager that patches httpx.AsyncClient."""
    ctx = patch("httpx.AsyncClient")
    mock_cls = ctx.__enter__()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return ctx, mock_cls


# =========================================================================
# Constructor Tests
# =========================================================================


class TestSlackNotifierConstructor:
    """Verify constructor stores parameters correctly."""

    def test_stores_bot_token(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-test-token")
        assert notifier._bot_token == "xoxb-test-token"  # noqa: S105

    def test_default_channel(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        assert notifier._default_channel == "#shieldops-alerts"

    def test_custom_channel(self) -> None:
        notifier = SlackNotifier(
            bot_token="xoxb-tok",
            default_channel="#incidents",
        )
        assert notifier._default_channel == "#incidents"

    def test_default_timeout(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        assert notifier._timeout == 10.0

    def test_custom_timeout(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok", timeout=30.0)
        assert notifier._timeout == 30.0


# =========================================================================
# Protocol Compliance
# =========================================================================


class TestSlackNotifierProtocol:
    """Verify SlackNotifier satisfies the NotificationChannel protocol."""

    def test_satisfies_protocol(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        assert isinstance(notifier, NotificationChannel)


# =========================================================================
# send() Tests
# =========================================================================


class TestSlackNotifierSend:
    """Tests for the send() method."""

    @pytest.mark.asyncio
    async def test_posts_to_correct_url(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-123")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send("test message")

        url = mock_client.post.call_args[0][0]
        assert url == SLACK_POST_MESSAGE_URL

    @pytest.mark.asyncio
    async def test_auth_header_set(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-secret")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send("hello")

        headers = _extract_headers(mock_client)
        assert headers["Authorization"] == "Bearer xoxb-secret"
        assert "application/json" in headers["Content-Type"]

    @pytest.mark.asyncio
    async def test_returns_true_on_ok(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send("success")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_error_response(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(
            ok=False,
            error="channel_not_found",
        )

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send("oops")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_http_error(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError(
            "connection refused",
        )

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send("fail")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_unexpected_exception(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.side_effect = RuntimeError("boom")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send("fail")

        assert result is False

    @pytest.mark.asyncio
    async def test_sends_to_default_channel(self) -> None:
        notifier = SlackNotifier(
            bot_token="xoxb-tok",
            default_channel="#my-alerts",
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send("check channel")

        payload = _extract_payload(mock_client)
        assert payload["channel"] == "#my-alerts"

    @pytest.mark.asyncio
    async def test_severity_emoji_critical(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send("CPU meltdown", severity="critical")

        payload = _extract_payload(mock_client)
        block_text = payload["blocks"][0]["text"]["text"]
        assert "\U0001f534" in block_text  # red circle
        assert "[CRITICAL]" in block_text

    @pytest.mark.asyncio
    async def test_severity_emoji_high(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send("disk full", severity="high")

        payload = _extract_payload(mock_client)
        block_text = payload["blocks"][0]["text"]["text"]
        assert "\U0001f7e0" in block_text  # orange circle

    @pytest.mark.asyncio
    async def test_severity_emoji_warning(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send("high latency", severity="warning")

        payload = _extract_payload(mock_client)
        block_text = payload["blocks"][0]["text"]["text"]
        assert "\U0001f7e1" in block_text  # yellow circle

    @pytest.mark.asyncio
    async def test_severity_emoji_info(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send("deploy complete", severity="info")

        payload = _extract_payload(mock_client)
        block_text = payload["blocks"][0]["text"]["text"]
        assert "\U0001f535" in block_text  # blue circle

    @pytest.mark.asyncio
    async def test_severity_emoji_unknown_defaults_to_blue(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send("something", severity="unknown")

        payload = _extract_payload(mock_client)
        block_text = payload["blocks"][0]["text"]["text"]
        assert "\U0001f535" in block_text  # blue circle (default)

    @pytest.mark.asyncio
    async def test_truncates_long_message(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)
        long_msg = "x" * 5000

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send(long_msg)

        payload = _extract_payload(mock_client)
        # The block text includes emoji + severity prefix, but the
        # truncated message portion should be at most _SLACK_TEXT_LIMIT.
        block_text = payload["blocks"][0]["text"]["text"]
        assert len(block_text) < _SLACK_TEXT_LIMIT + 100  # prefix overhead
        # Fallback text should also be truncated
        assert len(payload["text"]) <= _SLACK_TEXT_LIMIT

    @pytest.mark.asyncio
    async def test_includes_details_as_code_block(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send(
                "alert fired",
                details={"host": "web-01", "cpu": 95},
            )

        payload = _extract_payload(mock_client)
        assert len(payload["blocks"]) == 2
        detail_block = payload["blocks"][1]
        assert detail_block["type"] == "section"
        assert "```" in detail_block["text"]["text"]
        assert "web-01" in detail_block["text"]["text"]

    @pytest.mark.asyncio
    async def test_no_detail_block_when_details_none(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send("clean message", details=None)

        payload = _extract_payload(mock_client)
        assert len(payload["blocks"]) == 1

    @pytest.mark.asyncio
    async def test_no_detail_block_when_details_empty(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send("clean message", details={})

        payload = _extract_payload(mock_client)
        # Empty dict is falsy, so no detail block appended
        assert len(payload["blocks"]) == 1

    @pytest.mark.asyncio
    async def test_blocks_have_correct_structure(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send("structured test")

        payload = _extract_payload(mock_client)
        block = payload["blocks"][0]
        assert block["type"] == "section"
        assert block["text"]["type"] == "mrkdwn"


# =========================================================================
# send_escalation() Tests
# =========================================================================


class TestSlackNotifierSendEscalation:
    """Tests for the send_escalation() method."""

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send_escalation(
                title="DB down",
                description="Primary unreachable",
                severity="critical",
                source="supervisor",
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_error(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(
            ok=False,
            error="not_authed",
        )

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send_escalation(
                title="Incident",
                description="bad",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_header_block_contains_title(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send_escalation(
                title="DB Down",
                description="Primary unreachable",
            )

        payload = _extract_payload(mock_client)
        header = payload["blocks"][0]
        assert header["type"] == "header"
        assert header["text"]["text"] == "DB Down"

    @pytest.mark.asyncio
    async def test_description_block(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send_escalation(
                title="Outage",
                description="Region us-east-1 is down",
            )

        payload = _extract_payload(mock_client)
        section = payload["blocks"][1]
        assert section["type"] == "section"
        assert "us-east-1" in section["text"]["text"]

    @pytest.mark.asyncio
    async def test_context_block_has_severity_and_source(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send_escalation(
                title="Alert",
                description="something",
                severity="critical",
                source="remediation-agent",
            )

        payload = _extract_payload(mock_client)
        context = payload["blocks"][2]
        assert context["type"] == "context"
        text = context["elements"][0]["text"]
        assert "CRITICAL" in text
        assert "remediation-agent" in text

    @pytest.mark.asyncio
    async def test_details_rendered_as_fields(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send_escalation(
                title="Alert",
                description="issue",
                details={"cluster": "prod-east", "region": "us-east-1"},
            )

        payload = _extract_payload(mock_client)
        # 4 blocks: header, section, context, fields-section
        assert len(payload["blocks"]) == 4
        fields_block = payload["blocks"][3]
        assert fields_block["type"] == "section"
        field_texts = [f["text"] for f in fields_block["fields"]]
        assert any("cluster" in t for t in field_texts)
        assert any("prod-east" in t for t in field_texts)
        assert any("region" in t for t in field_texts)

    @pytest.mark.asyncio
    async def test_no_fields_block_when_details_none(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send_escalation(
                title="Alert",
                description="desc",
                details=None,
            )

        payload = _extract_payload(mock_client)
        # Only 3 blocks: header, section, context
        assert len(payload["blocks"]) == 3

    @pytest.mark.asyncio
    async def test_no_fields_block_when_details_empty(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send_escalation(
                title="Alert",
                description="desc",
                details={},
            )

        payload = _extract_payload(mock_client)
        assert len(payload["blocks"]) == 3

    @pytest.mark.asyncio
    async def test_default_severity_and_source(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send_escalation(
                title="Alert",
                description="something happened",
            )

        payload = _extract_payload(mock_client)
        context_text = payload["blocks"][2]["elements"][0]["text"]
        assert "HIGH" in context_text
        assert "shieldops" in context_text

    @pytest.mark.asyncio
    async def test_escalation_http_error(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timed out")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send_escalation(
                title="Alert",
                description="fail",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_fallback_text_included(self) -> None:
        """Slack requires a 'text' field for fallback in notifications."""
        notifier = SlackNotifier(bot_token="xoxb-tok")
        mock_client = AsyncMock()
        mock_client.post.return_value = _slack_response(ok=True)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send_escalation(
                title="DB Down",
                description="Primary unreachable",
                severity="critical",
            )

        payload = _extract_payload(mock_client)
        assert "text" in payload
        assert "DB Down" in payload["text"]


# =========================================================================
# Severity Emoji Mapping
# =========================================================================


class TestSeverityEmoji:
    """Verify the static severity-to-emoji mapping."""

    def test_critical(self) -> None:
        assert SlackNotifier._severity_emoji("critical") == "\U0001f534"

    def test_high(self) -> None:
        assert SlackNotifier._severity_emoji("high") == "\U0001f7e0"

    def test_warning(self) -> None:
        assert SlackNotifier._severity_emoji("warning") == "\U0001f7e1"

    def test_info(self) -> None:
        assert SlackNotifier._severity_emoji("info") == "\U0001f535"

    def test_case_insensitive(self) -> None:
        assert SlackNotifier._severity_emoji("CRITICAL") == "\U0001f534"
        assert SlackNotifier._severity_emoji("High") == "\U0001f7e0"

    def test_unknown_defaults_to_blue(self) -> None:
        assert SlackNotifier._severity_emoji("banana") == "\U0001f535"


# =========================================================================
# App Wiring Tests
# =========================================================================


class TestSlackAppWiring:
    """Verify Slack channel is wired into SupervisorRunner via lifespan."""

    @pytest.mark.asyncio
    async def test_slack_wired_when_token_set(self) -> None:
        """When slack_bot_token is set, notification_channels should
        contain a 'slack' entry with a SlackNotifier."""
        mock_router = MagicMock()
        mock_policy = MagicMock()
        mock_policy.close = AsyncMock()

        with ExitStack() as stack:
            from shieldops.observability.factory import ObservabilitySources

            stack.enter_context(
                patch(
                    "shieldops.api.app.create_observability_sources",
                    return_value=ObservabilitySources(),
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.create_connector_router",
                    return_value=mock_router,
                )
            )
            stack.enter_context(patch("shieldops.api.app.InvestigationRunner"))
            stack.enter_context(
                patch(
                    "shieldops.api.app.PolicyEngine",
                    return_value=mock_policy,
                )
            )
            stack.enter_context(patch("shieldops.api.app.ApprovalWorkflow"))
            stack.enter_context(patch("shieldops.api.app.RemediationRunner"))
            stack.enter_context(patch("shieldops.api.app.SecurityRunner"))
            stack.enter_context(patch("shieldops.api.app.CostRunner"))
            stack.enter_context(patch("shieldops.api.app.LearningRunner"))
            mock_sup_cls = stack.enter_context(patch("shieldops.api.app.SupervisorRunner"))

            # Set slack token, clear PD key so only slack is wired
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.pagerduty_routing_key",
                    "",
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.slack_bot_token",
                    "xoxb-test-token",
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.slack_approval_channel",
                    "#test-channel",
                )
            )

            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                mock_sup_cls.assert_called_once()
                call_kwargs = mock_sup_cls.call_args.kwargs
                channels = call_kwargs["notification_channels"]

                assert "slack" in channels
                assert isinstance(channels["slack"], SlackNotifier)
                assert channels["slack"]._default_channel == ("#test-channel")

    @pytest.mark.asyncio
    async def test_no_slack_when_token_empty(self) -> None:
        """When slack_bot_token is empty, no Slack channel is registered."""
        mock_router = MagicMock()
        mock_policy = MagicMock()
        mock_policy.close = AsyncMock()

        with ExitStack() as stack:
            from shieldops.observability.factory import ObservabilitySources

            stack.enter_context(
                patch(
                    "shieldops.api.app.create_observability_sources",
                    return_value=ObservabilitySources(),
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.create_connector_router",
                    return_value=mock_router,
                )
            )
            stack.enter_context(patch("shieldops.api.app.InvestigationRunner"))
            stack.enter_context(
                patch(
                    "shieldops.api.app.PolicyEngine",
                    return_value=mock_policy,
                )
            )
            stack.enter_context(patch("shieldops.api.app.ApprovalWorkflow"))
            stack.enter_context(patch("shieldops.api.app.RemediationRunner"))
            stack.enter_context(patch("shieldops.api.app.SecurityRunner"))
            stack.enter_context(patch("shieldops.api.app.CostRunner"))
            stack.enter_context(patch("shieldops.api.app.LearningRunner"))
            mock_sup_cls = stack.enter_context(patch("shieldops.api.app.SupervisorRunner"))

            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.pagerduty_routing_key",
                    "",
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.slack_bot_token",
                    "",
                )
            )

            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                call_kwargs = mock_sup_cls.call_args.kwargs
                channels = call_kwargs["notification_channels"]
                assert "slack" not in channels
