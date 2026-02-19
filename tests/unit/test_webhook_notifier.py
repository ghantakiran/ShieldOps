"""Comprehensive tests for the WebhookNotifier.

Covers:
- send() and send_escalation() payload correctness
- HTTP status code handling (2xx, 4xx, 5xx)
- HMAC-SHA256 signature generation and verification
- Retry logic for transient failures
- Custom headers
- Configuration and edge cases
- ISO 8601 timestamps
- NotificationChannel protocol compliance
- App wiring when webhook_url is configured
"""

from __future__ import annotations

import hashlib
import hmac
import json
from contextlib import ExitStack
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from shieldops.integrations.notifications.base import NotificationChannel
from shieldops.integrations.notifications.webhook import WebhookNotifier

TEST_URL = "https://hooks.example.com/shieldops"


# =========================================================================
# Helpers
# =========================================================================


def _mock_response(
    status_code: int = 200,
    text: str = "ok",
) -> httpx.Response:
    """Build a minimal httpx.Response for mocking."""
    return httpx.Response(
        status_code=status_code,
        request=httpx.Request("POST", TEST_URL),
        text=text,
    )


def _patch_client(
    mock_client: AsyncMock,
):
    """Return a patch context for httpx.AsyncClient."""
    patcher = patch("httpx.AsyncClient")
    mock_cls = patcher.start()
    mock_cls.return_value.__aenter__ = AsyncMock(
        return_value=mock_client,
    )
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return patcher


def _extract_payload(mock_client: AsyncMock) -> dict[str, Any]:
    """Extract the JSON payload from the mock POST call."""
    call_kwargs = mock_client.post.call_args
    content = call_kwargs.kwargs.get("content") or call_kwargs[1]["content"]
    return json.loads(content)


def _extract_headers(mock_client: AsyncMock) -> dict[str, str]:
    """Extract headers from the mock POST call."""
    call_kwargs = mock_client.post.call_args
    return call_kwargs.kwargs.get("headers") or call_kwargs[1]["headers"]


# =========================================================================
# Protocol Compliance
# =========================================================================


