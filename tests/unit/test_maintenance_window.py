"""Tests for shieldops.scheduler.maintenance_window — MaintenanceWindowManager."""

from __future__ import annotations

import time

import pytest

from shieldops.scheduler.maintenance_window import (
    MaintenanceWindow,
    MaintenanceWindowManager,
    WindowConflict,
    WindowStatus,
    WindowType,
)


def _manager(**kw) -> MaintenanceWindowManager:
    return MaintenanceWindowManager(**kw)


def _now() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # WindowStatus (5 values)

    def test_status_scheduled(self):
        assert WindowStatus.SCHEDULED == "scheduled"

    def test_status_active(self):
        assert WindowStatus.ACTIVE == "active"

    def test_status_completed(self):
        assert WindowStatus.COMPLETED == "completed"

    def test_status_cancelled(self):
        assert WindowStatus.CANCELLED == "cancelled"

    def test_status_extended(self):
        assert WindowStatus.EXTENDED == "extended"

    # WindowType (3 values)

    def test_type_planned(self):
        assert WindowType.PLANNED == "planned"

    def test_type_emergency(self):
        assert WindowType.EMERGENCY == "emergency"

    def test_type_recurring(self):
        assert WindowType.RECURRING == "recurring"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_maintenance_window_defaults(self):
        t = _now()
        w = MaintenanceWindow(title="DB upgrade", start_time=t, end_time=t + 3600)
        assert w.id
        assert w.services == []
        assert w.window_type == WindowType.PLANNED
        assert w.status == WindowStatus.SCHEDULED
        assert w.owner == ""
        assert w.description == ""
        assert w.notifications_sent == []
        assert w.metadata == {}
        assert w.created_at > 0

    def test_window_conflict_defaults(self):
        t = _now()
        c = WindowConflict(
            window_a_id="a",
            window_b_id="b",
            overlap_start=t,
            overlap_end=t + 1800,
        )
        assert c.id
        assert c.overlapping_services == []
        assert c.detected_at > 0


# ---------------------------------------------------------------------------
# create_window
# ---------------------------------------------------------------------------


class TestCreateWindow:
    def test_basic(self):
        m = _manager()
        t = _now()
        w = m.create_window(
            title="Deploy v2",
            services=["api", "web"],
            start_time=t,
            end_time=t + 3600,
        )
        assert w.title == "Deploy v2"
        assert w.services == ["api", "web"]
        assert w.status == WindowStatus.SCHEDULED

    def test_all_fields(self):
        m = _manager()
        t = _now()
        w = m.create_window(
            title="Emergency patch",
            services=["db"],
            start_time=t,
            end_time=t + 7200,
            window_type=WindowType.EMERGENCY,
            owner="oncall-team",
            description="Critical security patch",
        )
        assert w.window_type == WindowType.EMERGENCY
        assert w.owner == "oncall-team"
        assert w.description == "Critical security patch"

    def test_max_limit(self):
        m = _manager(max_windows=2)
        t = _now()
        m.create_window(title="w1", services=[], start_time=t, end_time=t + 3600)
        m.create_window(title="w2", services=[], start_time=t, end_time=t + 3600)
        with pytest.raises(ValueError, match="Maximum windows"):
            m.create_window(title="w3", services=[], start_time=t, end_time=t + 3600)

    def test_duration_exceeds_max(self):
        m = _manager(max_duration_hours=1)
        t = _now()
        with pytest.raises(ValueError, match="exceeds"):
            m.create_window(
                title="long",
                services=[],
                start_time=t,
                end_time=t + 7200,  # 2 hours > 1 hour max
            )


# ---------------------------------------------------------------------------
# activate_window
# ---------------------------------------------------------------------------


class TestActivateWindow:
    def test_basic(self):
        m = _manager()
        t = _now()
        w = m.create_window(title="w", services=[], start_time=t, end_time=t + 3600)
        result = m.activate_window(w.id)
        assert result is not None
        assert result.status == WindowStatus.ACTIVE

    def test_not_found(self):
        m = _manager()
        assert m.activate_window("nonexistent") is None

    def test_already_completed_can_still_activate(self):
        m = _manager()
        t = _now()
        w = m.create_window(title="w", services=[], start_time=t, end_time=t + 3600)
        m.complete_window(w.id)
        result = m.activate_window(w.id)
        assert result is not None
        assert result.status == WindowStatus.ACTIVE


# ---------------------------------------------------------------------------
# complete_window
# ---------------------------------------------------------------------------


class TestCompleteWindow:
    def test_basic(self):
        m = _manager()
        t = _now()
        w = m.create_window(title="w", services=[], start_time=t, end_time=t + 3600)
        result = m.complete_window(w.id)
        assert result is not None
        assert result.status == WindowStatus.COMPLETED

    def test_not_found(self):
        m = _manager()
        assert m.complete_window("nonexistent") is None


# ---------------------------------------------------------------------------
# cancel_window
# ---------------------------------------------------------------------------


class TestCancelWindow:
    def test_basic(self):
        m = _manager()
        t = _now()
        w = m.create_window(title="w", services=[], start_time=t, end_time=t + 3600)
        result = m.cancel_window(w.id)
        assert result is not None
        assert result.status == WindowStatus.CANCELLED

    def test_not_found(self):
        m = _manager()
        assert m.cancel_window("nonexistent") is None


# ---------------------------------------------------------------------------
# extend_window
# ---------------------------------------------------------------------------


