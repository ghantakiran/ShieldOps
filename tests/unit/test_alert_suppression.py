"""Tests for shieldops.observability.alert_suppression – AlertSuppressionEngine."""

from __future__ import annotations

import time

import pytest

from shieldops.observability.alert_suppression import (
    AlertSuppressionEngine,
    MaintenanceWindow,
    SuppressionMatch,
    SuppressionRule,
    SuppressionRuleStatus,
    WindowStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kwargs) -> AlertSuppressionEngine:
    return AlertSuppressionEngine(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_rule_status_values(self):
        assert SuppressionRuleStatus.ACTIVE == "active"
        assert SuppressionRuleStatus.EXPIRED == "expired"
        assert SuppressionRuleStatus.DISABLED == "disabled"

    def test_window_status_values(self):
        assert WindowStatus.SCHEDULED == "scheduled"
        assert WindowStatus.ACTIVE == "active"
        assert WindowStatus.COMPLETED == "completed"
        assert WindowStatus.CANCELLED == "cancelled"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_suppression_rule_defaults(self):
        r = SuppressionRule(name="test")
        assert r.status == SuppressionRuleStatus.ACTIVE
        assert r.id

    def test_maintenance_window_defaults(self):
        now = time.time()
        w = MaintenanceWindow(name="maint", start_time=now, end_time=now + 3600)
        assert w.status == WindowStatus.SCHEDULED

    def test_suppression_match_defaults(self):
        m = SuppressionMatch(suppressed=False)
        assert m.reason == ""
        assert m.rule_id == ""


# ---------------------------------------------------------------------------
# Rule operations
# ---------------------------------------------------------------------------


class TestRuleOperations:
    def test_add_rule_basic(self):
        e = _engine()
        r = e.add_rule(name="silence-cpu", match_pattern="cpu_high.*")
        assert r.name == "silence-cpu"
        assert r.id

    def test_add_rule_with_labels(self):
        e = _engine()
        r = e.add_rule(name="env-filter", match_labels={"env": "staging"})
        assert r.match_labels["env"] == "staging"

    def test_add_rule_max_limit(self):
        e = _engine(max_rules=2)
        e.add_rule(name="r1")
        e.add_rule(name="r2")
        with pytest.raises(ValueError, match="Maximum rules"):
            e.add_rule(name="r3")

    def test_remove_rule_found(self):
        e = _engine()
        r = e.add_rule(name="temp")
        assert e.remove_rule(r.id) is True

    def test_remove_rule_not_found(self):
        e = _engine()
        assert e.remove_rule("nonexistent") is False

    def test_list_rules_all(self):
        e = _engine()
        e.add_rule(name="r1")
        e.add_rule(name="r2")
        assert len(e.list_rules()) == 2

    def test_list_rules_filtered(self):
        e = _engine()
        r = e.add_rule(name="r1")
        r.status = SuppressionRuleStatus.DISABLED
        e.add_rule(name="r2")
        active = e.list_rules(status=SuppressionRuleStatus.ACTIVE)
        assert len(active) == 1


# ---------------------------------------------------------------------------
# Window operations
# ---------------------------------------------------------------------------


class TestWindowOperations:
    def test_schedule_window_basic(self):
        e = _engine()
        now = time.time()
        w = e.schedule_window(name="deploy", start_time=now, end_time=now + 3600)
        assert w.name == "deploy"
        assert w.id

    def test_schedule_window_with_services(self):
        e = _engine()
        now = time.time()
        w = e.schedule_window(
            name="deploy", start_time=now, end_time=now + 3600, services=["api", "web"]
        )
        assert "api" in w.services

    def test_schedule_window_max_duration_exceeded(self):
        e = _engine(max_window_duration_hours=2)
        now = time.time()
        with pytest.raises(ValueError, match="exceeds max"):
            e.schedule_window(name="long", start_time=now, end_time=now + 10 * 3600)

    def test_schedule_window_end_before_start(self):
        e = _engine()
        now = time.time()
        with pytest.raises(ValueError, match="end_time must be after"):
            e.schedule_window(name="bad", start_time=now, end_time=now - 100)

    def test_cancel_window_found(self):
        e = _engine()
        now = time.time()
        w = e.schedule_window(name="temp", start_time=now, end_time=now + 3600)
        result = e.cancel_window(w.id)
        assert result is not None
        assert result.status == WindowStatus.CANCELLED

    def test_cancel_window_not_found(self):
        e = _engine()
        assert e.cancel_window("nonexistent") is None

    def test_get_active_windows(self):
        e = _engine()
        now = time.time()
        e.schedule_window(name="active", start_time=now - 100, end_time=now + 3600)
        e.schedule_window(name="future", start_time=now + 7200, end_time=now + 10800)
        active = e.get_active_windows()
        assert len(active) == 1
        assert active[0].name == "active"

    def test_get_active_windows_marks_completed(self):
        e = _engine()
        now = time.time()
        e.schedule_window(name="past", start_time=now - 7200, end_time=now - 3600)
        active = e.get_active_windows()
        assert len(active) == 0


# ---------------------------------------------------------------------------
# Suppression checks
# ---------------------------------------------------------------------------


class TestShouldSuppress:
    def test_no_suppression(self):
        e = _engine()
        result = e.should_suppress(alert_name="cpu_high")
        assert result.suppressed is False

    def test_suppress_by_label_match(self):
        e = _engine()
        e.add_rule(name="staging", match_labels={"env": "staging"})
        result = e.should_suppress(labels={"env": "staging"})
        assert result.suppressed is True
        assert "staging" in result.reason

    def test_suppress_by_pattern_match(self):
        e = _engine()
        e.add_rule(name="cpu-pattern", match_pattern="cpu_high.*")
        result = e.should_suppress(alert_name="cpu_high_warning")
        assert result.suppressed is True

    def test_no_suppress_label_mismatch(self):
        e = _engine()
        e.add_rule(name="staging", match_labels={"env": "staging"})
        result = e.should_suppress(labels={"env": "production"})
        assert result.suppressed is False

    def test_suppress_by_maintenance_window_service(self):
        e = _engine()
        now = time.time()
        e.schedule_window(
            name="deploy", start_time=now - 100, end_time=now + 3600, services=["api"]
        )
        result = e.should_suppress(service="api")
        assert result.suppressed is True
        assert result.window_id

    def test_no_suppress_wrong_service(self):
        e = _engine()
        now = time.time()
        e.schedule_window(
            name="deploy", start_time=now - 100, end_time=now + 3600, services=["api"]
        )
        result = e.should_suppress(service="web")
        assert result.suppressed is False

    def test_suppress_by_global_window(self):
        e = _engine()
        now = time.time()
        e.schedule_window(name="global", start_time=now - 100, end_time=now + 3600)
        result = e.should_suppress(alert_name="anything")
        assert result.suppressed is True

    def test_suppress_by_window_labels(self):
        e = _engine()
        now = time.time()
        e.schedule_window(
            name="labeled",
            start_time=now - 100,
            end_time=now + 3600,
            suppress_labels={"team": "platform"},
        )
        result = e.should_suppress(labels={"team": "platform"})
        assert result.suppressed is True

    def test_expired_rule_not_suppressed(self):
        e = _engine()
        e.add_rule(name="expired", match_pattern=".*", expires_at=time.time() - 100)
        result = e.should_suppress(alert_name="test")
        assert result.suppressed is False

    def test_cancelled_window_not_suppressed(self):
        e = _engine()
        now = time.time()
        w = e.schedule_window(name="cancelled", start_time=now - 100, end_time=now + 3600)
        e.cancel_window(w.id)
        result = e.should_suppress(alert_name="test")
        assert result.suppressed is False

    def test_disabled_rule_not_suppressed(self):
        e = _engine()
        r = e.add_rule(name="disabled", match_pattern=".*")
        r.status = SuppressionRuleStatus.DISABLED
        result = e.should_suppress(alert_name="test")
        assert result.suppressed is False


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        e = _engine()
        s = e.get_stats()
        assert s["total_rules"] == 0
        assert s["active_rules"] == 0
        assert s["total_windows"] == 0

    def test_stats_with_data(self):
        e = _engine()
        now = time.time()
        e.add_rule(name="r1")
        e.schedule_window(name="w1", start_time=now - 100, end_time=now + 3600)
        s = e.get_stats()
        assert s["total_rules"] == 1
        assert s["active_rules"] == 1
        assert s["total_windows"] == 1
        assert s["active_windows"] == 1

    def test_stats_inactive_window(self):
        e = _engine()
        now = time.time()
        e.schedule_window(name="future", start_time=now + 7200, end_time=now + 10800)
        s = e.get_stats()
        assert s["active_windows"] == 0
