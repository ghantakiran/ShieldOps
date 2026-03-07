"""Slack Events API, slash-command, and interactive-component routes."""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response

from shieldops.integrations.slack.bot import (
    InteractionPayload,
    SlackBotService,
    SlackEventsChallenge,
    SlashCommandPayload,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/slack", tags=["Slack"])

# ---------------------------------------------------------------------------
# Module-level service reference (wired at startup from app.py)
# ---------------------------------------------------------------------------

_bot_service: SlackBotService | None = None


def set_bot_service(service: SlackBotService) -> None:
    """Inject the :class:`SlackBotService` instance (called during app startup)."""
    global _bot_service
    _bot_service = service


def _get_bot() -> SlackBotService:
    if _bot_service is None:
        raise HTTPException(status_code=503, detail="Slack bot service unavailable")
    return _bot_service


# ---------------------------------------------------------------------------
# Signature verification helper
# ---------------------------------------------------------------------------


async def _verify_or_reject(request: Request) -> bytes:
    """Read the raw body and verify the Slack request signature.

    Raises ``HTTPException(403)`` on failure.
    """
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    bot = _get_bot()
    if not bot.verify_request(timestamp, signature, body):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")
    return body


# ---------------------------------------------------------------------------
# Background task dispatchers
# ---------------------------------------------------------------------------


async def _dispatch_investigate(service_name: str, channel_id: str, user_id: str) -> None:
    """Background: run an investigation and post results back to Slack."""
    bot = _get_bot()
    try:
        # Import lazily to avoid circular deps and keep startup fast.
        from shieldops.agents.investigation.runner import InvestigationRunner

        runner = InvestigationRunner()
        result = await runner.investigate(service=service_name)  # type: ignore[call-arg]
        investigation = result if isinstance(result, dict) else {"id": "N/A", "title": service_name}
        await bot.send_investigation_result(channel_id, investigation)
    except Exception as exc:
        logger.error(
            "slack_investigate_failed",
            service=service_name,
            error=str(exc),
        )
        await bot._post_message(
            channel=channel_id,
            blocks=[],
            text=f"Investigation for *{service_name}* failed: {exc}",
        )


async def _dispatch_remediate(investigation_id: str, channel_id: str, user_id: str) -> None:
    """Background: initiate remediation and send an approval request."""
    bot = _get_bot()
    try:
        remediation: dict[str, Any] = {
            "id": f"rem-{investigation_id}",
            "title": f"Remediation for {investigation_id}",
            "description": f"Auto-generated remediation for investigation {investigation_id}.",
            "investigation_id": investigation_id,
            "target_service": "TBD",
            "action_type": "auto",
            "risk_level": "medium",
        }
        callback_id = remediation["id"]
        await bot.send_approval_request(
            channel=bot._approval_channel,
            remediation=remediation,
            callback_id=callback_id,
        )
    except Exception as exc:
        logger.error(
            "slack_remediate_failed",
            investigation_id=investigation_id,
            error=str(exc),
        )


async def _dispatch_status(channel_id: str) -> None:
    """Background: fetch agent status and post to channel."""
    bot = _get_bot()
    try:
        # Placeholder — in production wire into supervisor agent
        await bot._post_message(
            channel=channel_id,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "*Active Agents*\n"
                            "- Investigation Agent: idle\n"
                            "- Remediation Agent: idle\n"
                            "- Security Agent: idle\n"
                            "- Learning Agent: idle"
                        ),
                    },
                },
            ],
            text="Active Agents status",
        )
    except Exception as exc:
        logger.error("slack_status_failed", error=str(exc))


