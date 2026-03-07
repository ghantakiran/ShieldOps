"""Slack bot service — signature verification, slash commands, interactions."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx
import structlog
from pydantic import BaseModel

from shieldops.integrations.slack.blocks import (
    approval_blocks,
    investigation_blocks,
    timeline_blocks,
    war_room_header_blocks,
)

logger = structlog.get_logger()

SLACK_API_BASE = "https://slack.com/api"

# ---------------------------------------------------------------------------
# Pydantic models for Slack payloads
# ---------------------------------------------------------------------------


class SlashCommandPayload(BaseModel):
    """Incoming Slack slash-command payload."""

    command: str
    text: str = ""
    user_id: str
    user_name: str = ""
    channel_id: str
    channel_name: str = ""
    team_id: str = ""
    trigger_id: str = ""
    response_url: str = ""


class InteractionAction(BaseModel):
    """A single action inside an interactive payload."""

    action_id: str
    value: str = ""
    type: str = "button"


class InteractionUser(BaseModel):
    """User who triggered the interaction."""

    id: str
    username: str = ""
    name: str = ""


class InteractionPayload(BaseModel):
    """Slack interactive-component payload (buttons, modals)."""

    type: str  # "block_actions", "view_submission", etc.
    trigger_id: str = ""
    user: InteractionUser
    actions: list[InteractionAction] = []
    channel: dict[str, str] | None = None
    response_url: str = ""
    message: dict[str, Any] | None = None


class SlackEventsChallenge(BaseModel):
    """Slack Events API URL-verification challenge."""

    type: str  # "url_verification"
    challenge: str
    token: str = ""


# ---------------------------------------------------------------------------
# SlackBotService
# ---------------------------------------------------------------------------


class SlackBotService:
    """Core Slack bot service for ShieldOps.

    Handles request verification, slash commands, interactive messages,
    war-room creation, and rich Block Kit formatting.
    """

    def __init__(
        self,
        bot_token: str,
        signing_secret: str,
        approval_channel: str = "#shieldops-approvals",
        *,
        timeout: float = 10.0,
    ) -> None:
        self._bot_token = bot_token
        self._signing_secret = signing_secret
        self._approval_channel = approval_channel
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Request verification (HMAC-SHA256)
    # ------------------------------------------------------------------

    def verify_request(self, timestamp: str, signature: str, body: bytes) -> bool:
        """Verify a Slack request using HMAC-SHA256 signing secret.

        Returns ``True`` when the signature is valid **and** the timestamp
        is within 5 minutes (replay-attack guard).
        """
        try:
            ts = int(timestamp)
        except (ValueError, TypeError):
            logger.warning("slack_verify_bad_timestamp", timestamp=timestamp)
            return False

        if abs(time.time() - ts) > 300:
            logger.warning("slack_verify_timestamp_expired", timestamp=timestamp)
            return False

        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        computed = (
            "v0="
            + hmac.new(
                self._signing_secret.encode("utf-8"),
                sig_basestring.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        )

        if not hmac.compare_digest(computed, signature):
            logger.warning("slack_verify_signature_mismatch")
            return False

        return True

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------

    async def handle_slash_command(
        self,
        command: str,
        text: str,
        user_id: str,
        channel_id: str,
    ) -> dict[str, Any]:
        """Route ``/shieldops`` slash commands.

        Supported sub-commands:
            investigate <service-name>
            remediate <investigation-id>
            status
            warroom <incident-title>

        Returns an *immediate* ephemeral response dict.  Long-running work
        is triggered via background tasks by the caller.
        """
        parts = text.strip().split(maxsplit=1)
        subcommand = parts[0].lower() if parts else ""
        argument = parts[1] if len(parts) > 1 else ""

        logger.info(
            "slack_slash_command",
            command=command,
            subcommand=subcommand,
            argument=argument,
            user_id=user_id,
            channel_id=channel_id,
        )

        if subcommand == "investigate":
            if not argument:
                return self._ephemeral("Usage: `/shieldops investigate <service-name>`")
            return self._ephemeral(
                f"Starting investigation for *{argument}*. "
                "Results will be posted here when complete."
            )

        if subcommand == "remediate":
            if not argument:
                return self._ephemeral("Usage: `/shieldops remediate <investigation-id>`")
            return self._ephemeral(
                f"Initiating remediation for investigation `{argument}`. "
                "An approval request will be sent to the approvals channel."
            )

        if subcommand == "status":
            return self._ephemeral("Fetching active agent status. Results will appear shortly.")

        if subcommand == "warroom":
            if not argument:
                return self._ephemeral("Usage: `/shieldops warroom <incident-title>`")
            return self._ephemeral(
                f"Creating war room for *{argument}*. "
                "You will be invited to the new channel momentarily."
            )

        return self._ephemeral(
            "Unknown sub-command. Available: `investigate`, `remediate`, `status`, `warroom`"
        )

    # ------------------------------------------------------------------
    # Interactive components (button clicks, modal submissions)
    # ------------------------------------------------------------------

    async def handle_interaction(self, payload: InteractionPayload) -> dict[str, Any]:
        """Handle Slack interactive-component callbacks.

        Supports:
            - ``remediation_approve`` / ``remediation_reject`` button actions
            - ``view_submission`` modal callbacks
        """
        if payload.type == "block_actions":
            return await self._handle_block_actions(payload)

        if payload.type == "view_submission":
            return await self._handle_view_submission(payload)

        logger.warning("slack_interaction_unknown_type", payload_type=payload.type)
        return {"text": "Unsupported interaction type."}

    async def _handle_block_actions(self, payload: InteractionPayload) -> dict[str, Any]:
        for action in payload.actions:
            if action.action_id == "remediation_approve":
                logger.info(
                    "slack_remediation_approved",
                    callback_id=action.value,
                    user=payload.user.id,
                )
                return {
                    "response_type": "in_channel",
                    "text": (f"Remediation `{action.value}` *approved* by <@{payload.user.id}>."),
                    "replace_original": True,
                }

            if action.action_id == "remediation_reject":
                logger.info(
                    "slack_remediation_rejected",
                    callback_id=action.value,
                    user=payload.user.id,
                )
                return {
                    "response_type": "in_channel",
                    "text": (f"Remediation `{action.value}` *rejected* by <@{payload.user.id}>."),
                    "replace_original": True,
                }

        return {"text": "Action not recognised."}

    async def _handle_view_submission(self, payload: InteractionPayload) -> dict[str, Any]:
        logger.info("slack_modal_submitted", user=payload.user.id)
        return {"response_action": "clear"}

    # ------------------------------------------------------------------
    # Rich message senders
    # ------------------------------------------------------------------

    async def send_investigation_result(
        self,
        channel: str,
        investigation: dict[str, Any],
    ) -> bool:
        """Post an investigation result as a rich Block Kit message."""
        blocks = investigation_blocks(investigation)
        fallback = (
            f"Investigation {investigation.get('id', '?')}: "
            f"{investigation.get('title', 'Untitled')}"
        )
        return await self._post_message(channel=channel, blocks=blocks, text=fallback)

    async def send_approval_request(
        self,
        channel: str,
        remediation: dict[str, Any],
        callback_id: str,
    ) -> bool:
        """Post an approval request with Approve / Reject buttons."""
        blocks = approval_blocks(remediation, callback_id)
        fallback = f"Approval needed for remediation: {remediation.get('title', 'Untitled')}"
        return await self._post_message(channel=channel, blocks=blocks, text=fallback)

    async def create_war_room_channel(self, incident_title: str) -> str | None:
        """Create a new Slack channel for incident coordination.

        Returns the channel ID on success, or ``None`` on failure.
        """
        slug = incident_title.lower().replace(" ", "-").replace("_", "-")
        # Slack channel names: lowercase, max 80 chars, no spaces/periods
        channel_name = f"warroom-{slug}"[:80]

        data = await self._slack_api(
            "conversations.create",
            json={"name": channel_name, "is_private": False},
        )
        if not data:
            return None

        channel_id: str = data.get("channel", {}).get("id", "")
        if channel_id:
            logger.info(
                "slack_war_room_created",
                channel_id=channel_id,
                channel_name=channel_name,
            )
        return channel_id or None

    async def invite_to_channel(
        self,
        channel_id: str,
        user_ids: list[str],
    ) -> bool:
        """Invite users to a Slack channel."""
        if not user_ids:
            return True

        data = await self._slack_api(
            "conversations.invite",
            json={"channel": channel_id, "users": ",".join(user_ids)},
        )
        success = data is not None
        if success:
            logger.info(
                "slack_users_invited",
                channel_id=channel_id,
                user_count=len(user_ids),
            )
        return success

    async def post_incident_timeline(
        self,
        channel_id: str,
        events: list[dict[str, Any]],
    ) -> bool:
        """Post a formatted incident timeline to a channel."""
        blocks = timeline_blocks(events)
        return await self._post_message(
            channel=channel_id,
            blocks=blocks,
            text="Incident Timeline",
        )

    async def set_war_room_header(
        self,
        channel_id: str,
        incident: dict[str, Any],
    ) -> bool:
        """Post the war room header message to the channel."""
        blocks = war_room_header_blocks(incident)
        return await self._post_message(
            channel=channel_id,
            blocks=blocks,
            text=f"War Room: {incident.get('title', 'Incident')}",
        )

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    async def _post_message(
        self,
        channel: str,
        blocks: list[dict[str, Any]],
        text: str,
    ) -> bool:
        """Post a message via chat.postMessage."""
        data = await self._slack_api(
            "chat.postMessage",
            json={"channel": channel, "blocks": blocks, "text": text},
        )
        return data is not None

    async def _slack_api(
        self,
        method: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Call a Slack Web API method.  Returns response data or None."""
        url = f"{SLACK_API_BASE}/{method}"
        headers = {
            "Authorization": f"Bearer {self._bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=json or {}, headers=headers)
                data = resp.json()

            if not data.get("ok", False):
                logger.warning(
                    "slack_api_error",
                    method=method,
                    error=data.get("error", "unknown"),
                )
                return None

            return dict(data)
        except httpx.HTTPError as exc:
            logger.error("slack_http_error", method=method, error=str(exc))
            return None
        except Exception as exc:
            logger.error("slack_error", method=method, error=str(exc))
            return None

    @staticmethod
    def _ephemeral(text: str) -> dict[str, Any]:
        """Build an ephemeral (visible only to the invoking user) response."""
        return {"response_type": "ephemeral", "text": text}
