"""Generic webhook notification channel with HMAC signing and retries."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class WebhookNotifier:
    """Generic webhook notification channel.

    Sends JSON payloads to a configurable URL with optional HMAC
    signature verification.

    Implements the :class:`NotificationChannel` protocol so it can be
    registered with :class:`NotificationDispatcher`.
    """

    def __init__(
        self,
        url: str,
        secret: str = "",
        *,
        timeout: float = 10.0,
        custom_headers: dict[str, str] | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self._url = url
        self._secret = secret
        self._timeout = timeout
        self._custom_headers = custom_headers or {}
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    # ------------------------------------------------------------------
    # NotificationChannel protocol
    # ------------------------------------------------------------------

    async def send(
        self,
        message: str,
        severity: str = "info",
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Send a notification event to the webhook URL."""
        payload: dict[str, Any] = {
            "event_type": "notification",
            "severity": severity,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "shieldops",
        }
        return await self._post(payload)

    async def send_escalation(
        self,
        title: str,
        description: str,
        severity: str = "high",
        source: str = "shieldops",
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Send an escalation event to the webhook URL."""
        payload: dict[str, Any] = {
            "event_type": "escalation",
            "title": title,
            "description": description,
            "severity": severity,
            "source": source,
            "details": details or {},
            "timestamp": datetime.now(UTC).isoformat(),
        }
        return await self._post(payload)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(self, body: bytes) -> dict[str, str]:
        """Build request headers, including HMAC signature if secret set."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            **self._custom_headers,
        }
        if self._secret:
            signature = hmac.new(
                self._secret.encode(),
                body,
                hashlib.sha256,
            ).hexdigest()
            headers["X-ShieldOps-Signature"] = signature
        return headers

    async def _post(self, payload: dict[str, Any]) -> bool:
        """POST *payload* as JSON with retry logic for transient errors."""
        if not self._url:
            logger.warning("webhook_send_skipped", reason="empty_url")
            return False

        body = json.dumps(payload).encode()
        headers = self._build_headers(body)

        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout,
                ) as client:
                    resp = await client.post(
                        self._url,
                        content=body,
                        headers=headers,
                    )
                if 200 <= resp.status_code < 300:
                    logger.info(
                        "webhook_event_sent",
                        url=self._url,
                        status=resp.status_code,
                        event_type=payload.get("event_type"),
                    )
                    return True

                # Client errors (4xx) are not retryable
                if 400 <= resp.status_code < 500:
                    logger.warning(
                        "webhook_client_error",
                        status=resp.status_code,
                        body=resp.text[:200],
                        url=self._url,
                    )
                    return False

                # Server errors (5xx) are retryable
                logger.warning(
                    "webhook_server_error",
                    status=resp.status_code,
                    attempt=attempt,
                    max_retries=self._max_retries,
                    url=self._url,
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "webhook_http_error",
                    error=str(exc),
                    attempt=attempt,
                    max_retries=self._max_retries,
                    url=self._url,
                )
            except Exception as exc:
                logger.error(
                    "webhook_unexpected_error",
                    error=str(exc),
                    url=self._url,
                )
                return False

            # Wait before retrying (skip delay after the last attempt)
            if attempt < self._max_retries:
                await asyncio.sleep(self._retry_delay)

        logger.error(
            "webhook_all_retries_exhausted",
            max_retries=self._max_retries,
            url=self._url,
        )
        return False