async def _dispatch_warroom(incident_title: str, channel_id: str, user_id: str) -> None:
    """Background: create a war room channel and invite the requester."""
    bot = _get_bot()
    try:
        new_channel_id = await bot.create_war_room_channel(incident_title)
        if not new_channel_id:
            await bot._post_message(
                channel=channel_id,
                blocks=[],
                text=f"Failed to create war room for *{incident_title}*.",
            )
            return

        await bot.invite_to_channel(new_channel_id, [user_id])
        await bot.set_war_room_header(
            new_channel_id,
            {
                "title": incident_title,
                "severity": "high",
                "services": [],
                "responders": [user_id],
                "started_at": "now",
            },
        )
        await bot._post_message(
            channel=channel_id,
            blocks=[],
            text=f"War room created: <#{new_channel_id}>",
        )
    except Exception as exc:
        logger.error(
            "slack_warroom_failed",
            incident_title=incident_title,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/events")
async def slack_events(request: Request) -> Response:
    """Slack Events API handler.

    Handles:
        - ``url_verification`` challenge (no signature check per Slack docs)
        - Event dispatch (signature verified)
    """
    body = await request.body()

    # URL verification challenge — Slack sends this once during setup.
    try:
        data = json.loads(body)
        if data.get("type") == "url_verification":
            challenge = SlackEventsChallenge(**data)
            return Response(
                content=json.dumps({"challenge": challenge.challenge}),
                media_type="application/json",
            )
    except Exception:  # noqa: S110
        logger.debug("slack_event_not_json_challenge")

    # All other events require signature verification.
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    bot = _get_bot()
    if not bot.verify_request(timestamp, signature, body):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    # Acknowledge quickly — event processing can be extended here.
    logger.info("slack_event_received", event_type=data.get("event", {}).get("type"))
    return Response(status_code=200)


@router.post("/commands")
async def slack_commands(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """Handle ``/shieldops`` slash commands.

    Returns an immediate ephemeral acknowledgement within 3 seconds and
    dispatches long-running work via ``BackgroundTasks``.
    """
    body = await _verify_or_reject(request)

    # Slash commands arrive as form-encoded, not JSON.
    form = dict(item.split("=", 1) for item in body.decode("utf-8").split("&") if "=" in item)
    # URL-decode values (Slack percent-encodes them)
    from urllib.parse import unquote_plus

    form = {k: unquote_plus(v) for k, v in form.items()}

    payload = SlashCommandPayload(
        command=form.get("command", ""),
        text=form.get("text", ""),
        user_id=form.get("user_id", ""),
        user_name=form.get("user_name", ""),
        channel_id=form.get("channel_id", ""),
        channel_name=form.get("channel_name", ""),
        team_id=form.get("team_id", ""),
        trigger_id=form.get("trigger_id", ""),
        response_url=form.get("response_url", ""),
    )

    bot = _get_bot()
    immediate = await bot.handle_slash_command(
        command=payload.command,
        text=payload.text,
        user_id=payload.user_id,
        channel_id=payload.channel_id,
    )

    # Schedule background work based on sub-command.
    parts = payload.text.strip().split(maxsplit=1)
    subcommand = parts[0].lower() if parts else ""
    argument = parts[1] if len(parts) > 1 else ""

    if subcommand == "investigate" and argument:
        background_tasks.add_task(
            _dispatch_investigate, argument, payload.channel_id, payload.user_id
        )
    elif subcommand == "remediate" and argument:
        background_tasks.add_task(
            _dispatch_remediate, argument, payload.channel_id, payload.user_id
        )
    elif subcommand == "status":
        background_tasks.add_task(_dispatch_status, payload.channel_id)
    elif subcommand == "warroom" and argument:
        background_tasks.add_task(_dispatch_warroom, argument, payload.channel_id, payload.user_id)

    return Response(
        content=json.dumps(immediate),
        media_type="application/json",
    )


@router.post("/interactions")
async def slack_interactions(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """Handle Slack interactive components (button clicks, modal submissions).

    Interactive payloads arrive as form-encoded with a single ``payload``
    field containing JSON.
    """
    body = await _verify_or_reject(request)

    from urllib.parse import unquote_plus

    raw = body.decode("utf-8")
    # Strip the "payload=" prefix
    if raw.startswith("payload="):
        raw = raw[len("payload=") :]
    payload_json = unquote_plus(raw)

    try:
        payload_data = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid interaction payload") from exc

    payload = InteractionPayload(**payload_data)

    bot = _get_bot()
    result = await bot.handle_interaction(payload)

    return Response(
        content=json.dumps(result),
        media_type="application/json",
    )
