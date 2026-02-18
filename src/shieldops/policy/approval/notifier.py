"""Approval notifier — sends Slack notifications for approval requests and escalations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import structlog

if TYPE_CHECKING:
    from shieldops.policy.approval.workflow import ApprovalRequest

from shieldops.models.base import ApprovalStatus

logger = structlog.get_logger()


class ApprovalNotifier:
    """Sends approval notifications via Slack Web API.

    Uses ``httpx`` to POST to ``chat.postMessage`` — no extra dependency needed.
    When ``slack_bot_token`` is empty, all methods are silent no-ops.
    """

    def __init__(
        self,
        slack_bot_token: str = "",
        slack_channel: str = "#shieldops-approvals",
    ) -> None:
        self._token = slack_bot_token
        self._channel = slack_channel

    @property
    def enabled(self) -> bool:
        return bool(self._token)

    async def send_request(self, request: ApprovalRequest) -> None:
        """Notify the primary approval channel of a new request."""
        if not self.enabled:
            return

        text = (
            f":rotating_light: *Approval Required*\n"
            f"*Action:* `{request.action.action_type}` on `{request.action.target_resource}`\n"
            f"*Risk Level:* {request.action.risk_level.value}\n"
            f"*Environment:* {request.action.environment.value}\n"
            f"*Requested by:* {request.agent_id}\n"
            f"*Reason:* {request.reason}\n"
            f"*Required approvals:* {request.required_approvals}\n"
            f"*Request ID:* `{request.request_id}`"
        )
        await self._post_message(text)

        logger.info(
            "approval_notification_sent",
            request_id=request.request_id,
            channel=self._channel,
        )

    async def send_escalation(self, request: ApprovalRequest, target: str) -> None:
        """Notify an escalation target that approval is needed."""
        if not self.enabled:
            return

        text = (
            f":warning: *Escalation — Approval Timeout*\n"
            f"*Action:* `{request.action.action_type}` on `{request.action.target_resource}`\n"
            f"*Risk Level:* {request.action.risk_level.value}\n"
            f"*Escalated to:* {target}\n"
            f"*Request ID:* `{request.request_id}`\n"
            f"_Primary approver did not respond in time._"
        )
        await self._post_message(text, target_channel=target)

        logger.info(
            "approval_escalation_sent",
            request_id=request.request_id,
            target=target,
        )

    async def send_resolution(self, request: ApprovalRequest, status: ApprovalStatus) -> None:
        """Notify the channel of the final approval outcome."""
        if not self.enabled:
            return

        emoji = {
            ApprovalStatus.APPROVED: ":white_check_mark:",
            ApprovalStatus.DENIED: ":x:",
            ApprovalStatus.ESCALATED: ":arrow_up:",
            ApprovalStatus.TIMEOUT: ":hourglass:",
        }.get(status, ":question:")

        text = (
            f"{emoji} *Approval {status.value.upper()}*\n"
            f"*Action:* `{request.action.action_type}` on `{request.action.target_resource}`\n"
            f"*Request ID:* `{request.request_id}`"
        )
        await self._post_message(text)

        logger.info(
            "approval_resolution_sent",
            request_id=request.request_id,
            status=status.value,
        )

    async def _post_message(self, text: str, target_channel: str | None = None) -> None:
        """Post a message to Slack via chat.postMessage."""
        channel = target_channel or self._channel
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {self._token}"},
                    json={"channel": channel, "text": text, "mrkdwn": True},
                )
                data = resp.json()
                if not data.get("ok"):
                    logger.warning(
                        "slack_post_failed",
                        channel=channel,
                        error=data.get("error", "unknown"),
                    )
        except Exception as e:
            logger.warning("slack_post_error", channel=channel, error=str(e))
