"""Tests for the incident war room module.

Covers:
- WarRoomStatus enum values
- ParticipantRole enum values
- WarRoomParticipant model defaults and full creation
- WarRoomAction model defaults and full creation
- WarRoom model defaults and full creation
- WarRoomManager creation and defaults
- create_room() with all params, minimal, max limit
- add_participant() found, not found, status transition OPEN->ACTIVE
- add_action() found, not found
- complete_action() found, not found, missing room
- resolve_room() found, not found, with summary
- close_room() found, not found
- get_room() found and not found
- list_rooms() all, filtered by status, empty
- get_stale_rooms() stale, not stale, closed excluded
- get_stats() empty and populated
"""

from __future__ import annotations

import time

import pytest

from shieldops.incidents.war_room import (
    ParticipantRole,
    WarRoom,
    WarRoomAction,
    WarRoomManager,
    WarRoomParticipant,
    WarRoomStatus,
)

# -- Helpers ----------------------------------------------------------


def _make_manager(**kwargs) -> WarRoomManager:
    """Return a fresh WarRoomManager with optional overrides."""
    return WarRoomManager(**kwargs)


def _make_room(
    mgr: WarRoomManager,
    incident_id: str = "inc-001",
    title: str = "DB outage",
    **kwargs,
) -> WarRoom:
    """Create and return a war room through the manager."""
    return mgr.create_room(
        incident_id=incident_id,
        title=title,
        **kwargs,
    )


# -- Fixtures ---------------------------------------------------------


@pytest.fixture()
def manager() -> WarRoomManager:
    """Return a fresh WarRoomManager."""
    return WarRoomManager()


@pytest.fixture()
def populated_manager() -> WarRoomManager:
    """Return a manager with several rooms in various states."""
    mgr = WarRoomManager()
    r1 = mgr.create_room(
        incident_id="inc-001",
        title="DB outage",
        severity="P1",
        created_by="alice",
    )
    mgr.add_participant(r1.id, "u1", "Alice", ParticipantRole.COMMANDER)
    mgr.add_action(r1.id, "Restart primary", assignee="bob")

    r2 = mgr.create_room(
        incident_id="inc-002",
        title="API latency",
        severity="P2",
    )
    mgr.add_participant(r2.id, "u2", "Bob")

    r3 = mgr.create_room(
        incident_id="inc-003",
        title="Old incident",
    )
    mgr.resolve_room(r3.id, summary="Fixed")
    return mgr


# -- Enum Tests -------------------------------------------------------


class TestWarRoomStatusEnum:
    def test_open_value(self) -> None:
        assert WarRoomStatus.OPEN == "open"

    def test_active_value(self) -> None:
        assert WarRoomStatus.ACTIVE == "active"

    def test_resolved_value(self) -> None:
        assert WarRoomStatus.RESOLVED == "resolved"

    def test_closed_value(self) -> None:
        assert WarRoomStatus.CLOSED == "closed"

    def test_all_members(self) -> None:
        members = {m.value for m in WarRoomStatus}
        assert members == {"open", "active", "resolved", "closed"}


class TestParticipantRoleEnum:
    def test_commander_value(self) -> None:
        assert ParticipantRole.COMMANDER == "commander"

    def test_responder_value(self) -> None:
        assert ParticipantRole.RESPONDER == "responder"

    def test_observer_value(self) -> None:
        assert ParticipantRole.OBSERVER == "observer"

    def test_communicator_value(self) -> None:
        assert ParticipantRole.COMMUNICATOR == "communicator"

    def test_all_members(self) -> None:
        members = {m.value for m in ParticipantRole}
        expected = {"commander", "responder", "observer", "communicator"}
        assert members == expected


# -- Model Tests ------------------------------------------------------


class TestWarRoomParticipantModel:
    def test_defaults(self) -> None:
        p = WarRoomParticipant(user_id="u1", name="Alice")
        assert p.user_id == "u1"
        assert p.name == "Alice"
        assert p.role == ParticipantRole.RESPONDER
        assert p.joined_at > 0
        assert len(p.id) == 12

    def test_unique_ids(self) -> None:
        p1 = WarRoomParticipant(user_id="u1", name="A")
        p2 = WarRoomParticipant(user_id="u2", name="B")
        assert p1.id != p2.id

    def test_custom_role(self) -> None:
        p = WarRoomParticipant(
            user_id="u1",
            name="Alice",
            role=ParticipantRole.COMMANDER,
        )
        assert p.role == ParticipantRole.COMMANDER


