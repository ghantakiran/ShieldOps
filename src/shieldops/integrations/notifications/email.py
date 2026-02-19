"""Email notification channel via async SMTP."""

from __future__ import annotations

from email.message import EmailMessage
from typing import Any

import structlog

logger = structlog.get_logger()


class EmailNotifier:
    """Send notifications and escalations via email (SMTP).

    Implements the :class:`NotificationChannel` protocol so it can be
    registered with :class:`NotificationDispatcher`.

    Uses ``aiosmtplib`` for async delivery. If the library is not
    installed, methods log a warning and return ``False`` (graceful
    degradation).
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        use_tls: bool = True,
        from_address: str = "shieldops@localhost",
        to_addresses: list[str] | None = None,
        *,
        timeout: float = 10.0,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._from_address = from_address
        self._to_addresses = to_addresses or []
        self._timeout = timeout

    # ------------------------------------------------------------------
    # NotificationChannel protocol
    # ------------------------------------------------------------------

    async def send(
        self,
        message: str,
        severity: str = "info",
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Send a plain-text notification email."""
        if not self._to_addresses:
            logger.warning("email_send_skipped", reason="no recipients")
            return False

        subject = f"[ShieldOps] [{severity.upper()}] Notification"

        body_parts = [message]
        if details:
            body_parts.append("")
            body_parts.append("Details:")
            for key, value in details.items():
                body_parts.append(f"  {key}: {value}")
        body = "\n".join(body_parts)

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._from_address
        msg["To"] = ", ".join(self._to_addresses)
        msg.set_content(body)

        return await self._send_message(msg)

    async def send_escalation(
        self,
        title: str,
        description: str,
        severity: str = "high",
        source: str = "shieldops",
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Send an HTML escalation email with a styled severity banner."""
        if not self._to_addresses:
            logger.warning("email_escalation_skipped", reason="no recipients")
            return False

        subject = f"[ShieldOps] ESCALATION: {title}"

        # -- HTML body ------------------------------------------------
        severity_colors: dict[str, str] = {
            "low": "#2196F3",
            "info": "#2196F3",
            "medium": "#FF9800",
            "warning": "#FF9800",
            "high": "#F44336",
            "critical": "#9C27B0",
        }
        color = severity_colors.get(severity.lower(), "#F44336")

        details_html = ""
        if details:
            rows = "".join(
                f"<tr><td style='padding:4px 8px;border:1px solid "
                f"#ddd;font-weight:bold'>{k}</td>"
                f"<td style='padding:4px 8px;border:1px solid "
                f"#ddd'>{v}</td></tr>"
                for k, v in details.items()
            )
            details_html = (
                f"<h3>Details</h3><table style='border-collapse:collapse;width:100%'>{rows}</table>"
            )

        html_body = (
            "<div style='font-family:Arial,sans-serif;max-width:600px'>"
            f"<div style='background:{color};color:#fff;"
            f"padding:12px 16px;font-size:18px;font-weight:bold'>"
            f"ESCALATION &mdash; {severity.upper()}</div>"
            "<div style='padding:16px'>"
            f"<h2>{title}</h2>"
            f"<p>{description}</p>"
            f"<p><strong>Source:</strong> {source}</p>"
            f"{details_html}"
            "</div></div>"
        )

        # -- Plain-text fallback --------------------------------------
        text_parts = [
            f"ESCALATION - {severity.upper()}",
            "",
            f"Title: {title}",
            f"Description: {description}",
            f"Source: {source}",
        ]
        if details:
            text_parts.append("")
            text_parts.append("Details:")
            for key, value in details.items():
                text_parts.append(f"  {key}: {value}")
        plain_body = "\n".join(text_parts)

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._from_address
        msg["To"] = ", ".join(self._to_addresses)
        msg.set_content(plain_body)
        msg.add_alternative(html_body, subtype="html")

        return await self._send_message(msg)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send_message(self, msg: EmailMessage) -> bool:
        """Deliver an :class:`EmailMessage` via ``aiosmtplib``."""
        try:
            import aiosmtplib
        except ImportError:
            logger.warning(
                "email_send_failed",
                reason="aiosmtplib not installed",
            )
            return False

        try:
            await aiosmtplib.send(
                msg,
                hostname=self._smtp_host,
                port=self._smtp_port,
                username=self._username or None,
                password=self._password or None,
                start_tls=self._use_tls,
                timeout=self._timeout,
            )
            logger.info(
                "email_sent",
                subject=msg["Subject"],
                recipients=self._to_addresses,
            )
            return True
        except aiosmtplib.SMTPException as exc:
            logger.error(
                "email_smtp_error",
                error=str(exc),
                subject=msg["Subject"],
            )
            return False
        except Exception as exc:
            logger.error(
                "email_send_error",
                error=str(exc),
                subject=msg["Subject"],
            )
            return False
