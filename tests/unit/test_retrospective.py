"""Tests for the incident retrospective module.

Covers:
- RetroStatus enum values
- ActionItemPriority enum values
- ActionItem model defaults and full creation
- Retrospective model defaults and full creation
- RetrospectiveManager creation and defaults
- create_retrospective() with all params, minimal, auto schedule, max limit
- start_retrospective() found, not found
- complete_retrospective() with all fields, partial, not found
- cancel_retrospective() found, not found
- add_action_item() with all params, minimal, not found
- complete_action_item() found, not found, missing retro
- get_retrospective() found and not found
- list_retrospectives() all, filter by status, filter by incident_id, combined
- get_overdue_actions() overdue detected, not overdue, completed excluded
- get_stats() empty and populated
"""

from __future__ import annotations

import time

import pytest

from shieldops.incidents.retrospective import (
    ActionItem,
    ActionItemPriority,
    Retrospective,
    RetrospectiveManager,
    RetroStatus,
)

# -- Helpers ----------------------------------------------------------


def _make_manager(**kwargs) -> RetrospectiveManager:
    """Return a fresh RetrospectiveManager with optional overrides."""
    return RetrospectiveManager(**kwargs)


def _make_retro(
    mgr: RetrospectiveManager,
    incident_id: str = "inc-001",
    title: str = "DB outage postmortem",
    **kwargs,
) -> Retrospective:
    """Create and return a retrospective through the manager."""
    return mgr.create_retrospective(
        incident_id=incident_id,
        title=title,
        **kwargs,
    )


# -- Fixtures ---------------------------------------------------------


@pytest.fixture()
def manager() -> RetrospectiveManager:
    """Return a fresh RetrospectiveManager."""
    return RetrospectiveManager()


@pytest.fixture()
def populated_manager() -> RetrospectiveManager:
    """Return a manager with several retros in various states."""
    mgr = RetrospectiveManager()
    r1 = mgr.create_retrospective(
        incident_id="inc-001",
        title="DB outage",
        facilitator="alice",
        participants=["alice", "bob"],
    )
    mgr.add_action_item(
        r1.id,
        "Add DB monitoring",
        assignee="bob",
        priority=ActionItemPriority.HIGH,
        due_date=time.time() - 3600,  # overdue
    )
    mgr.add_action_item(
        r1.id,
        "Update runbook",
        assignee="alice",
        due_date=time.time() + 86400,  # future
    )

    r2 = mgr.create_retrospective(
        incident_id="inc-002",
        title="API latency",
    )
    mgr.start_retrospective(r2.id)

    r3 = mgr.create_retrospective(
        incident_id="inc-001",
        title="DB outage follow-up",
    )
    mgr.complete_retrospective(
        r3.id,
        root_cause="Connection pool exhaustion",
    )
    return mgr


# -- Enum Tests -------------------------------------------------------


class TestRetroStatusEnum:
    def test_scheduled_value(self) -> None:
        assert RetroStatus.SCHEDULED == "scheduled"

    def test_in_progress_value(self) -> None:
        assert RetroStatus.IN_PROGRESS == "in_progress"

    def test_completed_value(self) -> None:
        assert RetroStatus.COMPLETED == "completed"

    def test_cancelled_value(self) -> None:
        assert RetroStatus.CANCELLED == "cancelled"

    def test_all_members(self) -> None:
        members = {m.value for m in RetroStatus}
        expected = {"scheduled", "in_progress", "completed", "cancelled"}
        assert members == expected


class TestActionItemPriorityEnum:
    def test_low_value(self) -> None:
        assert ActionItemPriority.LOW == "low"

    def test_medium_value(self) -> None:
        assert ActionItemPriority.MEDIUM == "medium"

    def test_high_value(self) -> None:
        assert ActionItemPriority.HIGH == "high"

    def test_critical_value(self) -> None:
        assert ActionItemPriority.CRITICAL == "critical"

    def test_all_members(self) -> None:
        members = {m.value for m in ActionItemPriority}
        assert members == {"low", "medium", "high", "critical"}


# -- Model Tests ------------------------------------------------------


class TestActionItemModel:
    def test_defaults(self) -> None:
        item = ActionItem(description="Fix monitoring")
        assert item.description == "Fix monitoring"
        assert item.assignee == ""
        assert item.priority == ActionItemPriority.MEDIUM
        assert item.status == "open"
        assert item.due_date is None
        assert item.completed_at is None
        assert item.created_at > 0
        assert len(item.id) == 12

    def test_unique_ids(self) -> None:
        a1 = ActionItem(description="A")
        a2 = ActionItem(description="B")
        assert a1.id != a2.id

    def test_full_creation(self) -> None:
        now = time.time()
        item = ActionItem(
            description="Add alerts",
            assignee="bob",
            priority=ActionItemPriority.CRITICAL,
            due_date=now + 86400,
        )
        assert item.assignee == "bob"
        assert item.priority == ActionItemPriority.CRITICAL
        assert item.due_date == pytest.approx(now + 86400, abs=1)


