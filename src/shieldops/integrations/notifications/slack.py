"""Slack notification channel via Bot Token + chat.postMessage API."""

from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"

# Slack enforces a 3 000-character limit on text within a single block.
_SLACK_TEXT_LIMIT = 3000

_SEVERITY_EMOJI: dict[str, str] = {
    "critical": "\U0001f534",  # red circle
    "high": "\U0001f7e0",  # orange circle
    "warning": "\U0001f7e1",  # yellow circle
    "info": "\U0001f535",  # blue circle
}


class SlackNotifier:
    """Send alerts to Slack via the chat.postMessage API.

    Implements the :class:`NotificationChannel` protocol so it can be
    registered with :class:`NotificationDispatcher`.
    """

    def __init__(
        self,
        bot_token: str,
        default_channel: str = "#shieldops-alerts",
        *,
        timeout: float = 10.0,
    ) -> None:
        self._bot_token = bot_token
        self._default_channel = default_channel
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
        """Send a simple notification to Slack."""
        emoji = self._severity_emoji(severity)
        truncated = message[:_SLACK_TEXT_LIMIT]

        blocks: list[dict[str, Any]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *[{severity.upper()}]* {truncated}",
                },
            },
        ]

        if details:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (f"```{json.dumps(details, indent=2)[:_SLACK_TEXT_LIMIT]}```"),
                    },
                }
            )

        return await self._post_message(
            blocks=blocks,
            text=f"{emoji} [{severity.upper()}] {truncated}",
        )

    async def send_escalation(
        self,
        title: str,
        description: str,
        severity: str = "high",
        source: str = "shieldops",
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Send a rich escalation notification to Slack with Block Kit."""
        emoji = self._severity_emoji(severity)

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": title[:_SLACK_TEXT_LIMIT],
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": description[:_SLACK_TEXT_LIMIT],
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (f"{emoji} *Severity:* {severity.upper()}  |  *Source:* {source}"),
                    },
                ],
            },
        ]

        if details:
            fields = [
                {
                    "type": "mrkdwn",
                    "text": f"*{k}:* {v}",
                }
                for k, v in details.items()
            ]
            blocks.append({"type": "section", "fields": fields})

        fallback = f"{emoji} [{severity.upper()}] {title}"
        return await self._post_message(blocks=blocks, text=fallback)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _post_message(
        self,
        blocks: list[dict[str, Any]],
        text: str,
    ) -> bool:
        """POST a message to the Slack chat.postMessage API."""
        headers = {
            "Authorization": f"Bearer {self._bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload: dict[str, Any] = {
            "channel": self._default_channel,
            "text": text[:_SLACK_TEXT_LIMIT],
            "blocks": blocks,
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
            ) as client:
                resp = await client.post(
                    SLACK_POST_MESSAGE_URL,
                    json=payload,
                    headers=headers,
                )
                data = resp.json()
                success = data.get("ok", False)
                if not success:
                    logger.warning(
                        "slack_send_failed",
                        error=data.get("error", "unknown"),
                        channel=self._default_channel,
                    )
                else:
                    logger.info(
                        "slack_message_sent",
                        channel=self._default_channel,
                        text=text[:80],
                    )
                return bool(success)
        except httpx.HTTPError as exc:
            logger.error("slack_http_error", error=str(exc))
            return False
        except Exception as exc:
            logger.error("slack_error", error=str(exc))
            return False

    @staticmethod
    def _severity_emoji(severity: str) -> str:
        """Map a ShieldOps severity label to a Slack emoji."""
        return _SEVERITY_EMOJI.get(severity.lower(), "\U0001f535")
