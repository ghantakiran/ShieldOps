"""Block Kit builders for Slack interactive messages."""

from __future__ import annotations

from typing import Any

# Slack enforces a 3 000-character limit on text within a single block.
_SLACK_TEXT_LIMIT = 3000

_SEVERITY_EMOJI: dict[str, str] = {
    "critical": "\U0001f534",  # red circle
    "high": "\U0001f7e0",  # orange circle
    "warning": "\U0001f7e1",  # yellow circle
    "medium": "\U0001f7e1",  # yellow circle
    "info": "\U0001f535",  # blue circle
    "low": "\U0001f535",  # blue circle
}


def _emoji(severity: str) -> str:
    return _SEVERITY_EMOJI.get(severity.lower(), "\U0001f535")


def _trunc(text: str, limit: int = _SLACK_TEXT_LIMIT) -> str:
    return text[:limit]


# ---------------------------------------------------------------------------
# Investigation result blocks
# ---------------------------------------------------------------------------


def investigation_blocks(investigation: dict[str, Any]) -> list[dict[str, Any]]:
    """Build Block Kit blocks for an investigation result.

    Expected keys in *investigation*:
        id, title, service, status, confidence, root_cause, evidence, severity
    """
    severity = investigation.get("severity", "info")
    emoji = _emoji(severity)
    confidence = investigation.get("confidence", 0.0)
    confidence_pct = f"{confidence * 100:.0f}%" if confidence <= 1.0 else f"{confidence:.0f}%"

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": _trunc(f"{emoji} Investigation: {investigation.get('title', 'Untitled')}"),
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*ID:* `{investigation.get('id', 'N/A')}`"},
                {"type": "mrkdwn", "text": f"*Service:* {investigation.get('service', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Status:* {investigation.get('status', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Confidence:* {confidence_pct}"},
                {"type": "mrkdwn", "text": f"*Severity:* {severity.upper()}"},
            ],
        },
    ]

    root_cause = investigation.get("root_cause")
    if root_cause:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": _trunc(f"*Root Cause:*\n{root_cause}"),
                },
            }
        )

    evidence = investigation.get("evidence")
    if evidence and isinstance(evidence, list):
        evidence_lines = "\n".join(f"- {e}" for e in evidence[:10])
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": _trunc(f"*Evidence:*\n{evidence_lines}"),
                },
            }
        )

    blocks.append({"type": "divider"})
    return blocks


# ---------------------------------------------------------------------------
# Approval request blocks
# ---------------------------------------------------------------------------


def approval_blocks(
    remediation: dict[str, Any],
    callback_id: str,
) -> list[dict[str, Any]]:
    """Build Block Kit blocks for a remediation approval request.

    Expected keys in *remediation*:
        id, title, description, target_service, action_type, risk_level, investigation_id
    """
    risk = remediation.get("risk_level", "medium")
    emoji = _emoji(risk)

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": _trunc(f"{emoji} Approval Required: {remediation.get('title', '')}"),
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": _trunc(remediation.get("description", "No description provided.")),
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Remediation ID:* `{remediation.get('id', 'N/A')}`",
                },
                {
                    "type": "mrkdwn",
                    "text": (f"*Investigation:* `{remediation.get('investigation_id', 'N/A')}`"),
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Target:* {remediation.get('target_service', 'N/A')}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Action:* {remediation.get('action_type', 'N/A')}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Risk:* {risk.upper()}",
                },
            ],
        },
        {
            "type": "actions",
            "block_id": f"approval_{callback_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                    "style": "primary",
                    "action_id": "remediation_approve",
                    "value": callback_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                    "style": "danger",
                    "action_id": "remediation_reject",
                    "value": callback_id,
                },
            ],
        },
        {"type": "divider"},
    ]
    return blocks


# ---------------------------------------------------------------------------
# War room header blocks
# ---------------------------------------------------------------------------


def war_room_header_blocks(incident: dict[str, Any]) -> list[dict[str, Any]]:
    """Build Block Kit blocks for a war room channel header.

    Expected keys in *incident*:
        title, severity, services, responders, started_at
    """
    severity = incident.get("severity", "info")
    emoji = _emoji(severity)
    services = ", ".join(incident.get("services", [])) or "N/A"
    responders = ", ".join(f"<@{uid}>" for uid in incident.get("responders", [])) or "N/A"

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": _trunc(f"{emoji} WAR ROOM: {incident.get('title', 'Incident')}"),
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Severity:* {severity.upper()}"},
                {
                    "type": "mrkdwn",
                    "text": f"*Started:* {incident.get('started_at', 'N/A')}",
                },
                {"type": "mrkdwn", "text": f"*Services:* {services}"},
                {"type": "mrkdwn", "text": f"*Responders:* {responders}"},
            ],
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        "This channel was created by ShieldOps for incident coordination. "
                        "All actions are logged."
                    ),
                },
            ],
        },
    ]
    return blocks


# ---------------------------------------------------------------------------
# Timeline blocks
# ---------------------------------------------------------------------------


def timeline_blocks(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build Block Kit blocks for an incident timeline.

    Each event dict should contain:
        timestamp, description, actor (optional), type (optional)
    """
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Incident Timeline", "emoji": True},
        },
    ]

    for event in events[:50]:  # Slack has a 50-block limit per message
        ts = event.get("timestamp", "??:??")
        desc = event.get("description", "")
        actor = event.get("actor", "")
        event_type = event.get("type", "event")

        prefix = f"[{event_type.upper()}] " if event_type else ""
        actor_suffix = f" — _{actor}_" if actor else ""

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": _trunc(f"*{ts}*  {prefix}{desc}{actor_suffix}"),
                },
            }
        )

    blocks.append({"type": "divider"})
    return blocks