class TestRetrospectiveModel:
    def test_defaults(self) -> None:
        r = Retrospective(incident_id="inc-1", title="Postmortem")
        assert r.incident_id == "inc-1"
        assert r.title == "Postmortem"
        assert r.status == RetroStatus.SCHEDULED
        assert r.scheduled_at is None
        assert r.timeline == ""
        assert r.root_cause == ""
        assert r.impact_summary == ""
        assert r.lessons_learned == []
        assert r.action_items == []
        assert r.facilitator == ""
        assert r.participants == []
        assert r.metadata == {}
        assert r.created_at > 0
        assert r.completed_at is None
        assert len(r.id) == 12

    def test_full_creation(self) -> None:
        r = Retrospective(
            incident_id="inc-1",
            title="Full postmortem",
            facilitator="alice",
            participants=["alice", "bob"],
            metadata={"team": "platform"},
        )
        assert r.facilitator == "alice"
        assert r.participants == ["alice", "bob"]
        assert r.metadata == {"team": "platform"}


# -- Manager Creation -------------------------------------------------


class TestManagerCreation:
    def test_default_params(self) -> None:
        mgr = RetrospectiveManager()
        assert mgr._max_retros == 500
        assert mgr._default_schedule_hours == 48

    def test_custom_params(self) -> None:
        mgr = RetrospectiveManager(max_retros=10, default_schedule_hours=24)
        assert mgr._max_retros == 10
        assert mgr._default_schedule_hours == 24

    def test_starts_empty(self) -> None:
        mgr = RetrospectiveManager()
        assert len(mgr._retros) == 0


# -- create_retrospective ---------------------------------------------


class TestCreateRetrospective:
    def test_minimal(self, manager: RetrospectiveManager) -> None:
        retro = manager.create_retrospective(incident_id="inc-1", title="Postmortem")
        assert retro.incident_id == "inc-1"
        assert retro.title == "Postmortem"
        assert retro.status == RetroStatus.SCHEDULED
        assert retro.scheduled_at is not None

    def test_auto_schedule_default(self, manager: RetrospectiveManager) -> None:
        before = time.time()
        retro = manager.create_retrospective("inc-1", "PM")
        expected = before + 48 * 3600
        assert retro.scheduled_at == pytest.approx(expected, abs=5)

    def test_custom_scheduled_at(self, manager: RetrospectiveManager) -> None:
        ts = time.time() + 7200
        retro = manager.create_retrospective("inc-1", "PM", scheduled_at=ts)
        assert retro.scheduled_at == pytest.approx(ts, abs=1)

    def test_all_params(self, manager: RetrospectiveManager) -> None:
        retro = manager.create_retrospective(
            incident_id="inc-1",
            title="Full PM",
            scheduled_at=time.time() + 3600,
            facilitator="alice",
            participants=["alice", "bob"],
            metadata={"severity": "P1"},
        )
        assert retro.facilitator == "alice"
        assert retro.participants == ["alice", "bob"]
        assert retro.metadata == {"severity": "P1"}

    def test_stored_in_manager(self, manager: RetrospectiveManager) -> None:
        retro = manager.create_retrospective("inc-1", "PM")
        assert manager.get_retrospective(retro.id) is not None

    def test_max_limit_raises(self) -> None:
        mgr = RetrospectiveManager(max_retros=2)
        mgr.create_retrospective("inc-1", "PM 1")
        mgr.create_retrospective("inc-2", "PM 2")
        with pytest.raises(ValueError, match="Maximum retrospectives limit reached"):
            mgr.create_retrospective("inc-3", "PM 3")

    def test_none_participants_becomes_empty_list(self, manager: RetrospectiveManager) -> None:
        retro = manager.create_retrospective("inc-1", "PM", participants=None)
        assert retro.participants == []

    def test_none_metadata_becomes_empty_dict(self, manager: RetrospectiveManager) -> None:
        retro = manager.create_retrospective("inc-1", "PM", metadata=None)
        assert retro.metadata == {}

    def test_returns_retrospective_instance(self, manager: RetrospectiveManager) -> None:
        retro = manager.create_retrospective("inc-1", "PM")
        assert isinstance(retro, Retrospective)


