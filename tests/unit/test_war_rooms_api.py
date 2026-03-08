"""Tests for shieldops.api.routes.war_rooms — War Room API routes."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from shieldops.api.routes.war_rooms import (
    AddResponderRequest,
    AddTimelineEntryRequest,
    CreateWarRoomRequest,
    ResolveWarRoomRequest,
    Responder,
    ResponderStatus,
    TimelineEntry,
    TimelineEventType,
    WarRoom,
    WarRoomStatus,
    _get_room_or_404,
    _war_rooms,
    add_responder,
    add_timeline_entry,
    create_war_room,
    get_war_room,
    list_war_rooms,
    resolve_war_room,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_store() -> None:
    """Reset the in-memory war room store between tests."""
    _war_rooms.clear()


def _seed_room(
    *,
    room_id: str = "room-001",
    title: str = "P1 API Outage",
    severity: str = "critical",
    status: WarRoomStatus = WarRoomStatus.ACTIVE,
    **kwargs: Any,
) -> WarRoom:
    room = WarRoom(id=room_id, title=title, severity=severity, status=status, **kwargs)
    _war_rooms[room.id] = room
    return room


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_war_room_statuses(self) -> None:
        assert WarRoomStatus.ACTIVE == "active"
        assert WarRoomStatus.RESOLVED == "resolved"
        assert WarRoomStatus.ESCALATED == "escalated"

    def test_timeline_event_types(self) -> None:
        assert TimelineEventType.AGENT_ACTION == "agent_action"
        assert TimelineEventType.HUMAN_NOTE == "human_note"
        assert TimelineEventType.STATUS_CHANGE == "status_change"
        assert TimelineEventType.ESCALATION == "escalation"

    def test_responder_statuses(self) -> None:
        assert ResponderStatus.ACTIVE == "active"
        assert ResponderStatus.PAGED == "paged"
        assert ResponderStatus.ACKNOWLEDGED == "acknowledged"
        assert ResponderStatus.OFFLINE == "offline"


# ---------------------------------------------------------------------------
# _get_room_or_404
# ---------------------------------------------------------------------------


class TestGetRoomOr404:
    def test_existing_room(self) -> None:
        room = _seed_room()
        assert _get_room_or_404(room.id) is room

    def test_missing_room_raises_404(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _get_room_or_404("nonexistent")
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# create_war_room
# ---------------------------------------------------------------------------


class TestCreateWarRoom:
    @pytest.mark.asyncio
    async def test_returns_correct_structure(self) -> None:
        req = CreateWarRoomRequest(
            title="DB failover",
            severity="high",
            incident_id="INC-42",
            description="Primary DB unreachable",
        )
        result = await create_war_room(req)

        assert "war_room" in result
        wr = result["war_room"]
        assert wr["title"] == "DB failover"
        assert wr["severity"] == "high"
        assert wr["status"] == "active"
        assert wr["incident_id"] == "INC-42"
        assert wr["description"] == "Primary DB unreachable"
        assert wr["id"] in _war_rooms

    @pytest.mark.asyncio
    async def test_stored_in_memory(self) -> None:
        req = CreateWarRoomRequest(title="test", severity="low")
        result = await create_war_room(req)
        room_id = result["war_room"]["id"]
        assert room_id in _war_rooms

    @pytest.mark.asyncio
    async def test_default_fields(self) -> None:
        req = CreateWarRoomRequest(title="Minimal", severity="medium")
        result = await create_war_room(req)
        wr = result["war_room"]
        assert wr["incident_id"] is None
        assert wr["description"] is None
        assert wr["timeline"] == []
        assert wr["responders"] == []
        assert wr["resolved_at"] is None


# ---------------------------------------------------------------------------
# list_war_rooms
# ---------------------------------------------------------------------------


class TestListWarRooms:
    @pytest.mark.asyncio
    async def test_empty_store(self) -> None:
        result = await list_war_rooms(status=None, severity=None, limit=50)
        assert result["war_rooms"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_filter_by_status(self) -> None:
        _seed_room(room_id="r1", status=WarRoomStatus.ACTIVE)
        _seed_room(room_id="r2", status=WarRoomStatus.RESOLVED)

        result = await list_war_rooms(status="active", severity=None, limit=50)
        assert result["total"] == 1
        assert result["war_rooms"][0]["id"] == "r1"

    @pytest.mark.asyncio
    async def test_filter_by_severity(self) -> None:
        _seed_room(room_id="r1", severity="critical")
        _seed_room(room_id="r2", severity="low")

        result = await list_war_rooms(status=None, severity="critical", limit=50)
        assert result["total"] == 1
        assert result["war_rooms"][0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_combined_filters(self) -> None:
        _seed_room(room_id="r1", severity="critical", status=WarRoomStatus.ACTIVE)
        _seed_room(room_id="r2", severity="critical", status=WarRoomStatus.RESOLVED)
        _seed_room(room_id="r3", severity="low", status=WarRoomStatus.ACTIVE)

        result = await list_war_rooms(status="active", severity="critical", limit=50)
        assert result["total"] == 1
        assert result["war_rooms"][0]["id"] == "r1"

    @pytest.mark.asyncio
    async def test_limit_applied(self) -> None:
        for i in range(5):
            _seed_room(room_id=f"r{i}", severity="medium")

        result = await list_war_rooms(status=None, severity=None, limit=3)
        assert result["total"] == 3


# ---------------------------------------------------------------------------
# get_war_room
# ---------------------------------------------------------------------------


class TestGetWarRoom:
    @pytest.mark.asyncio
    async def test_existing_room(self) -> None:
        _seed_room(room_id="r1", title="Test Room")
        result = await get_war_room("r1")
        assert result["war_room"]["title"] == "Test Room"

    @pytest.mark.asyncio
    async def test_nonexistent_room_returns_404(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await get_war_room("nonexistent")
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# add_timeline_entry
# ---------------------------------------------------------------------------


class TestAddTimelineEntry:
    @pytest.mark.asyncio
    async def test_add_entry(self) -> None:
        room = _seed_room(room_id="r1")
        req = AddTimelineEntryRequest(
            event_type=TimelineEventType.HUMAN_NOTE,
            actor="ops@example.com",
            content="Investigating DB connections",
            metadata={"source": "manual"},
        )
        result = await add_timeline_entry("r1", req)

        assert "entry" in result
        entry = result["entry"]
        assert entry["event_type"] == "human_note"
        assert entry["actor"] == "ops@example.com"
        assert entry["content"] == "Investigating DB connections"
        assert entry["metadata"] == {"source": "manual"}
        assert len(room.timeline) == 1

    @pytest.mark.asyncio
    async def test_multiple_entries_appended(self) -> None:
        _seed_room(room_id="r1")
        for i in range(3):
            req = AddTimelineEntryRequest(
                event_type=TimelineEventType.AGENT_ACTION,
                actor="agent",
                content=f"Action {i}",
            )
            await add_timeline_entry("r1", req)

        assert len(_war_rooms["r1"].timeline) == 3

    @pytest.mark.asyncio
    async def test_nonexistent_room_returns_404(self) -> None:
        req = AddTimelineEntryRequest(
            event_type=TimelineEventType.HUMAN_NOTE,
            actor="user",
            content="note",
        )
        with pytest.raises(HTTPException) as exc_info:
            await add_timeline_entry("ghost", req)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# add_responder
# ---------------------------------------------------------------------------


class TestAddResponder:
    @pytest.mark.asyncio
    async def test_add_responder(self) -> None:
        room = _seed_room(room_id="r1")
        req = AddResponderRequest(user_id="u1", name="Jane Doe", role="incident_commander")
        result = await add_responder("r1", req)

        resp = result["responder"]
        assert resp["user_id"] == "u1"
        assert resp["name"] == "Jane Doe"
        assert resp["role"] == "incident_commander"
        assert resp["status"] == "active"
        assert len(room.responders) == 1

    @pytest.mark.asyncio
    async def test_duplicate_responder_returns_409(self) -> None:
        room = _seed_room(room_id="r1")
        room.responders.append(
            Responder(user_id="u1", name="Jane Doe", role="incident_commander"),
        )

        req = AddResponderRequest(user_id="u1", name="Jane Doe", role="comms_lead")
        with pytest.raises(HTTPException) as exc_info:
            await add_responder("r1", req)
        assert exc_info.value.status_code == 409
        assert "already" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_nonexistent_room_returns_404(self) -> None:
        req = AddResponderRequest(user_id="u1", name="Test", role="ops")
        with pytest.raises(HTTPException) as exc_info:
            await add_responder("ghost", req)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# resolve_war_room
# ---------------------------------------------------------------------------


class TestResolveWarRoom:
    @pytest.mark.asyncio
    async def test_resolve_active_room(self) -> None:
        _seed_room(room_id="r1")
        req = ResolveWarRoomRequest(resolution_summary="Root cause was a bad deploy")
        result = await resolve_war_room("r1", req)

        wr = result["war_room"]
        assert wr["status"] == "resolved"
        assert wr["resolved_at"] is not None

    @pytest.mark.asyncio
    async def test_resolve_already_resolved_returns_400(self) -> None:
        _seed_room(room_id="r1", status=WarRoomStatus.RESOLVED)
        req = ResolveWarRoomRequest(resolution_summary="duplicate")

        with pytest.raises(HTTPException) as exc_info:
            await resolve_war_room("r1", req)
        assert exc_info.value.status_code == 400
        assert "already resolved" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_resolve_adds_timeline_entry(self) -> None:
        _seed_room(room_id="r1")
        req = ResolveWarRoomRequest(resolution_summary="Fixed by rollback")
        await resolve_war_room("r1", req)

        room = _war_rooms["r1"]
        assert len(room.timeline) == 1
        entry = room.timeline[0]
        assert entry.event_type == TimelineEventType.STATUS_CHANGE
        assert entry.actor == "system"
        assert entry.content == "Fixed by rollback"

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_room_returns_404(self) -> None:
        req = ResolveWarRoomRequest(resolution_summary="n/a")
        with pytest.raises(HTTPException) as exc_info:
            await resolve_war_room("ghost", req)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_resolve_escalated_room_succeeds(self) -> None:
        _seed_room(room_id="r1", status=WarRoomStatus.ESCALATED)
        req = ResolveWarRoomRequest(resolution_summary="Escalation resolved")
        result = await resolve_war_room("r1", req)
        assert result["war_room"]["status"] == "resolved"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModelDefaults:
    def test_war_room_defaults(self) -> None:
        room = WarRoom(title="test", severity="low")
        assert room.status == WarRoomStatus.ACTIVE
        assert room.timeline == []
        assert room.responders == []
        assert room.id  # auto-generated

    def test_timeline_entry_auto_id(self) -> None:
        entry = TimelineEntry(
            event_type=TimelineEventType.HUMAN_NOTE,
            actor="user",
            content="note",
        )
        assert entry.id  # auto-generated hex string

    def test_responder_default_status(self) -> None:
        resp = Responder(user_id="u1", name="Test", role="ops")
        assert resp.status == ResponderStatus.ACTIVE
