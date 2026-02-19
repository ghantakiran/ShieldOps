"""Comprehensive tests for the Email notification channel.

Covers:
- EmailNotifier: send, send_escalation, constructor config, error handling
- Graceful degradation when aiosmtplib is not installed
- Protocol compliance with NotificationChannel
- App wiring: email channel registered when SMTP settings are configured
- Settings: SMTP defaults and overrides
"""

from contextlib import ExitStack
from email.message import EmailMessage
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.integrations.notifications.base import NotificationChannel
from shieldops.integrations.notifications.email import EmailNotifier

# =========================================================================
# Helpers
# =========================================================================


def _make_notifier(**overrides: Any) -> EmailNotifier:
    """Build an EmailNotifier with sensible test defaults."""
    defaults: dict[str, Any] = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "username": "user@example.com",
        "password": "secret",
        "use_tls": True,
        "from_address": "shieldops@example.com",
        "to_addresses": ["oncall@example.com"],
    }
    defaults.update(overrides)
    return EmailNotifier(**defaults)


def _captured_message(mock_send: AsyncMock) -> EmailMessage:
    """Extract the EmailMessage from a mocked aiosmtplib.send call."""
    return mock_send.call_args[0][0]


# =========================================================================
# NotificationChannel Protocol Compliance
# =========================================================================


class TestEmailProtocolCompliance:
    """Verify EmailNotifier satisfies the NotificationChannel protocol."""

    def test_satisfies_protocol(self) -> None:
        notifier = _make_notifier()
        assert isinstance(notifier, NotificationChannel)

    def test_has_send_method(self) -> None:
        notifier = _make_notifier()
        assert callable(getattr(notifier, "send", None))

    def test_has_send_escalation_method(self) -> None:
        notifier = _make_notifier()
        assert callable(getattr(notifier, "send_escalation", None))


# =========================================================================
# Constructor Tests
# =========================================================================


class TestEmailNotifierConstructor:
    """Verify constructor stores all configuration correctly."""

    def test_stores_smtp_host(self) -> None:
        n = _make_notifier(smtp_host="mail.corp.com")
        assert n._smtp_host == "mail.corp.com"

    def test_stores_smtp_port(self) -> None:
        n = _make_notifier(smtp_port=465)
        assert n._smtp_port == 465

    def test_stores_username(self) -> None:
        n = _make_notifier(username="admin")
        assert n._username == "admin"

    def test_stores_password(self) -> None:
        n = _make_notifier(password="hunter2")
        assert n._password == "hunter2"  # noqa: S105

    def test_stores_use_tls(self) -> None:
        n = _make_notifier(use_tls=False)
        assert n._use_tls is False

    def test_stores_from_address(self) -> None:
        n = _make_notifier(from_address="alerts@corp.com")
        assert n._from_address == "alerts@corp.com"

    def test_stores_to_addresses(self) -> None:
        addrs = ["a@b.com", "c@d.com"]
        n = _make_notifier(to_addresses=addrs)
        assert n._to_addresses == addrs

    def test_stores_custom_timeout(self) -> None:
        n = _make_notifier(timeout=30.0)
        assert n._timeout == 30.0

    def test_default_timeout(self) -> None:
        n = _make_notifier()
        assert n._timeout == 10.0

    def test_none_to_addresses_becomes_empty_list(self) -> None:
        n = _make_notifier(to_addresses=None)
        assert n._to_addresses == []

    def test_default_port(self) -> None:
        n = EmailNotifier(smtp_host="h")
        assert n._smtp_port == 587

    def test_default_from_address(self) -> None:
        n = EmailNotifier(smtp_host="h")
        assert n._from_address == "shieldops@localhost"


# =========================================================================
# send() Tests
# =========================================================================


