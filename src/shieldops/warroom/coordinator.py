"""War Room Coordinator — creates Slack channels, pages on-call teams, and
coordinates incident response through PagerDuty + Slack integration.

Orchestrates the full lifecycle: create war room, page responders, post
updates, escalate, and close with summary.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field

from shieldops.integrations.pagerduty.client import PagerDutyClient
from shieldops.integrations.pagerduty.oncall import OnCallResolver

logger = structlog.get_logger()

# Slack API endpoints used for channel management.
SLACK_API = "https://slack.com/api"


# ---------------------------------------------------------------------------
# Enums & models
# ---------------------------------------------------------------------------


class WarRoomStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class ResponderStatus(StrEnum):
    PAGED = "paged"
    JOINED = "joined"
    LEFT = "left"


class WarRoomResponder(BaseModel):
    """A responder in a war room."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_name: str
    user_email: str = ""
    role: str = "responder"
    status: ResponderStatus = ResponderStatus.PAGED
    pagerduty_user_id: str = ""
    joined_at: float = Field(default_factory=time.time)


class TimelineEntry(BaseModel):
    """A single entry in the war room timeline."""

    timestamp: float = Field(default_factory=time.time)
    author: str = "system"
    message: str = ""
    entry_type: str = "update"  # update | page | escalation | resolution