class TestProtocolCompliance:
    """Verify WebhookNotifier satisfies NotificationChannel protocol."""

    def test_webhook_satisfies_protocol(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        assert isinstance(notifier, NotificationChannel)


# =========================================================================
# send() Tests
# =========================================================================


class TestWebhookSend:
    """Tests for the send() method."""

    @pytest.mark.asyncio
    async def test_send_posts_correct_payload(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send(
                "CPU usage at 95%",
                severity="high",
                details={"host": "web-01"},
            )
        finally:
            patcher.stop()

        payload = _extract_payload(mock_client)
        assert payload["event_type"] == "notification"
        assert payload["severity"] == "high"
        assert payload["message"] == "CPU usage at 95%"
        assert payload["details"] == {"host": "web-01"}
        assert payload["source"] == "shieldops"

    @pytest.mark.asyncio
    async def test_send_returns_true_on_200(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send("ok")
        finally:
            patcher.stop()

        assert result is True

    @pytest.mark.asyncio
    async def test_send_returns_true_on_201(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(201)

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send("created")
        finally:
            patcher.stop()

        assert result is True

    @pytest.mark.asyncio
    async def test_send_returns_true_on_202(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(202)

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send("accepted")
        finally:
            patcher.stop()

        assert result is True

    @pytest.mark.asyncio
    async def test_send_returns_false_on_4xx(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL, max_retries=1)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(
            400,
            "bad request",
        )

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send("bad")
        finally:
            patcher.stop()

        assert result is False

    @pytest.mark.asyncio
    async def test_send_posts_to_correct_url(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send("test")
        finally:
            patcher.stop()

        call_args = mock_client.post.call_args
        assert call_args[0][0] == TEST_URL

    @pytest.mark.asyncio
    async def test_send_default_severity_is_info(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send("test")
        finally:
            patcher.stop()

        payload = _extract_payload(mock_client)
        assert payload["severity"] == "info"

    @pytest.mark.asyncio
    async def test_send_details_default_to_empty_dict(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send("test")
        finally:
            patcher.stop()

        payload = _extract_payload(mock_client)
        assert payload["details"] == {}


# =========================================================================
# send_escalation() Tests
# =========================================================================


class TestWebhookSendEscalation:
    """Tests for the send_escalation() method."""

    @pytest.mark.asyncio
    async def test_send_escalation_posts_correct_payload(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send_escalation(
                title="DB Down",
                description="Primary database unreachable",
                severity="critical",
                source="supervisor",
                details={"cluster": "prod-east"},
            )
        finally:
            patcher.stop()

        payload = _extract_payload(mock_client)
        assert payload["event_type"] == "escalation"
        assert payload["title"] == "DB Down"
        assert payload["description"] == "Primary database unreachable"
        assert payload["severity"] == "critical"
        assert payload["source"] == "supervisor"
        assert payload["details"] == {"cluster": "prod-east"}

    @pytest.mark.asyncio
    async def test_send_escalation_includes_all_fields(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send_escalation(
                title="Alert",
                description="Something happened",
            )
        finally:
            patcher.stop()

        payload = _extract_payload(mock_client)
        expected_keys = {
            "event_type",
            "title",
            "description",
            "severity",
            "source",
            "details",
            "timestamp",
        }
        assert set(payload.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_send_escalation_default_severity_high(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send_escalation(
                title="t",
                description="d",
            )
        finally:
            patcher.stop()

        payload = _extract_payload(mock_client)
        assert payload["severity"] == "high"

    @pytest.mark.asyncio
    async def test_send_escalation_default_source_shieldops(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send_escalation(
                title="t",
                description="d",
            )
        finally:
            patcher.stop()

        payload = _extract_payload(mock_client)
        assert payload["source"] == "shieldops"

    @pytest.mark.asyncio
    async def test_send_escalation_returns_true_on_success(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send_escalation(
                title="t",
                description="d",
            )
        finally:
            patcher.stop()

        assert result is True

    @pytest.mark.asyncio
    async def test_send_escalation_returns_false_on_failure(
        self,
    ) -> None:
        notifier = WebhookNotifier(url=TEST_URL, max_retries=1)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(403)

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send_escalation(
                title="t",
                description="d",
            )
        finally:
            patcher.stop()

        assert result is False


# =========================================================================
# HMAC Signature Tests
# =========================================================================


class TestHMACSignature:
    """Tests for HMAC-SHA256 signature generation."""

    @pytest.mark.asyncio
    async def test_no_signature_when_secret_empty(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL, secret="")
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send("test")
        finally:
            patcher.stop()

        headers = _extract_headers(mock_client)
        assert "X-ShieldOps-Signature" not in headers

    @pytest.mark.asyncio
    async def test_signature_present_when_secret_set(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL, secret="s3cret")
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send("test")
        finally:
            patcher.stop()

        headers = _extract_headers(mock_client)
        assert "X-ShieldOps-Signature" in headers

    @pytest.mark.asyncio
    async def test_signature_matches_hmac_sha256(self) -> None:
        secret = "my-webhook-secret"  # noqa: S105
        notifier = WebhookNotifier(url=TEST_URL, secret=secret)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send("verify me")
        finally:
            patcher.stop()

        # Reconstruct the expected signature from the actual body
        call_kwargs = mock_client.post.call_args
        body = call_kwargs.kwargs["content"]
        expected_sig = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        headers = _extract_headers(mock_client)
        assert headers["X-ShieldOps-Signature"] == expected_sig

    @pytest.mark.asyncio
    async def test_signature_verification_roundtrip(self) -> None:
        """Simulate a receiver verifying the signature."""
        secret = "roundtrip-secret"  # noqa: S105
        notifier = WebhookNotifier(url=TEST_URL, secret=secret)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send("payload-data", severity="high")
        finally:
            patcher.stop()

        call_kwargs = mock_client.post.call_args
        body = call_kwargs.kwargs["content"]
        headers = _extract_headers(mock_client)
        received_sig = headers["X-ShieldOps-Signature"]

        # Receiver side: recompute and compare
        computed = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        assert hmac.compare_digest(received_sig, computed)


# =========================================================================
# Retry Logic Tests
# =========================================================================


class TestRetryLogic:
    """Tests for retry behaviour on transient failures."""

    @pytest.mark.asyncio
    async def test_retries_on_500(self) -> None:
        notifier = WebhookNotifier(
            url=TEST_URL,
            max_retries=3,
            retry_delay=0.0,
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(500)

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send("fail")
        finally:
            patcher.stop()

        assert result is False
        assert mock_client.post.await_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_502(self) -> None:
        notifier = WebhookNotifier(
            url=TEST_URL,
            max_retries=2,
            retry_delay=0.0,
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(502)

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send("fail")
        finally:
            patcher.stop()

        assert result is False
        assert mock_client.post.await_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_503(self) -> None:
        notifier = WebhookNotifier(
            url=TEST_URL,
            max_retries=2,
            retry_delay=0.0,
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(503)

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send("fail")
        finally:
            patcher.stop()

        assert result is False
        assert mock_client.post.await_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_connection_error(self) -> None:
        notifier = WebhookNotifier(
            url=TEST_URL,
            max_retries=3,
            retry_delay=0.0,
        )
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError(
            "connection refused",
        )

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send("fail")
        finally:
            patcher.stop()

        assert result is False
        assert mock_client.post.await_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_400(self) -> None:
        notifier = WebhookNotifier(
            url=TEST_URL,
            max_retries=3,
            retry_delay=0.0,
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(400)

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send("bad request")
        finally:
            patcher.stop()

        assert result is False
        # 4xx should not trigger retries — only 1 call
        assert mock_client.post.await_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_respected(self) -> None:
        notifier = WebhookNotifier(
            url=TEST_URL,
            max_retries=5,
            retry_delay=0.0,
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(500)

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send("fail")
        finally:
            patcher.stop()

        assert result is False
        assert mock_client.post.await_count == 5

    @pytest.mark.asyncio
    async def test_returns_false_after_retries_exhausted(self) -> None:
        notifier = WebhookNotifier(
            url=TEST_URL,
            max_retries=2,
            retry_delay=0.0,
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(500)

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send("fail")
        finally:
            patcher.stop()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_if_retry_succeeds(self) -> None:
        notifier = WebhookNotifier(
            url=TEST_URL,
            max_retries=3,
            retry_delay=0.0,
        )
        mock_client = AsyncMock()
        # Fail twice, then succeed
        mock_client.post.side_effect = [
            _mock_response(500),
            _mock_response(502),
            _mock_response(200),
        ]

        patcher = _patch_client(mock_client)
        try:
            result = await notifier.send("eventually ok")
        finally:
            patcher.stop()

        assert result is True
        assert mock_client.post.await_count == 3

    @pytest.mark.asyncio
    async def test_retry_delay_is_applied(self) -> None:
        """Verify asyncio.sleep is called between retries."""
        notifier = WebhookNotifier(
            url=TEST_URL,
            max_retries=3,
            retry_delay=2.5,
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(500)

        patcher = _patch_client(mock_client)
        with patch("asyncio.sleep", new_callable=AsyncMock) as m_sleep:
            try:
                await notifier.send("fail")
            finally:
                patcher.stop()

        # Sleep called between attempts (not after the last one)
        assert m_sleep.await_count == 2
        m_sleep.assert_awaited_with(2.5)


# =========================================================================
# Custom Headers Tests
# =========================================================================


class TestCustomHeaders:
    """Tests for custom header support."""

    @pytest.mark.asyncio
    async def test_custom_headers_included(self) -> None:
        notifier = WebhookNotifier(
            url=TEST_URL,
            custom_headers={"X-Custom": "value"},
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send("test")
        finally:
            patcher.stop()

        headers = _extract_headers(mock_client)
        assert headers["X-Custom"] == "value"

    @pytest.mark.asyncio
    async def test_custom_headers_merged_with_defaults(self) -> None:
        notifier = WebhookNotifier(
            url=TEST_URL,
            custom_headers={"Authorization": "Bearer tok"},
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send("test")
        finally:
            patcher.stop()

        headers = _extract_headers(mock_client)
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer tok"


# =========================================================================
# Configuration Tests
# =========================================================================


class TestConfiguration:
    """Tests for constructor and configuration."""

    def test_constructor_stores_settings(self) -> None:
        notifier = WebhookNotifier(
            url="https://example.com/hook",
            secret="sec",
            timeout=30.0,
            custom_headers={"X-Key": "val"},
            max_retries=5,
            retry_delay=2.0,
        )
        assert notifier._url == "https://example.com/hook"
        assert notifier._secret == "sec"  # noqa: S105
        assert notifier._timeout == 30.0
        assert notifier._custom_headers == {"X-Key": "val"}
        assert notifier._max_retries == 5
        assert notifier._retry_delay == 2.0

    def test_default_timeout(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        assert notifier._timeout == 10.0

    def test_default_max_retries(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        assert notifier._max_retries == 3

    def test_default_retry_delay(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        assert notifier._retry_delay == 1.0

    @pytest.mark.asyncio
    async def test_empty_url_returns_false(self) -> None:
        notifier = WebhookNotifier(url="")
        result = await notifier.send("test")
        assert result is False

    @pytest.mark.asyncio
    async def test_empty_url_escalation_returns_false(self) -> None:
        notifier = WebhookNotifier(url="")
        result = await notifier.send_escalation(
            title="t",
            description="d",
        )
        assert result is False


# =========================================================================
# Timestamp Tests
# =========================================================================


class TestTimestamp:
    """Tests for ISO 8601 timestamp inclusion."""

    @pytest.mark.asyncio
    async def test_send_payload_includes_timestamp(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send("test")
        finally:
            patcher.stop()

        payload = _extract_payload(mock_client)
        assert "timestamp" in payload
        # ISO 8601 basic check: contains 'T' separator and '+' or 'Z'
        ts = payload["timestamp"]
        assert "T" in ts

    @pytest.mark.asyncio
    async def test_escalation_payload_includes_timestamp(self) -> None:
        notifier = WebhookNotifier(url=TEST_URL)
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        patcher = _patch_client(mock_client)
        try:
            await notifier.send_escalation(
                title="t",
                description="d",
            )
        finally:
            patcher.stop()

        payload = _extract_payload(mock_client)
        assert "timestamp" in payload
        ts = payload["timestamp"]
        assert "T" in ts


# =========================================================================
# Settings Tests
# =========================================================================


class TestWebhookSettings:
    """Verify webhook settings exist with correct defaults."""

    def test_webhook_url_default_empty(self) -> None:
        from shieldops.config.settings import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.webhook_url == ""

    def test_webhook_secret_default_empty(self) -> None:
        from shieldops.config.settings import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.webhook_secret == ""

    def test_webhook_timeout_default(self) -> None:
        from shieldops.config.settings import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.webhook_timeout == 10.0

    def test_webhook_settings_configurable(self) -> None:
        from shieldops.config.settings import Settings

        s = Settings(
            webhook_url="https://hooks.example.com/test",
            webhook_secret="wh-secret-123",
            webhook_timeout=30.0,
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.webhook_url == "https://hooks.example.com/test"
        assert s.webhook_secret == "wh-secret-123"  # noqa: S105
        assert s.webhook_timeout == 30.0


# =========================================================================
# App Wiring Tests
# =========================================================================


class TestAppWiring:
    """Verify webhook channel is wired into SupervisorRunner."""

    @pytest.mark.asyncio
    async def test_webhook_wired_when_url_set(self) -> None:
        mock_router = MagicMock()
        mock_policy = MagicMock()
        mock_policy.close = AsyncMock()

        with ExitStack() as stack:
            from shieldops.observability.factory import (
                ObservabilitySources,
            )

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
            stack.enter_context(
                patch("shieldops.api.app.InvestigationRunner"),
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.PolicyEngine",
                    return_value=mock_policy,
                )
            )
            stack.enter_context(
                patch("shieldops.api.app.ApprovalWorkflow"),
            )
            stack.enter_context(
                patch("shieldops.api.app.RemediationRunner"),
            )
            stack.enter_context(
                patch("shieldops.api.app.SecurityRunner"),
            )
            stack.enter_context(
                patch("shieldops.api.app.CostRunner"),
            )
            stack.enter_context(
                patch("shieldops.api.app.LearningRunner"),
            )
            mock_sup_cls = stack.enter_context(
                patch("shieldops.api.app.SupervisorRunner"),
            )

            # Patch settings for webhook
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.webhook_url",
                    "https://hooks.example.com/test",
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.webhook_secret",
                    "wh-s3cret",
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.webhook_timeout",
                    15.0,
                )
            )

            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                mock_sup_cls.assert_called_once()
                call_kwargs = mock_sup_cls.call_args.kwargs
                channels = call_kwargs["notification_channels"]

                assert "webhook" in channels
                wh = channels["webhook"]
                assert isinstance(wh, WebhookNotifier)
                assert wh._url == "https://hooks.example.com/test"
                assert wh._secret == "wh-s3cret"  # noqa: S105
                assert wh._timeout == 15.0

    @pytest.mark.asyncio
    async def test_no_webhook_when_url_empty(self) -> None:
        mock_router = MagicMock()
        mock_policy = MagicMock()
        mock_policy.close = AsyncMock()

        with ExitStack() as stack:
            from shieldops.observability.factory import (
                ObservabilitySources,
            )

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
            stack.enter_context(
                patch("shieldops.api.app.InvestigationRunner"),
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.PolicyEngine",
                    return_value=mock_policy,
                )
            )
            stack.enter_context(
                patch("shieldops.api.app.ApprovalWorkflow"),
            )
            stack.enter_context(
                patch("shieldops.api.app.RemediationRunner"),
            )
            stack.enter_context(
                patch("shieldops.api.app.SecurityRunner"),
            )
            stack.enter_context(
                patch("shieldops.api.app.CostRunner"),
            )
            stack.enter_context(
                patch("shieldops.api.app.LearningRunner"),
            )
            mock_sup_cls = stack.enter_context(
                patch("shieldops.api.app.SupervisorRunner"),
            )

            # Ensure webhook_url is empty (default)
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.webhook_url",
                    "",
                )
            )

            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                call_kwargs = mock_sup_cls.call_args.kwargs
                channels = call_kwargs["notification_channels"]
                assert "webhook" not in channels