class TestWarRoomActionModel:
    def test_defaults(self) -> None:
        a = WarRoomAction(war_room_id="wr-1", description="Fix it")
        assert a.war_room_id == "wr-1"
        assert a.description == "Fix it"
        assert a.assignee == ""
        assert a.status == "pending"
        assert a.created_at > 0
        assert a.completed_at is None
        assert len(a.id) == 12

    def test_full_creation(self) -> None:
        a = WarRoomAction(
            war_room_id="wr-1",
            description="Restart",
            assignee="bob",
            status="completed",
        )
        assert a.assignee == "bob"
        assert a.status == "completed"


class TestWarRoomModel:
    def test_defaults(self) -> None:
        r = WarRoom(incident_id="inc-1", title="Outage")
        assert r.incident_id == "inc-1"
        assert r.title == "Outage"
        assert r.severity == "P2"
        assert r.status == WarRoomStatus.OPEN
        assert r.participants == []
        assert r.actions == []
        assert r.summary == ""
        assert r.created_by == ""
        assert r.metadata == {}
        assert r.created_at > 0
        assert r.resolved_at is None
        assert len(r.id) == 12

    def test_full_creation(self) -> None:
        r = WarRoom(
            incident_id="inc-1",
            title="Full outage",
            severity="P1",
            created_by="alice",
            metadata={"env": "prod"},
        )
        assert r.severity == "P1"
        assert r.created_by == "alice"
        assert r.metadata == {"env": "prod"}


# -- Manager Creation -------------------------------------------------


class TestManagerCreation:
    def test_default_params(self) -> None:
        mgr = WarRoomManager()
        assert mgr._max_rooms == 200
        assert mgr._auto_escalate_minutes == 30

    def test_custom_params(self) -> None:
        mgr = WarRoomManager(max_rooms=5, auto_escalate_minutes=10)
        assert mgr._max_rooms == 5
        assert mgr._auto_escalate_minutes == 10

    def test_starts_empty(self) -> None:
        mgr = WarRoomManager()
        assert len(mgr._rooms) == 0


# -- create_room ------------------------------------------------------


class TestCreateRoom:
    def test_minimal(self, manager: WarRoomManager) -> None:
        room = manager.create_room(
            incident_id="inc-1",
            title="Outage",
        )
        assert room.incident_id == "inc-1"
        assert room.title == "Outage"
        assert room.severity == "P2"
        assert room.status == WarRoomStatus.OPEN

    def test_all_params(self, manager: WarRoomManager) -> None:
        room = manager.create_room(
            incident_id="inc-1",
            title="DB down",
            severity="P1",
            created_by="alice",
            metadata={"team": "platform"},
        )
        assert room.severity == "P1"
        assert room.created_by == "alice"
        assert room.metadata == {"team": "platform"}

    def test_stored_in_manager(self, manager: WarRoomManager) -> None:
        room = manager.create_room("inc-1", "Test")
        assert manager.get_room(room.id) is not None

    def test_max_limit_raises(self) -> None:
        mgr = WarRoomManager(max_rooms=2)
        mgr.create_room("inc-1", "Room 1")
        mgr.create_room("inc-2", "Room 2")
        with pytest.raises(ValueError, match="Maximum rooms limit reached"):
            mgr.create_room("inc-3", "Room 3")

    def test_none_metadata_becomes_empty_dict(self, manager: WarRoomManager) -> None:
        room = manager.create_room("inc-1", "Test", metadata=None)
        assert room.metadata == {}

    def test_returns_war_room_instance(self, manager: WarRoomManager) -> None:
        room = manager.create_room("inc-1", "Test")
        assert isinstance(room, WarRoom)


# -- add_participant --------------------------------------------------