class WarRoom(BaseModel):
    """In-memory representation of a war room."""

    id: str = Field(default_factory=lambda: f"wr-{uuid.uuid4().hex[:12]}")
    incident_id: str
    title: str
    severity: str = "P2"
    status: WarRoomStatus = WarRoomStatus.ACTIVE
    slack_channel_id: str = ""
    slack_channel_name: str = ""
    pagerduty_incident_id: str = ""
    responders: list[WarRoomResponder] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    escalation_level: int = 1
    created_at: float = Field(default_factory=time.time)
    resolved_at: float | None = None
    resolution_summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class WarRoomCoordinator:
    """Coordinate incident war rooms across Slack and PagerDuty.

    Parameters
    ----------
    pagerduty_client:
        Initialised :class:`PagerDutyClient` for incident/on-call operations.
    slack_bot_token:
        Slack Bot Token for channel creation and messaging.
    slack_timeout:
        Timeout for Slack API calls.
    channel_prefix:
        Prefix for auto-created Slack channel names.
    """

    def __init__(
        self,
        pagerduty_client: PagerDutyClient,
        slack_bot_token: str,
        *,
        slack_timeout: float = 10.0,
        channel_prefix: str = "war-room",
    ) -> None:
        self._pd = pagerduty_client
        self._oncall = OnCallResolver(pagerduty_client)
        self._slack_token = slack_bot_token
        self._slack_timeout = slack_timeout
        self._channel_prefix = channel_prefix
        self._rooms: dict[str, WarRoom] = {}

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_war_room(
        self,
        incident_id: str,
        title: str,
        severity: str = "P2",
        service_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WarRoom:
        """Create a war room: Slack channel + page on-call + post initial timeline.

        Steps:
        1. Create a dedicated Slack channel.
        2. Resolve on-call responders from PagerDuty services.
        3. Page the responders.
        4. Post an initial timeline message to the channel.
        """
        room = WarRoom(
            incident_id=incident_id,
            title=title,
            severity=severity,
            metadata=metadata or {},
        )

        # 1. Create Slack channel
        channel_name = self._build_channel_name(incident_id)
        channel_id = await self._create_slack_channel(channel_name)
        room.slack_channel_id = channel_id
        room.slack_channel_name = channel_name

        room.timeline.append(
            TimelineEntry(
                message=f"War room created for incident {incident_id}: {title}",
                entry_type="update",
            )
        )

        # 2. Page responders if service IDs provided
        if service_ids:
            await self._page_services(room, service_ids)

        # 3. Post opening message to Slack channel
        await self._post_to_slack(
            channel_id,
            (
                f":rotating_light: *War Room Opened* — `{severity}`\n"
                f"*Incident:* {incident_id}\n"
                f"*Title:* {title}\n"
                f"*Responders:* {len(room.responders)}"
            ),
        )

        self._rooms[room.id] = room
        logger.info(
            "war_room_created",
            war_room_id=room.id,
            incident_id=incident_id,
            channel=channel_name,
            responder_count=len(room.responders),
        )
        return room

    # ------------------------------------------------------------------
    # Page
    # ------------------------------------------------------------------

    async def page_responders(
        self,
        war_room_id: str,
        service_ids: list[str],
    ) -> list[WarRoomResponder]:
        """Resolve on-call for the given services and page them into the war room."""
        room = self._rooms.get(war_room_id)
        if room is None:
            raise ValueError(f"War room '{war_room_id}' not found")

        new_responders = await self._page_services(room, service_ids)
        logger.info(
            "war_room_responders_paged",
            war_room_id=war_room_id,
            new_count=len(new_responders),
        )
        return new_responders

    # ------------------------------------------------------------------
    # Add responder manually
    # ------------------------------------------------------------------

    async def add_responder(
        self,
        war_room_id: str,
        user_name: str,
        user_email: str = "",
        role: str = "responder",
    ) -> WarRoomResponder:
        """Manually add a responder to the war room and invite to the Slack channel."""
        room = self._rooms.get(war_room_id)
        if room is None:
            raise ValueError(f"War room '{war_room_id}' not found")

        responder = WarRoomResponder(
            user_name=user_name,
            user_email=user_email,
            role=role,
            status=ResponderStatus.JOINED,
        )
        room.responders.append(responder)
        room.timeline.append(
            TimelineEntry(
                message=f"Responder added: {user_name} ({role})",
                entry_type="update",
                author=user_name,
            )
        )

        # Best-effort invite to Slack channel
        if room.slack_channel_id and user_email:
            await self._invite_to_channel(room.slack_channel_id, user_email)

        await self._post_to_slack(
            room.slack_channel_id,
            f":busts_in_silhouette: *{user_name}* joined as `{role}`",
        )

        logger.info(
            "war_room_responder_added",
            war_room_id=war_room_id,
            user_name=user_name,
        )
        return responder

    # ------------------------------------------------------------------
    # Post update
    # ------------------------------------------------------------------

    async def post_update(
        self,
        war_room_id: str,
        message: str,
        author: str = "system",
    ) -> TimelineEntry:
        """Post an update to the war room timeline and Slack channel."""
        room = self._rooms.get(war_room_id)
        if room is None:
            raise ValueError(f"War room '{war_room_id}' not found")

        entry = TimelineEntry(message=message, author=author, entry_type="update")
        room.timeline.append(entry)

        await self._post_to_slack(
            room.slack_channel_id,
            f":memo: *Update* ({author}): {message}",
        )

        logger.info("war_room_update_posted", war_room_id=war_room_id)
        return entry

    # ------------------------------------------------------------------
    # Escalate
    # ------------------------------------------------------------------

    async def escalate(
        self,
        war_room_id: str,
        service_ids: list[str] | None = None,
    ) -> int:
        """Escalate the war room to the next tier.

        Increments the escalation level and, if service IDs are provided,
        fetches the next-level on-call from the escalation chain.
        Returns the new escalation level.
        """
        room = self._rooms.get(war_room_id)
        if room is None:
            raise ValueError(f"War room '{war_room_id}' not found")

        room.escalation_level += 1

        room.timeline.append(
            TimelineEntry(
                message=f"Escalated to level {room.escalation_level}",
                entry_type="escalation",
            )
        )

        # Page next-level responders
        if service_ids:
            for sid in service_ids:
                chain = await self._oncall.resolve_escalation_chain(sid)
                for level in chain:
                    if level.level == room.escalation_level:
                        for user in level.users:
                            existing = {r.pagerduty_user_id for r in room.responders}
                            if user.id not in existing:
                                responder = WarRoomResponder(
                                    user_name=user.name,
                                    user_email=user.email,
                                    role="responder",
                                    pagerduty_user_id=user.id,
                                )
                                room.responders.append(responder)

        await self._post_to_slack(
            room.slack_channel_id,
            (
                f":arrow_up: *Escalated to Level {room.escalation_level}*\n"
                f"New responders may be joining."
            ),
        )

        logger.info(
            "war_room_escalated",
            war_room_id=war_room_id,
            level=room.escalation_level,
        )
        return room.escalation_level

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    async def close_war_room(
        self,
        war_room_id: str,
        resolution_summary: str = "",
    ) -> WarRoom:
        """Close the war room: post summary, archive channel, update status."""
        room = self._rooms.get(war_room_id)
        if room is None:
            raise ValueError(f"War room '{war_room_id}' not found")

        room.status = WarRoomStatus.RESOLVED
        room.resolved_at = time.time()
        room.resolution_summary = resolution_summary

        room.timeline.append(
            TimelineEntry(
                message=f"War room closed: {resolution_summary}",
                entry_type="resolution",
            )
        )

        # Post summary to channel
        duration_min = (room.resolved_at - room.created_at) / 60
        await self._post_to_slack(
            room.slack_channel_id,
            (
                f":white_check_mark: *War Room Closed*\n"
                f"*Duration:* {duration_min:.1f} minutes\n"
                f"*Responders:* {len(room.responders)}\n"
                f"*Timeline entries:* {len(room.timeline)}\n"
                f"*Resolution:* {resolution_summary}"
            ),
        )

        # Archive channel
        await self._archive_slack_channel(room.slack_channel_id)

        # Resolve PagerDuty incident if linked
        if room.pagerduty_incident_id:
            await self._pd.resolve_incident(room.pagerduty_incident_id)

        logger.info(
            "war_room_closed",
            war_room_id=war_room_id,
            duration_min=round(duration_min, 1),
        )
        return room

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_war_room(self, war_room_id: str) -> WarRoom | None:
        """Return a war room by ID."""
        return self._rooms.get(war_room_id)

    def list_war_rooms(
        self,
        status: WarRoomStatus | None = None,
    ) -> list[WarRoom]:
        """List war rooms, optionally filtered by status."""
        rooms = list(self._rooms.values())
        if status is not None:
            rooms = [r for r in rooms if r.status == status]
        return sorted(rooms, key=lambda r: r.created_at, reverse=True)

    # ------------------------------------------------------------------
    # Private helpers — PagerDuty paging
    # ------------------------------------------------------------------

    async def _page_services(
        self,
        room: WarRoom,
        service_ids: list[str],
    ) -> list[WarRoomResponder]:
        """Resolve on-call for services and add them as responders."""
        new_responders: list[WarRoomResponder] = []
        existing_pd_ids = {r.pagerduty_user_id for r in room.responders}

        for sid in service_ids:
            users = await self._oncall.resolve_oncall_for_service(sid)
            for user in users:
                if user.id in existing_pd_ids:
                    continue
                existing_pd_ids.add(user.id)
                responder = WarRoomResponder(
                    user_name=user.name,
                    user_email=user.email,
                    role="responder",
                    pagerduty_user_id=user.id,
                )
                room.responders.append(responder)
                new_responders.append(responder)

                room.timeline.append(
                    TimelineEntry(
                        message=f"Paged on-call: {user.name} ({user.email})",
                        entry_type="page",
                    )
                )

                # Best-effort invite to Slack channel
                if room.slack_channel_id:
                    await self._invite_to_channel(room.slack_channel_id, user.email)

        return new_responders

    # ------------------------------------------------------------------
    # Private helpers — Slack
    # ------------------------------------------------------------------

    def _build_channel_name(self, incident_id: str) -> str:
        """Build a sanitised Slack channel name."""
        safe_id = incident_id.lower().replace(" ", "-")[:40]
        ts = int(time.time()) % 100000
        return f"{self._channel_prefix}-{safe_id}-{ts}"

    async def _create_slack_channel(self, name: str) -> str:
        """Create a Slack channel, return channel ID."""
        data = await self._slack_request(
            "conversations.create",
            json_body={"name": name, "is_private": False},
        )
        channel_id: str = data.get("channel", {}).get("id", "")
        if not channel_id:
            logger.warning("slack_channel_create_failed", name=name, response=data)
        return channel_id

    async def _archive_slack_channel(self, channel_id: str) -> None:
        """Archive a Slack channel (best-effort)."""
        if not channel_id:
            return
        await self._slack_request(
            "conversations.archive",
            json_body={"channel": channel_id},
        )

    async def _invite_to_channel(self, channel_id: str, email: str) -> None:
        """Invite a user to a Slack channel by email (best-effort).

        First looks up the Slack user ID by email, then invites them.
        """
        if not channel_id or not email:
            return
        try:
            user_data = await self._slack_request(
                "users.lookupByEmail",
                params={"email": email},
            )
            user_id = user_data.get("user", {}).get("id", "")
            if user_id:
                await self._slack_request(
                    "conversations.invite",
                    json_body={"channel": channel_id, "users": user_id},
                )
        except Exception as exc:
            logger.warning(
                "slack_invite_failed",
                channel_id=channel_id,
                email=email,
                error=str(exc),
            )

    async def _post_to_slack(self, channel_id: str, text: str) -> None:
        """Post a message to a Slack channel (best-effort)."""
        if not channel_id:
            return
        await self._slack_request(
            "chat.postMessage",
            json_body={"channel": channel_id, "text": text},
        )

    async def _slack_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a Slack Web API request."""
        url = f"{SLACK_API}/{method}"
        headers = {
            "Authorization": f"Bearer {self._slack_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        try:
            async with httpx.AsyncClient(timeout=self._slack_timeout) as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    params=params,
                    json=json_body,
                )
                data = resp.json()
                if not data.get("ok"):
                    logger.warning(
                        "slack_api_error",
                        method=method,
                        error=data.get("error", "unknown"),
                    )
                return data  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            logger.error("slack_http_error", method=method, error=str(exc))
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            logger.error("slack_error", method=method, error=str(exc))
            return {"ok": False, "error": str(exc)}