class TestEmailNotifierSend:
    """Tests for the send() method."""

    @pytest.mark.asyncio
    async def test_send_returns_true_on_success(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            result = await notifier.send("CPU at 95%", severity="high")

        assert result is True
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_subject_includes_severity(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send("test", severity="critical")

        msg = _captured_message(mock_send)
        assert "[CRITICAL]" in msg["Subject"]
        assert "[ShieldOps]" in msg["Subject"]

    @pytest.mark.asyncio
    async def test_send_subject_default_severity(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send("test")

        msg = _captured_message(mock_send)
        assert "[INFO]" in msg["Subject"]

    @pytest.mark.asyncio
    async def test_send_body_includes_message(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send("Disk usage at 90%")

        msg = _captured_message(mock_send)
        body = msg.get_content()
        assert "Disk usage at 90%" in body

    @pytest.mark.asyncio
    async def test_send_body_includes_details(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send(
                "alert",
                details={"host": "web-01", "region": "us-east-1"},
            )

        msg = _captured_message(mock_send)
        body = msg.get_content()
        assert "host: web-01" in body
        assert "region: us-east-1" in body

    @pytest.mark.asyncio
    async def test_send_body_without_details(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send("simple message")

        msg = _captured_message(mock_send)
        body = msg.get_content()
        assert "Details:" not in body

    @pytest.mark.asyncio
    async def test_send_from_and_to_headers(self) -> None:
        notifier = _make_notifier(
            from_address="alerts@corp.com",
            to_addresses=["team@corp.com", "manager@corp.com"],
        )
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send("test")

        msg = _captured_message(mock_send)
        assert msg["From"] == "alerts@corp.com"
        assert "team@corp.com" in msg["To"]
        assert "manager@corp.com" in msg["To"]

    @pytest.mark.asyncio
    async def test_send_passes_smtp_config(self) -> None:
        notifier = _make_notifier(
            smtp_host="mail.test.com",
            smtp_port=465,
            username="u",
            password="p",
            use_tls=False,
            timeout=5.0,
        )
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send("test")

        _, kwargs = mock_send.call_args
        assert kwargs["hostname"] == "mail.test.com"
        assert kwargs["port"] == 465
        assert kwargs["username"] == "u"
        assert kwargs["password"] == "p"  # noqa: S105
        assert kwargs["start_tls"] is False
        assert kwargs["timeout"] == 5.0

    @pytest.mark.asyncio
    async def test_send_returns_false_on_smtp_error(self) -> None:
        notifier = _make_notifier()

        mock_smtp_mod = MagicMock()
        mock_smtp_mod.SMTPException = type("SMTPException", (Exception,), {})
        mock_smtp_mod.send = AsyncMock(side_effect=mock_smtp_mod.SMTPException("relay denied"))

        with patch.dict("sys.modules", {"aiosmtplib": mock_smtp_mod}):
            result = await notifier.send("fail")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_returns_false_on_unexpected_error(self) -> None:
        notifier = _make_notifier()

        mock_smtp_mod = MagicMock()
        mock_smtp_mod.SMTPException = type("SMTPException", (Exception,), {})
        mock_smtp_mod.send = AsyncMock(side_effect=RuntimeError("unexpected"))

        with patch.dict("sys.modules", {"aiosmtplib": mock_smtp_mod}):
            result = await notifier.send("fail")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_empty_to_addresses_returns_false(self) -> None:
        notifier = _make_notifier(to_addresses=[])
        result = await notifier.send("no one to send to")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_none_to_addresses_returns_false(self) -> None:
        notifier = _make_notifier(to_addresses=None)
        result = await notifier.send("no one to send to")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_empty_username_passes_none(self) -> None:
        """Empty username/password should be passed as None to aiosmtplib."""
        notifier = _make_notifier(username="", password="")
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send("test")

        _, kwargs = mock_send.call_args
        assert kwargs["username"] is None
        assert kwargs["password"] is None


# =========================================================================
# send_escalation() Tests
# =========================================================================


class TestEmailNotifierSendEscalation:
    """Tests for the send_escalation() method."""

    @pytest.mark.asyncio
    async def test_escalation_returns_true_on_success(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            result = await notifier.send_escalation(
                title="DB Down",
                description="Primary unreachable",
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_escalation_subject_includes_title(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send_escalation(
                title="Disk Full",
                description="90% used",
            )

        msg = _captured_message(mock_send)
        assert msg["Subject"] == "[ShieldOps] ESCALATION: Disk Full"

    @pytest.mark.asyncio
    async def test_escalation_has_html_and_plain_parts(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send_escalation(title="Test", description="desc")

        msg = _captured_message(mock_send)
        # EmailMessage with add_alternative creates a multipart message
        parts = list(msg.iter_parts())
        content_types = [p.get_content_type() for p in parts]
        assert "text/plain" in content_types
        assert "text/html" in content_types

    @pytest.mark.asyncio
    async def test_escalation_html_includes_severity_banner(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send_escalation(
                title="T",
                description="D",
                severity="critical",
            )

        msg = _captured_message(mock_send)
        html_part = None
        for part in msg.iter_parts():
            if part.get_content_type() == "text/html":
                html_part = part.get_content()
                break
        assert html_part is not None
        assert "CRITICAL" in html_part
        assert "#9C27B0" in html_part  # critical color

    @pytest.mark.asyncio
    async def test_escalation_html_includes_description(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send_escalation(title="T", description="Primary DB is down")

        msg = _captured_message(mock_send)
        html_part = None
        for part in msg.iter_parts():
            if part.get_content_type() == "text/html":
                html_part = part.get_content()
                break
        assert "Primary DB is down" in html_part

    @pytest.mark.asyncio
    async def test_escalation_html_includes_source(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send_escalation(
                title="T",
                description="D",
                source="supervisor-agent",
            )

        msg = _captured_message(mock_send)
        html_part = None
        for part in msg.iter_parts():
            if part.get_content_type() == "text/html":
                html_part = part.get_content()
                break
        assert "supervisor-agent" in html_part

    @pytest.mark.asyncio
    async def test_escalation_with_details_table(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send_escalation(
                title="T",
                description="D",
                details={"cluster": "prod", "region": "us-east-1"},
            )

        msg = _captured_message(mock_send)
        html_part = None
        for part in msg.iter_parts():
            if part.get_content_type() == "text/html":
                html_part = part.get_content()
                break
        assert "<table" in html_part
        assert "cluster" in html_part
        assert "prod" in html_part
        assert "region" in html_part

    @pytest.mark.asyncio
    async def test_escalation_without_details_no_table(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send_escalation(title="T", description="D", details=None)

        msg = _captured_message(mock_send)
        html_part = None
        for part in msg.iter_parts():
            if part.get_content_type() == "text/html":
                html_part = part.get_content()
                break
        assert "<table" not in html_part

    @pytest.mark.asyncio
    async def test_escalation_plain_text_fallback(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send_escalation(
                title="DB Down",
                description="Primary unreachable",
                severity="high",
                source="supervisor",
            )

        msg = _captured_message(mock_send)
        plain_part = None
        for part in msg.iter_parts():
            if part.get_content_type() == "text/plain":
                plain_part = part.get_content()
                break
        assert "ESCALATION - HIGH" in plain_part
        assert "Title: DB Down" in plain_part
        assert "Description: Primary unreachable" in plain_part
        assert "Source: supervisor" in plain_part

    @pytest.mark.asyncio
    async def test_escalation_returns_false_on_smtp_error(self) -> None:
        notifier = _make_notifier()

        mock_smtp_mod = MagicMock()
        mock_smtp_mod.SMTPException = type("SMTPException", (Exception,), {})
        mock_smtp_mod.send = AsyncMock(side_effect=mock_smtp_mod.SMTPException("auth failed"))

        with patch.dict("sys.modules", {"aiosmtplib": mock_smtp_mod}):
            result = await notifier.send_escalation(title="T", description="D")

        assert result is False

    @pytest.mark.asyncio
    async def test_escalation_empty_to_addresses_returns_false(self) -> None:
        notifier = _make_notifier(to_addresses=[])
        result = await notifier.send_escalation(title="T", description="D")
        assert result is False

    @pytest.mark.asyncio
    async def test_escalation_severity_color_mapping(self) -> None:
        """Each severity should map to the correct banner color."""
        severity_expected = {
            "low": "#2196F3",
            "info": "#2196F3",
            "medium": "#FF9800",
            "warning": "#FF9800",
            "high": "#F44336",
            "critical": "#9C27B0",
        }
        for sev, expected_color in severity_expected.items():
            notifier = _make_notifier()
            mock_send = AsyncMock()

            with patch.dict(
                "sys.modules",
                {"aiosmtplib": MagicMock(send=mock_send)},
            ):
                await notifier.send_escalation(title="T", description="D", severity=sev)

            msg = _captured_message(mock_send)
            html_part = None
            for part in msg.iter_parts():
                if part.get_content_type() == "text/html":
                    html_part = part.get_content()
                    break
            assert expected_color in html_part, f"severity={sev}: expected {expected_color}"

    @pytest.mark.asyncio
    async def test_escalation_unknown_severity_uses_default(self) -> None:
        notifier = _make_notifier()
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            await notifier.send_escalation(title="T", description="D", severity="unknown")

        msg = _captured_message(mock_send)
        html_part = None
        for part in msg.iter_parts():
            if part.get_content_type() == "text/html":
                html_part = part.get_content()
                break
        # Falls back to #F44336 (the default)
        assert "#F44336" in html_part


# =========================================================================
# Graceful Degradation Tests
# =========================================================================


class TestGracefulDegradation:
    """Verify behavior when aiosmtplib is not installed."""

    @pytest.mark.asyncio
    async def test_send_returns_false_without_aiosmtplib(self) -> None:
        notifier = _make_notifier()

        with patch.dict("sys.modules", {"aiosmtplib": None}):
            result = await notifier.send("test")

        assert result is False

    @pytest.mark.asyncio
    async def test_escalation_returns_false_without_aiosmtplib(
        self,
    ) -> None:
        notifier = _make_notifier()

        with patch.dict("sys.modules", {"aiosmtplib": None}):
            result = await notifier.send_escalation(title="T", description="D")

        assert result is False


# =========================================================================
# Multiple Recipients Tests
# =========================================================================


class TestMultipleRecipients:
    """Verify emails are addressed to all recipients."""

    @pytest.mark.asyncio
    async def test_send_to_multiple_recipients(self) -> None:
        addrs = ["a@x.com", "b@x.com", "c@x.com"]
        notifier = _make_notifier(to_addresses=addrs)
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            result = await notifier.send("multi-test")

        assert result is True
        msg = _captured_message(mock_send)
        to_header = msg["To"]
        for addr in addrs:
            assert addr in to_header

    @pytest.mark.asyncio
    async def test_escalation_to_multiple_recipients(self) -> None:
        addrs = ["a@x.com", "b@x.com"]
        notifier = _make_notifier(to_addresses=addrs)
        mock_send = AsyncMock()

        with patch.dict("sys.modules", {"aiosmtplib": MagicMock(send=mock_send)}):
            result = await notifier.send_escalation(title="T", description="D")

        assert result is True
        msg = _captured_message(mock_send)
        to_header = msg["To"]
        for addr in addrs:
            assert addr in to_header


# =========================================================================
# Settings Tests
# =========================================================================


class TestSmtpSettings:
    """Verify SMTP settings exist with correct defaults."""

    def test_smtp_defaults(self) -> None:
        from shieldops.config.settings import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.smtp_host == ""
        assert s.smtp_port == 587
        assert s.smtp_username == ""
        assert s.smtp_password == ""
        assert s.smtp_use_tls is True
        assert s.smtp_from_address == "shieldops@localhost"
        assert s.smtp_to_addresses == []

    def test_smtp_settings_override(self) -> None:
        from shieldops.config.settings import Settings

        s = Settings(
            smtp_host="mail.corp.com",
            smtp_port=465,
            smtp_username="admin",
            smtp_password="s3cret",
            smtp_use_tls=False,
            smtp_from_address="alerts@corp.com",
            smtp_to_addresses=["ops@corp.com", "lead@corp.com"],
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.smtp_host == "mail.corp.com"
        assert s.smtp_port == 465
        assert s.smtp_username == "admin"
        assert s.smtp_password == "s3cret"  # noqa: S105
        assert s.smtp_use_tls is False
        assert s.smtp_from_address == "alerts@corp.com"
        assert s.smtp_to_addresses == ["ops@corp.com", "lead@corp.com"]


# =========================================================================
# App Wiring Tests
# =========================================================================


class TestAppWiringEmail:
    """Verify email channel is wired into SupervisorRunner via app lifespan."""

    @pytest.mark.asyncio
    async def test_email_wired_when_smtp_configured(self) -> None:
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

            # Patch SMTP settings
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.smtp_host",
                    "smtp.test.com",
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.smtp_to_addresses",
                    ["ops@test.com"],
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.smtp_port",
                    587,
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.smtp_username",
                    "user",
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.smtp_password",
                    "pass",
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.smtp_use_tls",
                    True,
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.smtp_from_address",
                    "shieldops@test.com",
                )
            )

            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                mock_sup_cls.assert_called_once()
                call_kwargs = mock_sup_cls.call_args.kwargs
                channels = call_kwargs["notification_channels"]

                assert "email" in channels
                assert isinstance(channels["email"], EmailNotifier)

    @pytest.mark.asyncio
    async def test_no_email_when_smtp_host_empty(self) -> None:
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

            # SMTP host empty
            stack.enter_context(patch("shieldops.api.app.settings.smtp_host", ""))
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.smtp_to_addresses",
                    ["ops@test.com"],
                )
            )

            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                call_kwargs = mock_sup_cls.call_args.kwargs
                channels = call_kwargs["notification_channels"]
                assert "email" not in channels

    @pytest.mark.asyncio
    async def test_no_email_when_to_addresses_empty(self) -> None:
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

            # SMTP host set but no recipients
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.smtp_host",
                    "smtp.test.com",
                )
            )
            stack.enter_context(
                patch(
                    "shieldops.api.app.settings.smtp_to_addresses",
                    [],
                )
            )

            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                call_kwargs = mock_sup_cls.call_args.kwargs
                channels = call_kwargs["notification_channels"]
                assert "email" not in channels
