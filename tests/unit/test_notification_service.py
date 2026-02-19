"""Comprehensive tests for the notification service.

Covers:
- PagerDutyNotifier: send, send_escalation, severity mapping, HTTP errors, timeouts
- NotificationDispatcher: register, unregister, send, send_escalation, broadcast,
  missing channel, concurrent broadcast
- NotificationChannel: protocol compliance
- App wiring: PagerDuty channel registered when routing_key is set
"""

from contextlib import ExitStack
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from shieldops.integrations.notifications.base import NotificationChannel
from shieldops.integrations.notifications.dispatcher import NotificationDispatcher
from shieldops.integrations.notifications.pagerduty import (
    _PD_SUMMARY_LIMIT,
    PAGERDUTY_EVENTS_URL,
    PagerDutyNotifier,
)

# =========================================================================
# Helpers
# =========================================================================


def _mock_response(status_code: int = 202, text: str = "ok") -> httpx.Response:
    """Build a minimal httpx.Response for mocking."""
    resp = httpx.Response(
        status_code=status_code,
        request=httpx.Request("POST", PAGERDUTY_EVENTS_URL),
        text=text,
    )
    return resp


class _FakeChannel:
    """Concrete class that satisfies NotificationChannel protocol."""

    def __init__(self, succeed: bool = True) -> None:
        self._succeed = succeed
        self.send_calls: list[dict[str, Any]] = []
        self.escalation_calls: list[dict[str, Any]] = []

    async def send(
        self,
        message: str,
        severity: str = "info",
        details: dict[str, Any] | None = None,
    ) -> bool:
        self.send_calls.append({"message": message, "severity": severity, "details": details})
        return self._succeed

    async def send_escalation(
        self,
        title: str,
        description: str,
        severity: str = "high",
        source: str = "shieldops",
        details: dict[str, Any] | None = None,
    ) -> bool:
        self.escalation_calls.append(
            {
                "title": title,
                "description": description,
                "severity": severity,
                "source": source,
                "details": details,
            }
        )
        return self._succeed


# =========================================================================
# NotificationChannel Protocol Tests
# =========================================================================


class TestNotificationChannelProtocol:
    """Verify that protocol compliance works at runtime."""

    def test_fake_channel_satisfies_protocol(self) -> None:
        ch = _FakeChannel()
        assert isinstance(ch, NotificationChannel)

    def test_pagerduty_satisfies_protocol(self) -> None:
        pd = PagerDutyNotifier(routing_key="test-key")
        assert isinstance(pd, NotificationChannel)

    def test_dict_does_not_satisfy_protocol(self) -> None:
        assert not isinstance({}, NotificationChannel)

    def test_partial_impl_does_not_satisfy(self) -> None:
        """A class with only send() should not match the two-method protocol."""

        class _OnlySend:
            async def send(self, message: str, **kw: Any) -> bool:
                return True

        assert not isinstance(_OnlySend(), NotificationChannel)


# =========================================================================
# PagerDutyNotifier Tests
# =========================================================================