class TestExtendWindow:
    def test_basic(self):
        m = _manager()
        t = _now()
        w = m.create_window(title="w", services=[], start_time=t, end_time=t + 3600)
        result = m.extend_window(w.id, t + 7200)
        assert result is not None
        assert result.end_time == t + 7200
        assert result.status == WindowStatus.EXTENDED

    def test_exceeds_max(self):
        m = _manager(max_duration_hours=2)
        t = _now()
        w = m.create_window(title="w", services=[], start_time=t, end_time=t + 3600)
        with pytest.raises(ValueError, match="exceeds"):
            m.extend_window(w.id, t + 3600 * 10)  # 10 hours > 2 hours max

    def test_not_found(self):
        m = _manager()
        assert m.extend_window("nonexistent", _now() + 9999) is None


# ---------------------------------------------------------------------------
# check_conflicts
# ---------------------------------------------------------------------------


class TestCheckConflicts:
    def test_no_conflicts(self):
        m = _manager()
        t = _now()
        m.create_window(
            title="w1",
            services=["api"],
            start_time=t,
            end_time=t + 3600,
        )
        m.create_window(
            title="w2",
            services=["api"],
            start_time=t + 7200,
            end_time=t + 10800,
        )
        conflicts = m.check_conflicts()
        assert conflicts == []

    def test_overlapping_window(self):
        m = _manager()
        t = _now()
        m.create_window(
            title="w1",
            services=["api"],
            start_time=t,
            end_time=t + 3600,
        )
        m.create_window(
            title="w2",
            services=["api"],
            start_time=t + 1800,
            end_time=t + 5400,
        )
        conflicts = m.check_conflicts()
        assert len(conflicts) == 1
        assert "api" in conflicts[0].overlapping_services


# ---------------------------------------------------------------------------
# get_window
# ---------------------------------------------------------------------------


class TestGetWindow:
    def test_found(self):
        m = _manager()
        t = _now()
        w = m.create_window(title="w", services=[], start_time=t, end_time=t + 3600)
        assert m.get_window(w.id) is not None

    def test_not_found(self):
        m = _manager()
        assert m.get_window("nonexistent") is None


# ---------------------------------------------------------------------------
# list_windows
# ---------------------------------------------------------------------------


class TestListWindows:
    def test_all(self):
        m = _manager()
        t = _now()
        m.create_window(title="w1", services=[], start_time=t, end_time=t + 3600)
        m.create_window(title="w2", services=[], start_time=t, end_time=t + 3600)
        assert len(m.list_windows()) == 2

    def test_by_status(self):
        m = _manager()
        t = _now()
        w = m.create_window(title="w1", services=[], start_time=t, end_time=t + 3600)
        m.create_window(title="w2", services=[], start_time=t, end_time=t + 3600)
        m.activate_window(w.id)
        active = m.list_windows(status=WindowStatus.ACTIVE)
        scheduled = m.list_windows(status=WindowStatus.SCHEDULED)
        assert len(active) == 1
        assert len(scheduled) == 1

    def test_by_type_in_full_list(self):
        m = _manager()
        t = _now()
        m.create_window(
            title="planned",
            services=[],
            start_time=t,
            end_time=t + 3600,
            window_type=WindowType.PLANNED,
        )
        m.create_window(
            title="emergency",
            services=[],
            start_time=t,
            end_time=t + 3600,
            window_type=WindowType.EMERGENCY,
        )
        assert len(m.list_windows()) == 2

    def test_by_service(self):
        m = _manager()
        t = _now()
        m.create_window(title="w1", services=["api"], start_time=t, end_time=t + 3600)
        m.create_window(title="w2", services=["db"], start_time=t, end_time=t + 3600)
        result = m.list_windows(service="api")
        assert len(result) == 1
        assert "api" in result[0].services

    def test_empty(self):
        m = _manager()
        assert m.list_windows() == []


# ---------------------------------------------------------------------------
# get_active_windows
# ---------------------------------------------------------------------------


class TestGetActiveWindows:
    def test_returns_only_active(self):
        m = _manager()
        t = _now()
        w1 = m.create_window(title="w1", services=[], start_time=t, end_time=t + 3600)
        m.create_window(title="w2", services=[], start_time=t, end_time=t + 3600)
        m.activate_window(w1.id)
        active = m.get_active_windows()
        assert len(active) == 1
        assert active[0].id == w1.id


# ---------------------------------------------------------------------------
# notify_window
# ---------------------------------------------------------------------------


class TestNotifyWindow:
    def test_basic(self):
        m = _manager()
        t = _now()
        w = m.create_window(title="w", services=[], start_time=t, end_time=t + 3600)
        result = m.notify_window(w.id, "slack")
        assert result is not None
        assert "slack" in result.notifications_sent

    def test_not_found(self):
        m = _manager()
        assert m.notify_window("nonexistent", "slack") is None


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        m = _manager()
        stats = m.get_stats()
        assert stats["total_windows"] == 0
        assert stats["by_status"] == {}
        assert stats["by_type"] == {}
        assert stats["active_count"] == 0
        assert stats["total_conflicts"] == 0
        assert stats["avg_duration_hours"] == 0.0

    def test_populated(self):
        m = _manager()
        t = _now()
        w1 = m.create_window(
            title="w1",
            services=["api"],
            start_time=t,
            end_time=t + 3600,
        )
        m.create_window(
            title="w2",
            services=["db"],
            start_time=t,
            end_time=t + 7200,
        )
        m.activate_window(w1.id)
        stats = m.get_stats()
        assert stats["total_windows"] == 2
        assert stats["active_count"] == 1
        assert WindowStatus.ACTIVE in stats["by_status"]
        assert WindowStatus.SCHEDULED in stats["by_status"]
        assert stats["avg_duration_hours"] > 0
