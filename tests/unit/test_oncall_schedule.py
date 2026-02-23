"""Tests for shieldops.integrations.oncall.schedule – OnCallScheduleManager."""

from __future__ import annotations

import time

import pytest

from shieldops.integrations.oncall.schedule import (
    OnCallOverride,
    OnCallRotation,
    OnCallSchedule,
    OnCallScheduleManager,
    OnCallShift,
    RotationType,
    ScheduleStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _manager(**kwargs) -> OnCallScheduleManager:
    return OnCallScheduleManager(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_rotation_type_values(self):
        assert RotationType.DAILY == "daily"
        assert RotationType.WEEKLY == "weekly"
        assert RotationType.CUSTOM == "custom"

    def test_schedule_status_values(self):
        assert ScheduleStatus.ACTIVE == "active"
        assert ScheduleStatus.PAUSED == "paused"
        assert ScheduleStatus.ARCHIVED == "archived"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_oncall_shift_model(self):
        s = OnCallShift(user="alice", start_time=1.0, end_time=2.0)
        assert s.user == "alice"
        assert s.is_override is False

    def test_oncall_rotation_defaults(self):
        r = OnCallRotation()
        assert r.rotation_type == RotationType.WEEKLY
        assert r.rotation_interval_hours == 168.0
        assert r.handoff_time_hour == 9

    def test_oncall_schedule_defaults(self):
        s = OnCallSchedule(name="primary")
        assert s.status == ScheduleStatus.ACTIVE
        assert s.timezone == "UTC"

    def test_oncall_override_model(self):
        o = OnCallOverride(schedule_id="s1", user="bob", start_time=1.0, end_time=2.0)
        assert o.user == "bob"
        assert o.reason == ""


# ---------------------------------------------------------------------------
# Schedule creation
# ---------------------------------------------------------------------------


class TestCreateSchedule:
    def test_create_basic(self):
        m = _manager()
        s = m.create_schedule(name="primary", users=["alice", "bob"])
        assert s.name == "primary"
        assert len(s.rotation.users) == 2

    def test_create_with_all_params(self):
        m = _manager()
        s = m.create_schedule(
            name="oncall",
            users=["alice"],
            team="platform",
            timezone="US/Pacific",
            rotation_type=RotationType.DAILY,
            handoff_time_hour=8,
            description="Primary oncall",
            metadata={"source": "api"},
        )
        assert s.team == "platform"
        assert s.rotation.rotation_type == RotationType.DAILY
        assert s.rotation.rotation_interval_hours == 24.0

    def test_create_weekly_default_interval(self):
        m = _manager()
        s = m.create_schedule(name="weekly", users=["alice"])
        assert s.rotation.rotation_interval_hours == 168.0

    def test_create_daily_auto_interval(self):
        m = _manager()
        s = m.create_schedule(name="daily", users=["alice"], rotation_type=RotationType.DAILY)
        assert s.rotation.rotation_interval_hours == 24.0

    def test_create_max_limit(self):
        m = _manager(max_schedules=2)
        m.create_schedule(name="s1", users=["a"])
        m.create_schedule(name="s2", users=["b"])
        with pytest.raises(ValueError, match="Maximum schedules"):
            m.create_schedule(name="s3", users=["c"])

    def test_create_empty_users_error(self):
        m = _manager()
        with pytest.raises(ValueError, match="At least one user"):
            m.create_schedule(name="empty", users=[])


# ---------------------------------------------------------------------------
# Schedule lookup
# ---------------------------------------------------------------------------


class TestScheduleLookup:
    def test_get_schedule_found(self):
        m = _manager()
        s = m.create_schedule(name="primary", users=["alice"])
        assert m.get_schedule(s.id) is not None

    def test_get_schedule_not_found(self):
        m = _manager()
        assert m.get_schedule("nonexistent") is None

    def test_list_schedules_all(self):
        m = _manager()
        m.create_schedule(name="s1", users=["a"])
        m.create_schedule(name="s2", users=["b"])
        assert len(m.list_schedules()) == 2

    def test_list_schedules_by_team(self):
        m = _manager()
        m.create_schedule(name="s1", users=["a"], team="platform")
        m.create_schedule(name="s2", users=["b"], team="infra")
        result = m.list_schedules(team="platform")
        assert len(result) == 1

    def test_list_schedules_by_status(self):
        m = _manager()
        s = m.create_schedule(name="s1", users=["a"])
        s.status = ScheduleStatus.PAUSED
        m.create_schedule(name="s2", users=["b"])
        active = m.list_schedules(status=ScheduleStatus.ACTIVE)
        assert len(active) == 1


# ---------------------------------------------------------------------------
# Current on-call
# ---------------------------------------------------------------------------


class TestCurrentOnCall:
    def test_current_oncall_single_user(self):
        m = _manager()
        s = m.create_schedule(name="primary", users=["alice"])
        assert m.get_current_oncall(s.id) == "alice"

    def test_current_oncall_not_found(self):
        m = _manager()
        assert m.get_current_oncall("nonexistent") is None

    def test_current_oncall_paused(self):
        m = _manager()
        s = m.create_schedule(name="primary", users=["alice"])
        s.status = ScheduleStatus.PAUSED
        assert m.get_current_oncall(s.id) is None

    def test_current_oncall_with_override(self):
        m = _manager()
        s = m.create_schedule(name="primary", users=["alice"])
        now = time.time()
        m.add_override(s.id, user="bob", start_time=now - 100, end_time=now + 3600)
        assert m.get_current_oncall(s.id) == "bob"

    def test_current_oncall_rotation(self):
        m = _manager()
        s = m.create_schedule(name="primary", users=["alice", "bob"], rotation_interval_hours=0.001)
        # With very short interval, rotation should cycle
        result = m.get_current_oncall(s.id)
        assert result in ("alice", "bob")


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------


class TestOverrides:
    def test_add_override_basic(self):
        m = _manager()
        s = m.create_schedule(name="primary", users=["alice"])
        now = time.time()
        o = m.add_override(s.id, user="bob", start_time=now, end_time=now + 3600)
        assert o is not None
        assert o.user == "bob"

    def test_add_override_not_found(self):
        m = _manager()
        now = time.time()
        result = m.add_override(
            "nonexistent",
            user="bob",
            start_time=now,
            end_time=now + 3600,
        )
        assert result is None

    def test_add_override_end_before_start(self):
        m = _manager()
        s = m.create_schedule(name="primary", users=["alice"])
        now = time.time()
        with pytest.raises(ValueError, match="end_time must be after"):
            m.add_override(s.id, user="bob", start_time=now, end_time=now - 100)

    def test_add_override_with_reason(self):
        m = _manager()
        s = m.create_schedule(name="primary", users=["alice"])
        now = time.time()
        o = m.add_override(s.id, user="bob", start_time=now, end_time=now + 3600, reason="vacation")
        assert o.reason == "vacation"


# ---------------------------------------------------------------------------
# Schedule for range
# ---------------------------------------------------------------------------


class TestScheduleForRange:
    def test_schedule_for_range_basic(self):
        m = _manager()
        s = m.create_schedule(name="primary", users=["alice", "bob"])
        now = time.time()
        shifts = m.get_schedule_for_range(s.id, now, now + 604800)
        assert len(shifts) > 0
        assert all(isinstance(sh, OnCallShift) for sh in shifts)

    def test_schedule_for_range_not_found(self):
        m = _manager()
        now = time.time()
        assert m.get_schedule_for_range("nonexistent", now, now + 3600) == []

    def test_schedule_for_range_empty_users(self):
        m = _manager()
        s = m.create_schedule(name="primary", users=["alice"])
        s.rotation.users = []
        now = time.time()
        assert m.get_schedule_for_range(s.id, now, now + 3600) == []


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        m = _manager()
        s = m.get_stats()
        assert s["total_schedules"] == 0
        assert s["total_users"] == 0

    def test_stats_with_data(self):
        m = _manager()
        m.create_schedule(name="s1", users=["alice", "bob"])
        m.create_schedule(name="s2", users=["bob", "carol"])
        s = m.get_stats()
        assert s["total_schedules"] == 2
        assert s["total_users"] == 3  # alice, bob, carol (deduplicated)
        assert s["by_status"]["active"] == 2