class TestPagerDutyNotifier:
    """Tests for PagerDutyNotifier."""

    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        notifier = PagerDutyNotifier(routing_key="R123")
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(202)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send("CPU high", severity="high")

        assert result is True
        mock_client.post.assert_awaited_once()
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1]["json"]
        assert payload["routing_key"] == "R123"
        assert payload["event_action"] == "trigger"
        assert payload["payload"]["severity"] == "error"  # high -> error

    @pytest.mark.asyncio
    async def test_send_failure_status(self) -> None:
        notifier = PagerDutyNotifier(routing_key="R123")
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(400, "bad request")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send("oops")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_http_error(self) -> None:
        notifier = PagerDutyNotifier(routing_key="R123")
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("connection refused")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send("fail")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_unexpected_exception(self) -> None:
        notifier = PagerDutyNotifier(routing_key="R123")
        mock_client = AsyncMock()
        mock_client.post.side_effect = RuntimeError("boom")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send("fail")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_escalation_success(self) -> None:
        notifier = PagerDutyNotifier(routing_key="R-esc")
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send_escalation(
                title="DB down",
                description="Primary database unreachable",
                severity="critical",
                source="supervisor",
                details={"cluster": "prod-east"},
            )

        assert result is True
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["payload"]["severity"] == "critical"
        assert payload["payload"]["source"] == "supervisor"
        assert payload["payload"]["custom_details"]["description"] == (
            "Primary database unreachable"
        )
        assert payload["payload"]["custom_details"]["cluster"] == "prod-east"

    @pytest.mark.asyncio
    async def test_send_escalation_failure(self) -> None:
        notifier = PagerDutyNotifier(routing_key="R-esc")
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(500, "server error")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send_escalation(title="DB down", description="unreachable")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_escalation_no_details(self) -> None:
        """Escalation without extra details should still include description."""
        notifier = PagerDutyNotifier(routing_key="R-esc")
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(202)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await notifier.send_escalation(title="disk full", description="90% used")

        assert result is True
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["payload"]["custom_details"] == {"description": "90% used"}

    @pytest.mark.asyncio
    async def test_summary_truncated_to_pd_limit(self) -> None:
        """Summaries longer than 1024 chars must be truncated."""
        notifier = PagerDutyNotifier(routing_key="R123")
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(202)
        long_msg = "x" * 2000

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send(long_msg)

        payload = mock_client.post.call_args.kwargs["json"]
        assert len(payload["payload"]["summary"]) == _PD_SUMMARY_LIMIT

    def test_severity_mapping(self) -> None:
        assert PagerDutyNotifier._map_severity("low") == "info"
        assert PagerDutyNotifier._map_severity("info") == "info"
        assert PagerDutyNotifier._map_severity("medium") == "warning"
        assert PagerDutyNotifier._map_severity("warning") == "warning"
        assert PagerDutyNotifier._map_severity("high") == "error"
        assert PagerDutyNotifier._map_severity("critical") == "critical"
        assert PagerDutyNotifier._map_severity("CRITICAL") == "critical"
        assert PagerDutyNotifier._map_severity("unknown") == "warning"

    def test_custom_timeout(self) -> None:
        notifier = PagerDutyNotifier(routing_key="R", timeout=30.0)
        assert notifier._timeout == 30.0

    @pytest.mark.asyncio
    async def test_send_posts_to_correct_url(self) -> None:
        notifier = PagerDutyNotifier(routing_key="R123")
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(202)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await notifier.send("test")

        call_args = mock_client.post.call_args
        assert call_args[0][0] == PAGERDUTY_EVENTS_URL


# =========================================================================
# NotificationDispatcher Tests
# =========================================================================