class TestAddParticipant:
    def test_basic(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        p = manager.add_participant(room.id, "u1", "Alice", ParticipantRole.COMMANDER)
        assert p is not None
        assert p.user_id == "u1"
        assert p.name == "Alice"
        assert p.role == ParticipantRole.COMMANDER

    def test_default_role_is_responder(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        p = manager.add_participant(room.id, "u1", "Alice")
        assert p.role == ParticipantRole.RESPONDER

    def test_transitions_open_to_active(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        assert room.status == WarRoomStatus.OPEN
        manager.add_participant(room.id, "u1", "Alice")
        assert room.status == WarRoomStatus.ACTIVE

    def test_already_active_stays_active(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        manager.add_participant(room.id, "u1", "Alice")
        assert room.status == WarRoomStatus.ACTIVE
        manager.add_participant(room.id, "u2", "Bob")
        assert room.status == WarRoomStatus.ACTIVE

    def test_not_found_raises(self, manager: WarRoomManager) -> None:
        with pytest.raises(ValueError, match="War room not found"):
            manager.add_participant("bad-id", "u1", "Alice")

    def test_multiple_participants(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        manager.add_participant(room.id, "u1", "Alice")
        manager.add_participant(room.id, "u2", "Bob")
        assert len(room.participants) == 2


# -- add_action -------------------------------------------------------


class TestAddAction:
    def test_basic(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        action = manager.add_action(room.id, "Restart DB", assignee="bob")
        assert action is not None
        assert action.description == "Restart DB"
        assert action.assignee == "bob"
        assert action.status == "pending"

    def test_not_found_returns_none(self, manager: WarRoomManager) -> None:
        result = manager.add_action("bad-id", "Do something")
        assert result is None

    def test_action_stored_in_room(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        manager.add_action(room.id, "Task 1")
        assert len(room.actions) == 1

    def test_multiple_actions(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        manager.add_action(room.id, "Task 1")
        manager.add_action(room.id, "Task 2")
        assert len(room.actions) == 2

    def test_default_assignee_is_empty(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        action = manager.add_action(room.id, "Task 1")
        assert action.assignee == ""


# -- complete_action --------------------------------------------------


class TestCompleteAction:
    def test_basic(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        action = manager.add_action(room.id, "Fix it")
        result = manager.complete_action(room.id, action.id)
        assert result is not None
        assert result.status == "completed"
        assert result.completed_at is not None

    def test_room_not_found_returns_none(self, manager: WarRoomManager) -> None:
        result = manager.complete_action("bad-room", "bad-action")
        assert result is None

    def test_action_not_found_returns_none(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        result = manager.complete_action(room.id, "bad-action")
        assert result is None

    def test_completed_at_is_recent(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        action = manager.add_action(room.id, "Fix")
        before = time.time()
        manager.complete_action(room.id, action.id)
        after = time.time()
        assert before <= action.completed_at <= after


# -- resolve_room -----------------------------------------------------


class TestResolveRoom:
    def test_basic(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        result = manager.resolve_room(room.id)
        assert result is not None
        assert result.status == WarRoomStatus.RESOLVED
        assert result.resolved_at is not None

    def test_with_summary(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        result = manager.resolve_room(room.id, summary="Root cause: OOM")
        assert result.summary == "Root cause: OOM"

    def test_empty_summary_leaves_default(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        result = manager.resolve_room(room.id)
        assert result.summary == ""

    def test_not_found_returns_none(self, manager: WarRoomManager) -> None:
        result = manager.resolve_room("bad-id")
        assert result is None


# -- close_room -------------------------------------------------------


class TestCloseRoom:
    def test_basic(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        result = manager.close_room(room.id)
        assert result is not None
        assert result.status == WarRoomStatus.CLOSED

    def test_not_found_returns_none(self, manager: WarRoomManager) -> None:
        result = manager.close_room("bad-id")
        assert result is None

    def test_close_after_resolve(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        manager.resolve_room(room.id)
        result = manager.close_room(room.id)
        assert result.status == WarRoomStatus.CLOSED


# -- get_room ---------------------------------------------------------


class TestGetRoom:
    def test_found(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        result = manager.get_room(room.id)
        assert result is not None
        assert result.id == room.id

    def test_not_found(self, manager: WarRoomManager) -> None:
        assert manager.get_room("nonexistent") is None

    def test_empty_manager(self, manager: WarRoomManager) -> None:
        assert manager.get_room("any") is None


# -- list_rooms -------------------------------------------------------


class TestListRooms:
    def test_all_rooms(self, populated_manager: WarRoomManager) -> None:
        rooms = populated_manager.list_rooms()
        assert len(rooms) == 3

    def test_filter_by_active(self, populated_manager: WarRoomManager) -> None:
        rooms = populated_manager.list_rooms(status=WarRoomStatus.ACTIVE)
        assert len(rooms) == 2
        for r in rooms:
            assert r.status == WarRoomStatus.ACTIVE

    def test_filter_by_resolved(self, populated_manager: WarRoomManager) -> None:
        rooms = populated_manager.list_rooms(status=WarRoomStatus.RESOLVED)
        assert len(rooms) == 1
        assert rooms[0].status == WarRoomStatus.RESOLVED

    def test_filter_no_match(self, populated_manager: WarRoomManager) -> None:
        rooms = populated_manager.list_rooms(status=WarRoomStatus.CLOSED)
        assert rooms == []

    def test_empty_manager(self, manager: WarRoomManager) -> None:
        assert manager.list_rooms() == []


# -- get_stale_rooms --------------------------------------------------


class TestGetStaleRooms:
    def test_no_stale_rooms_fresh(self, manager: WarRoomManager) -> None:
        _make_room(manager)
        stale = manager.get_stale_rooms()
        assert stale == []

    def test_stale_room_detected(self) -> None:
        mgr = WarRoomManager(auto_escalate_minutes=0)
        room = _make_room(mgr)
        # created_at is in the past relative to threshold=0
        stale = mgr.get_stale_rooms()
        assert len(stale) >= 1
        assert room.id in [r.id for r in stale]

    def test_resolved_rooms_excluded(self) -> None:
        mgr = WarRoomManager(auto_escalate_minutes=0)
        room = _make_room(mgr)
        mgr.resolve_room(room.id)
        stale = mgr.get_stale_rooms()
        assert len(stale) == 0

    def test_closed_rooms_excluded(self) -> None:
        mgr = WarRoomManager(auto_escalate_minutes=0)
        room = _make_room(mgr)
        mgr.close_room(room.id)
        stale = mgr.get_stale_rooms()
        assert len(stale) == 0

    def test_recent_action_prevents_staleness(self) -> None:
        mgr = WarRoomManager(auto_escalate_minutes=60)
        room = _make_room(mgr)
        action = mgr.add_action(room.id, "Fix it")
        mgr.complete_action(room.id, action.id)
        stale = mgr.get_stale_rooms()
        assert len(stale) == 0


# -- get_stats --------------------------------------------------------


class TestGetStats:
    def test_empty_manager(self, manager: WarRoomManager) -> None:
        stats = manager.get_stats()
        assert stats["total_rooms"] == 0
        assert stats["open_rooms"] == 0
        assert stats["active_rooms"] == 0
        assert stats["resolved_rooms"] == 0
        assert stats["stale_rooms"] == 0
        assert stats["total_actions"] == 0
        assert stats["completed_actions"] == 0

    def test_populated(self, populated_manager: WarRoomManager) -> None:
        stats = populated_manager.get_stats()
        assert stats["total_rooms"] == 3
        assert stats["active_rooms"] == 2
        assert stats["resolved_rooms"] == 1
        assert stats["total_actions"] == 1
        assert stats["completed_actions"] == 0

    def test_completed_action_counted(self, manager: WarRoomManager) -> None:
        room = _make_room(manager)
        action = manager.add_action(room.id, "Fix")
        manager.complete_action(room.id, action.id)
        stats = manager.get_stats()
        assert stats["total_actions"] == 1
        assert stats["completed_actions"] == 1

    def test_stats_keys(self, manager: WarRoomManager) -> None:
        stats = manager.get_stats()
        expected_keys = {
            "total_rooms",
            "open_rooms",
            "active_rooms",
            "resolved_rooms",
            "stale_rooms",
            "total_actions",
            "completed_actions",
        }
        assert set(stats.keys()) == expected_keys