# -- start_retrospective ----------------------------------------------


class TestStartRetrospective:
    def test_basic(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        result = manager.start_retrospective(retro.id)
        assert result is not None
        assert result.status == RetroStatus.IN_PROGRESS

    def test_not_found_returns_none(self, manager: RetrospectiveManager) -> None:
        result = manager.start_retrospective("bad-id")
        assert result is None


# -- complete_retrospective -------------------------------------------


class TestCompleteRetrospective:
    def test_basic(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        result = manager.complete_retrospective(retro.id)
        assert result is not None
        assert result.status == RetroStatus.COMPLETED
        assert result.completed_at is not None

    def test_with_all_fields(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        result = manager.complete_retrospective(
            retro.id,
            timeline="10:00 alert, 10:05 ack, 10:30 resolved",
            root_cause="Memory leak in cache",
            impact_summary="2000 users affected for 30 min",
            lessons_learned=["Add memory alerts", "Improve docs"],
        )
        assert result.timeline.startswith("10:00")
        assert result.root_cause == "Memory leak in cache"
        assert result.impact_summary == "2000 users affected for 30 min"
        assert len(result.lessons_learned) == 2

    def test_empty_fields_left_default(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        result = manager.complete_retrospective(retro.id)
        assert result.timeline == ""
        assert result.root_cause == ""
        assert result.impact_summary == ""
        assert result.lessons_learned == []

    def test_not_found_returns_none(self, manager: RetrospectiveManager) -> None:
        result = manager.complete_retrospective("bad-id")
        assert result is None

    def test_completed_at_is_recent(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        before = time.time()
        result = manager.complete_retrospective(retro.id)
        after = time.time()
        assert before <= result.completed_at <= after


# -- cancel_retrospective ---------------------------------------------


class TestCancelRetrospective:
    def test_basic(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        result = manager.cancel_retrospective(retro.id)
        assert result is not None
        assert result.status == RetroStatus.CANCELLED

    def test_not_found_returns_none(self, manager: RetrospectiveManager) -> None:
        result = manager.cancel_retrospective("bad-id")
        assert result is None


# -- add_action_item --------------------------------------------------


class TestAddActionItem:
    def test_basic(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        item = manager.add_action_item(retro.id, "Add monitoring")
        assert item is not None
        assert item.description == "Add monitoring"
        assert item.status == "open"

    def test_all_params(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        due = time.time() + 86400
        item = manager.add_action_item(
            retro.id,
            "Fix alerting",
            assignee="bob",
            priority=ActionItemPriority.CRITICAL,
            due_date=due,
        )
        assert item.assignee == "bob"
        assert item.priority == ActionItemPriority.CRITICAL
        assert item.due_date == pytest.approx(due, abs=1)

    def test_default_priority_is_medium(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        item = manager.add_action_item(retro.id, "Task")
        assert item.priority == ActionItemPriority.MEDIUM

    def test_not_found_returns_none(self, manager: RetrospectiveManager) -> None:
        result = manager.add_action_item("bad-id", "Task")
        assert result is None

    def test_stored_in_retro(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        manager.add_action_item(retro.id, "Task 1")
        manager.add_action_item(retro.id, "Task 2")
        assert len(retro.action_items) == 2

    def test_returns_action_item_instance(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        item = manager.add_action_item(retro.id, "Task")
        assert isinstance(item, ActionItem)


# -- complete_action_item ---------------------------------------------


class TestCompleteActionItem:
    def test_basic(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        item = manager.add_action_item(retro.id, "Fix it")
        result = manager.complete_action_item(retro.id, item.id)
        assert result is not None
        assert result.status == "completed"
        assert result.completed_at is not None

    def test_retro_not_found_returns_none(self, manager: RetrospectiveManager) -> None:
        result = manager.complete_action_item("bad-retro", "bad")
        assert result is None

    def test_item_not_found_returns_none(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        result = manager.complete_action_item(retro.id, "bad-item")
        assert result is None

    def test_completed_at_is_recent(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        item = manager.add_action_item(retro.id, "Task")
        before = time.time()
        manager.complete_action_item(retro.id, item.id)
        after = time.time()
        assert before <= item.completed_at <= after


# -- get_retrospective ------------------------------------------------


class TestGetRetrospective:
    def test_found(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        result = manager.get_retrospective(retro.id)
        assert result is not None
        assert result.id == retro.id

    def test_not_found(self, manager: RetrospectiveManager) -> None:
        assert manager.get_retrospective("nonexistent") is None

    def test_empty_manager(self, manager: RetrospectiveManager) -> None:
        assert manager.get_retrospective("any") is None


# -- list_retrospectives ----------------------------------------------


class TestListRetrospectives:
    def test_all(self, populated_manager: RetrospectiveManager) -> None:
        retros = populated_manager.list_retrospectives()
        assert len(retros) == 3

    def test_filter_by_status_scheduled(self, populated_manager: RetrospectiveManager) -> None:
        retros = populated_manager.list_retrospectives(status=RetroStatus.SCHEDULED)
        assert len(retros) == 1
        assert retros[0].status == RetroStatus.SCHEDULED

    def test_filter_by_status_in_progress(self, populated_manager: RetrospectiveManager) -> None:
        retros = populated_manager.list_retrospectives(status=RetroStatus.IN_PROGRESS)
        assert len(retros) == 1

    def test_filter_by_incident_id(self, populated_manager: RetrospectiveManager) -> None:
        retros = populated_manager.list_retrospectives(incident_id="inc-001")
        assert len(retros) == 2

    def test_combined_filters(self, populated_manager: RetrospectiveManager) -> None:
        retros = populated_manager.list_retrospectives(
            status=RetroStatus.COMPLETED,
            incident_id="inc-001",
        )
        assert len(retros) == 1
        assert retros[0].status == RetroStatus.COMPLETED

    def test_no_match(self, populated_manager: RetrospectiveManager) -> None:
        retros = populated_manager.list_retrospectives(status=RetroStatus.CANCELLED)
        assert retros == []

    def test_empty_manager(self, manager: RetrospectiveManager) -> None:
        assert manager.list_retrospectives() == []


# -- get_overdue_actions ----------------------------------------------


class TestGetOverdueActions:
    def test_overdue_detected(self, populated_manager: RetrospectiveManager) -> None:
        overdue = populated_manager.get_overdue_actions()
        assert len(overdue) >= 1
        assert overdue[0]["description"] == "Add DB monitoring"

    def test_overdue_entry_keys(self, populated_manager: RetrospectiveManager) -> None:
        overdue = populated_manager.get_overdue_actions()
        entry = overdue[0]
        expected_keys = {
            "retro_id",
            "incident_id",
            "item_id",
            "description",
            "assignee",
            "priority",
            "due_date",
            "overdue_seconds",
        }
        assert set(entry.keys()) == expected_keys

    def test_future_due_date_not_overdue(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        manager.add_action_item(
            retro.id,
            "Future task",
            due_date=time.time() + 86400,
        )
        overdue = manager.get_overdue_actions()
        assert len(overdue) == 0

    def test_no_due_date_not_overdue(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        manager.add_action_item(retro.id, "No deadline")
        overdue = manager.get_overdue_actions()
        assert len(overdue) == 0

    def test_completed_item_not_overdue(self, manager: RetrospectiveManager) -> None:
        retro = _make_retro(manager)
        item = manager.add_action_item(
            retro.id,
            "Done task",
            due_date=time.time() - 3600,
        )
        manager.complete_action_item(retro.id, item.id)
        overdue = manager.get_overdue_actions()
        assert len(overdue) == 0

    def test_overdue_seconds_positive(self, populated_manager: RetrospectiveManager) -> None:
        overdue = populated_manager.get_overdue_actions()
        for entry in overdue:
            assert entry["overdue_seconds"] > 0

    def test_empty_manager(self, manager: RetrospectiveManager) -> None:
        assert manager.get_overdue_actions() == []


# -- get_stats --------------------------------------------------------


class TestGetStats:
    def test_empty_manager(self, manager: RetrospectiveManager) -> None:
        stats = manager.get_stats()
        assert stats["total_retrospectives"] == 0
        assert stats["scheduled"] == 0
        assert stats["in_progress"] == 0
        assert stats["completed"] == 0
        assert stats["total_action_items"] == 0
        assert stats["open_action_items"] == 0
        assert stats["overdue_action_items"] == 0

    def test_populated(self, populated_manager: RetrospectiveManager) -> None:
        stats = populated_manager.get_stats()
        assert stats["total_retrospectives"] == 3
        assert stats["scheduled"] == 1
        assert stats["in_progress"] == 1
        assert stats["completed"] == 1
        assert stats["total_action_items"] == 2
        assert stats["open_action_items"] == 2
        assert stats["overdue_action_items"] >= 1

    def test_stats_keys(self, manager: RetrospectiveManager) -> None:
        stats = manager.get_stats()
        expected_keys = {
            "total_retrospectives",
            "scheduled",
            "in_progress",
            "completed",
            "total_action_items",
            "open_action_items",
            "overdue_action_items",
        }
        assert set(stats.keys()) == expected_keys