class TestNotificationDispatcher:
    """Tests for NotificationDispatcher."""

    def test_register_channel(self) -> None:
        dispatcher = NotificationDispatcher()
        ch = _FakeChannel()
        dispatcher.register("slack", ch)
        assert "slack" in dispatcher.channels

    def test_register_multiple_channels(self) -> None:
        dispatcher = NotificationDispatcher()
        dispatcher.register("slack", _FakeChannel())
        dispatcher.register("pagerduty", _FakeChannel())
        assert sorted(dispatcher.channels) == ["pagerduty", "slack"]

    def test_unregister_channel(self) -> None:
        dispatcher = NotificationDispatcher()
        dispatcher.register("slack", _FakeChannel())
        assert dispatcher.unregister("slack") is True
        assert dispatcher.channels == []

    def test_unregister_nonexistent(self) -> None:
        dispatcher = NotificationDispatcher()
        assert dispatcher.unregister("ghost") is False

    def test_channels_empty_by_default(self) -> None:
        dispatcher = NotificationDispatcher()
        assert dispatcher.channels == []

    @pytest.mark.asyncio
    async def test_send_to_registered_channel(self) -> None:
        dispatcher = NotificationDispatcher()
        ch = _FakeChannel()
        dispatcher.register("slack", ch)

        result = await dispatcher.send("slack", "hello", severity="high", details={"k": "v"})

        assert result is True
        assert len(ch.send_calls) == 1
        assert ch.send_calls[0]["message"] == "hello"
        assert ch.send_calls[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_send_to_missing_channel(self) -> None:
        dispatcher = NotificationDispatcher()
        result = await dispatcher.send("nonexistent", "msg")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_escalation_to_registered(self) -> None:
        dispatcher = NotificationDispatcher()
        ch = _FakeChannel()
        dispatcher.register("pagerduty", ch)

        result = await dispatcher.send_escalation(
            channel="pagerduty",
            title="DB Down",
            description="Primary unreachable",
            severity="critical",
            source="supervisor",
            details={"region": "us-east-1"},
        )

        assert result is True
        assert len(ch.escalation_calls) == 1
        call = ch.escalation_calls[0]
        assert call["title"] == "DB Down"
        assert call["description"] == "Primary unreachable"
        assert call["severity"] == "critical"
        assert call["source"] == "supervisor"
        assert call["details"]["region"] == "us-east-1"

    @pytest.mark.asyncio
    async def test_send_escalation_to_missing_channel(self) -> None:
        dispatcher = NotificationDispatcher()
        result = await dispatcher.send_escalation(channel="ghost", title="t", description="d")
        assert result is False

    @pytest.mark.asyncio
    async def test_broadcast_all_succeed(self) -> None:
        dispatcher = NotificationDispatcher()
        ch1 = _FakeChannel(succeed=True)
        ch2 = _FakeChannel(succeed=True)
        dispatcher.register("slack", ch1)
        dispatcher.register("pagerduty", ch2)

        results = await dispatcher.broadcast("alert fired", severity="high")

        assert results == {"slack": True, "pagerduty": True}
        assert len(ch1.send_calls) == 1
        assert len(ch2.send_calls) == 1

    @pytest.mark.asyncio
    async def test_broadcast_partial_failure(self) -> None:
        dispatcher = NotificationDispatcher()
        ch_ok = _FakeChannel(succeed=True)
        ch_fail = _FakeChannel(succeed=False)
        dispatcher.register("ok_channel", ch_ok)
        dispatcher.register("fail_channel", ch_fail)

        results = await dispatcher.broadcast("test")

        assert results["ok_channel"] is True
        assert results["fail_channel"] is False

    @pytest.mark.asyncio
    async def test_broadcast_exception_in_channel(self) -> None:
        """A channel that raises should return False without crashing broadcast."""
        dispatcher = NotificationDispatcher()
        ch_ok = _FakeChannel(succeed=True)

        class _Exploding:
            async def send(self, **kw: Any) -> bool:
                raise RuntimeError("kaboom")

            async def send_escalation(self, **kw: Any) -> bool:
                return False

        dispatcher.register("ok", ch_ok)
        dispatcher.register("broken", _Exploding())

        results = await dispatcher.broadcast("test")

        assert results["ok"] is True
        assert results["broken"] is False

    @pytest.mark.asyncio
    async def test_broadcast_empty(self) -> None:
        dispatcher = NotificationDispatcher()
        results = await dispatcher.broadcast("no channels")
        assert results == {}

    @pytest.mark.asyncio
    async def test_send_with_details_none(self) -> None:
        dispatcher = NotificationDispatcher()
        ch = _FakeChannel()
        dispatcher.register("ch", ch)

        result = await dispatcher.send("ch", "msg", details=None)
        assert result is True
        assert ch.send_calls[0]["details"] is None

    @pytest.mark.asyncio
    async def test_send_escalation_default_params(self) -> None:
        """Ensure defaults (severity=high, source=shieldops) propagate."""
        dispatcher = NotificationDispatcher()
        ch = _FakeChannel()
        dispatcher.register("ch", ch)

        await dispatcher.send_escalation("ch", title="t", description="d")

        call = ch.escalation_calls[0]
        assert call["severity"] == "high"
        assert call["source"] == "shieldops"


# =========================================================================
# App Wiring Tests
# =========================================================================


class TestAppWiring:
    """Verify PagerDuty channel is wired into SupervisorRunner via app lifespan."""

    @pytest.mark.asyncio
    async def test_pagerduty_wired_when_key_set(self) -> None:
        """When pagerduty_routing_key is set, the notifier should appear in
        notification_channels passed to SupervisorRunner."""
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

            # Patch settings to have a PagerDuty routing key
            stack.enter_context(patch("shieldops.api.app.settings.pagerduty_routing_key", "R-test"))

            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                mock_sup_cls.assert_called_once()
                call_kwargs = mock_sup_cls.call_args.kwargs
                channels = call_kwargs["notification_channels"]

                assert "pagerduty" in channels
                assert isinstance(channels["pagerduty"], PagerDutyNotifier)

    @pytest.mark.asyncio
    async def test_no_pagerduty_when_key_empty(self) -> None:
        """When pagerduty_routing_key is empty, notification_channels should
        not contain a pagerduty entry."""
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

            # Ensure routing key is empty (default)
            stack.enter_context(patch("shieldops.api.app.settings.pagerduty_routing_key", ""))

            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                call_kwargs = mock_sup_cls.call_args.kwargs
                channels = call_kwargs["notification_channels"]
                assert "pagerduty" not in channels


# =========================================================================
# Settings Tests
# =========================================================================


class TestSettings:
    """Verify PagerDuty setting exists with correct default."""

    def test_pagerduty_routing_key_default_empty(self) -> None:
        from shieldops.config.settings import Settings

        s = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.pagerduty_routing_key == ""

    def test_pagerduty_routing_key_set(self) -> None:
        from shieldops.config.settings import Settings

        s = Settings(
            pagerduty_routing_key="PD-ROUTING-KEY-123",
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.pagerduty_routing_key == "PD-ROUTING-KEY-123"
