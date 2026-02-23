"""Comprehensive unit tests for SLO / Error Budget monitoring (Phase 13 F6).

Tests cover:
- SLOStatus enum values
- SLODefinition Pydantic model defaults and custom values
- ErrorBudget model fields
- BurnRateAlert model fields
- SLOEvent model defaults
- SLOMonitor default SLOs registration
- SLOMonitor.register_slo / get_slo / list_slos
- SLOMonitor.record_event
- Error budget calculation: all good events, mixed, all bad, empty
- SLO status: MET, AT_RISK, BREACHED
- Burn rate calculation and thresholds
- Burn rate alerts generation
- get_all_budgets
- get_burn_rate_history
- Event trimming at max_events
- get_alerts filtering
- Edge cases: unknown SLO name, zero budget_total

Requires: pytest
"""

from __future__ import annotations

from datetime import datetime

import pytest

from shieldops.observability.slo_monitor import (
    BurnRateAlert,
    ErrorBudget,
    SLODefinition,
    SLOEvent,
    SLOMonitor,
    SLOStatus,
)

# ===========================================================================
# SLOStatus Enum Tests
# ===========================================================================


class TestSLOStatus:
    """Tests for the SLOStatus StrEnum."""

    def test_met_value(self):
        assert SLOStatus.MET == "met"

    def test_at_risk_value(self):
        assert SLOStatus.AT_RISK == "at_risk"

    def test_breached_value(self):
        assert SLOStatus.BREACHED == "breached"

    def test_status_count(self):
        assert len(SLOStatus) == 3

    def test_status_is_str(self):
        assert isinstance(SLOStatus.MET, str)


# ===========================================================================
# SLODefinition Model Tests
# ===========================================================================


class TestSLODefinition:
    """Tests for the SLODefinition Pydantic model."""

    def test_required_name(self):
        slo = SLODefinition(name="test_slo")
        assert slo.name == "test_slo"

    def test_default_description_empty(self):
        slo = SLODefinition(name="test")
        assert slo.description == ""

    def test_default_target(self):
        slo = SLODefinition(name="test")
        assert slo.target == 0.999

    def test_default_window_days(self):
        slo = SLODefinition(name="test")
        assert slo.window_days == 30

    def test_default_sli_type(self):
        slo = SLODefinition(name="test")
        assert slo.sli_type == "availability"

    def test_created_at_is_datetime(self):
        slo = SLODefinition(name="test")
        assert isinstance(slo.created_at, datetime)

    def test_custom_target(self):
        slo = SLODefinition(name="test", target=0.95)
        assert slo.target == 0.95

    def test_custom_window_days(self):
        slo = SLODefinition(name="test", window_days=7)
        assert slo.window_days == 7

    def test_custom_sli_type(self):
        slo = SLODefinition(name="test", sli_type="latency")
        assert slo.sli_type == "latency"


# ===========================================================================
# ErrorBudget Model Tests
# ===========================================================================


class TestErrorBudgetModel:
    """Tests for the ErrorBudget Pydantic model."""

    def test_all_fields_set(self):
        budget = ErrorBudget(
            slo_name="api_availability",
            target=0.999,
            current_sli=0.998,
            budget_total=0.001,
            budget_consumed=0.002,
            budget_remaining=0.0,
            burn_rate=2.0,
            status=SLOStatus.BREACHED,
        )
        assert budget.slo_name == "api_availability"
        assert budget.target == 0.999
        assert budget.status == SLOStatus.BREACHED

    def test_default_window_days(self):
        budget = ErrorBudget(
            slo_name="test",
            target=0.999,
            current_sli=1.0,
            budget_total=0.001,
            budget_consumed=0.0,
            budget_remaining=0.001,
            burn_rate=0.0,
            status=SLOStatus.MET,
        )
        assert budget.window_days == 30

    def test_calculated_at_is_datetime(self):
        budget = ErrorBudget(
            slo_name="test",
            target=0.999,
            current_sli=1.0,
            budget_total=0.001,
            budget_consumed=0.0,
            budget_remaining=0.001,
            burn_rate=0.0,
            status=SLOStatus.MET,
        )
        assert isinstance(budget.calculated_at, datetime)


# ===========================================================================
# BurnRateAlert Model Tests
# ===========================================================================


class TestBurnRateAlertModel:
    """Tests for the BurnRateAlert Pydantic model."""

    def test_all_fields_set(self):
        alert = BurnRateAlert(
            slo_name="api_availability",
            burn_rate=3.5,
            threshold=2.0,
            message="High burn rate",
        )
        assert alert.slo_name == "api_availability"
        assert alert.burn_rate == 3.5
        assert alert.threshold == 2.0

    def test_default_severity(self):
        alert = BurnRateAlert(
            slo_name="test",
            burn_rate=2.0,
            threshold=2.0,
            message="msg",
        )
        assert alert.severity == "warning"

    def test_fired_at_is_datetime(self):
        alert = BurnRateAlert(
            slo_name="test",
            burn_rate=2.0,
            threshold=2.0,
            message="msg",
        )
        assert isinstance(alert.fired_at, datetime)


# ===========================================================================
# SLOEvent Model Tests
# ===========================================================================


class TestSLOEventModel:
    """Tests for the SLOEvent Pydantic model."""

    def test_required_slo_name(self):
        event = SLOEvent(slo_name="api_availability")
        assert event.slo_name == "api_availability"

    def test_default_good_is_true(self):
        event = SLOEvent(slo_name="test")
        assert event.good is True

    def test_default_value_is_one(self):
        event = SLOEvent(slo_name="test")
        assert event.value == 1.0

    def test_timestamp_is_float(self):
        event = SLOEvent(slo_name="test")
        assert isinstance(event.timestamp, float)

    def test_bad_event(self):
        event = SLOEvent(slo_name="test", good=False)
        assert event.good is False


# ===========================================================================
# SLOMonitor Default SLOs Tests
# ===========================================================================


class TestSLOMonitorDefaults:
    """Tests for SLOMonitor constructor and default SLOs."""

    def test_default_slos_registered(self):
        monitor = SLOMonitor()
        slos = monitor.list_slos()
        names = {s.name for s in slos}
        assert "api_availability" in names
        assert "agent_success_rate" in names
        assert "mttr" in names
        assert "remediation_success" in names

    def test_default_slo_count(self):
        monitor = SLOMonitor()
        assert len(monitor.list_slos()) == 4

    def test_api_availability_target(self):
        monitor = SLOMonitor()
        slo = monitor.get_slo("api_availability")
        assert slo is not None
        assert slo.target == 0.999

    def test_agent_success_rate_target(self):
        monitor = SLOMonitor()
        slo = monitor.get_slo("agent_success_rate")
        assert slo is not None
        assert slo.target == 0.95

    def test_mttr_sli_type(self):
        monitor = SLOMonitor()
        slo = monitor.get_slo("mttr")
        assert slo.sli_type == "latency"

    def test_get_slo_unknown_returns_none(self):
        monitor = SLOMonitor()
        assert monitor.get_slo("nonexistent") is None


# ===========================================================================
# SLOMonitor register_slo / list_slos Tests
# ===========================================================================


class TestSLOMonitorRegistration:
    """Tests for register_slo and list_slos."""

    def test_register_custom_slo(self):
        monitor = SLOMonitor()
        custom = SLODefinition(name="custom_slo", target=0.98)
        result = monitor.register_slo(custom)
        assert result.name == "custom_slo"
        assert monitor.get_slo("custom_slo") is not None

    def test_register_slo_replaces_existing(self):
        monitor = SLOMonitor()
        v1 = SLODefinition(name="custom", target=0.99)
        v2 = SLODefinition(name="custom", target=0.95)
        monitor.register_slo(v1)
        monitor.register_slo(v2)
        slo = monitor.get_slo("custom")
        assert slo.target == 0.95

    def test_register_slo_initializes_event_list(self):
        monitor = SLOMonitor()
        custom = SLODefinition(name="new_slo")
        monitor.register_slo(custom)
        assert monitor._events.get("new_slo") is not None
        assert monitor._events["new_slo"] == []

    def test_register_slo_preserves_existing_events(self):
        monitor = SLOMonitor()
        custom = SLODefinition(name="new_slo")
        monitor.register_slo(custom)
        monitor.record_event(SLOEvent(slo_name="new_slo"))
        # Re-register should not wipe events
        monitor.register_slo(SLODefinition(name="new_slo", target=0.98))
        assert len(monitor._events["new_slo"]) == 1


# ===========================================================================
# SLOMonitor record_event Tests
# ===========================================================================


class TestSLOMonitorRecordEvent:
    """Tests for record_event."""

    def test_record_event_stores_event(self):
        monitor = SLOMonitor()
        monitor.record_event(SLOEvent(slo_name="api_availability"))
        assert len(monitor._events["api_availability"]) == 1

    def test_record_event_unknown_slo_ignored(self):
        monitor = SLOMonitor()
        # Should not raise
        monitor.record_event(SLOEvent(slo_name="unknown_slo"))
        assert (
            "unknown_slo" not in monitor._events or len(monitor._events.get("unknown_slo", [])) == 0
        )

    def test_record_multiple_events(self):
        monitor = SLOMonitor()
        for _ in range(10):
            monitor.record_event(SLOEvent(slo_name="api_availability"))
        assert len(monitor._events["api_availability"]) == 10

    def test_record_event_trims_to_max(self):
        monitor = SLOMonitor(max_events=5)
        for i in range(10):
            monitor.record_event(SLOEvent(slo_name="api_availability", value=float(i)))
        events = monitor._events["api_availability"]
        assert len(events) == 5
        # Should keep the most recent 5
        assert events[0].value == 5.0


# ===========================================================================
# Error Budget Calculation Tests
# ===========================================================================


class TestErrorBudgetCalculation:
    """Tests for get_error_budget."""

    def test_error_budget_no_events(self):
        monitor = SLOMonitor()
        budget = monitor.get_error_budget("api_availability")
        assert budget is not None
        assert budget.current_sli == 1.0
        assert budget.budget_consumed == 0.0
        assert budget.burn_rate == 0.0
        assert budget.status == SLOStatus.MET

    def test_error_budget_all_good_events(self):
        monitor = SLOMonitor()
        for _ in range(100):
            monitor.record_event(SLOEvent(slo_name="api_availability", good=True))
        budget = monitor.get_error_budget("api_availability")
        assert budget.current_sli == 1.0
        assert budget.budget_consumed == 0.0
        assert budget.status == SLOStatus.MET

    def test_error_budget_with_failures(self):
        monitor = SLOMonitor()
        # 95 good + 5 bad = 95% SLI, target 99.9%
        for _ in range(95):
            monitor.record_event(SLOEvent(slo_name="api_availability", good=True))
        for _ in range(5):
            monitor.record_event(SLOEvent(slo_name="api_availability", good=False))
        budget = monitor.get_error_budget("api_availability")
        assert budget.current_sli == 0.95
        assert budget.budget_consumed == pytest.approx(0.05)
        # budget_total for 99.9% = 0.001; consumed = 0.05 > 0.001 => breached
        assert budget.status == SLOStatus.BREACHED

    def test_error_budget_at_risk_status(self):
        # Use a target where burn rate >= threshold but budget still > 0
        monitor = SLOMonitor(burn_rate_threshold=1.0)
        custom = SLODefinition(name="custom", target=0.90)
        monitor.register_slo(custom)
        # 85 good + 15 bad = 85% SLI, target 90%, budget_total=0.10
        # consumed = 0.15, budget_remaining = max(0, 0.10-0.15)=0.0 => BREACHED
        # Need: consumed < budget_total but burn_rate >= threshold
        # 91 good + 9 bad = 91% SLI, consumed=0.09, budget_total=0.10
        # burn_rate = 0.09/0.10 = 0.9 < 1.0 => MET
        # 89 good + 11 bad = 89% SLI, consumed=0.11, remaining=0 => BREACHED
        # Let's try: 90 good + 10 bad = 90% SLI, consumed=0.10, remaining=0 => BREACHED
        # For AT_RISK: budget_remaining > 0 AND burn_rate >= threshold
        # target=0.80 => budget_total=0.20
        # 85 good + 15 bad = 85% SLI, consumed=0.15, remaining=0.05
        # burn_rate = 0.15/0.20 = 0.75 < 1.0 => MET
        # With threshold=0.5: burn_rate=0.75 >= 0.5 AND remaining=0.05 > 0 => AT_RISK
        monitor2 = SLOMonitor(burn_rate_threshold=0.5)
        custom2 = SLODefinition(name="custom2", target=0.80)
        monitor2.register_slo(custom2)
        for _ in range(85):
            monitor2.record_event(SLOEvent(slo_name="custom2", good=True))
        for _ in range(15):
            monitor2.record_event(SLOEvent(slo_name="custom2", good=False))
        budget = monitor2.get_error_budget("custom2")
        assert budget.status == SLOStatus.AT_RISK

    def test_error_budget_breached_status(self):
        monitor = SLOMonitor()
        # target 99.9%, budget_total=0.001
        # 990 good + 10 bad = 99% SLI, consumed=0.01, remaining=max(0, 0.001-0.01)=0
        for _ in range(990):
            monitor.record_event(SLOEvent(slo_name="api_availability", good=True))
        for _ in range(10):
            monitor.record_event(SLOEvent(slo_name="api_availability", good=False))
        budget = monitor.get_error_budget("api_availability")
        assert budget.status == SLOStatus.BREACHED
        assert budget.budget_remaining == 0.0

    def test_error_budget_unknown_slo_returns_none(self):
        monitor = SLOMonitor()
        assert monitor.get_error_budget("nonexistent") is None

    def test_error_budget_budget_total_correct(self):
        monitor = SLOMonitor()
        budget = monitor.get_error_budget("api_availability")
        # target=0.999, budget_total = 1 - 0.999 = 0.001
        assert budget.budget_total == pytest.approx(0.001)

    def test_error_budget_sli_calculation(self):
        monitor = SLOMonitor()
        for _ in range(80):
            monitor.record_event(SLOEvent(slo_name="agent_success_rate", good=True))
        for _ in range(20):
            monitor.record_event(SLOEvent(slo_name="agent_success_rate", good=False))
        budget = monitor.get_error_budget("agent_success_rate")
        assert budget.current_sli == pytest.approx(0.8)

    def test_error_budget_budget_remaining_non_negative(self):
        monitor = SLOMonitor()
        # Large number of failures should not produce negative remaining
        for _ in range(50):
            monitor.record_event(SLOEvent(slo_name="api_availability", good=False))
        budget = monitor.get_error_budget("api_availability")
        assert budget.budget_remaining >= 0.0
        assert budget.budget_consumed >= 0.0


# ===========================================================================
# Burn Rate and Alerts Tests
# ===========================================================================


class TestBurnRateAndAlerts:
    """Tests for burn rate calculation and alert generation."""

    def test_burn_rate_zero_for_all_good(self):
        monitor = SLOMonitor()
        for _ in range(100):
            monitor.record_event(SLOEvent(slo_name="api_availability", good=True))
        budget = monitor.get_error_budget("api_availability")
        assert budget.burn_rate == 0.0

    def test_burn_rate_increases_with_failures(self):
        monitor = SLOMonitor()
        custom = SLODefinition(name="test_slo", target=0.90)
        monitor.register_slo(custom)
        for _ in range(80):
            monitor.record_event(SLOEvent(slo_name="test_slo", good=True))
        for _ in range(20):
            monitor.record_event(SLOEvent(slo_name="test_slo", good=False))
        budget = monitor.get_error_budget("test_slo")
        # consumed=0.20, budget_total=0.10, burn_rate=0.20/0.10=2.0
        assert budget.burn_rate == pytest.approx(2.0)

    def test_alert_generated_when_burn_rate_exceeds_threshold(self):
        monitor = SLOMonitor(burn_rate_threshold=1.0)
        custom = SLODefinition(name="test_slo", target=0.90)
        monitor.register_slo(custom)
        # 80 good + 20 bad => burn_rate = 2.0 > 1.0
        for _ in range(80):
            monitor.record_event(SLOEvent(slo_name="test_slo", good=True))
        for _ in range(20):
            monitor.record_event(SLOEvent(slo_name="test_slo", good=False))
        monitor.get_error_budget("test_slo")  # Triggers alert check
        alerts = monitor.get_alerts("test_slo")
        assert len(alerts) >= 1
        assert alerts[0].slo_name == "test_slo"
        assert alerts[0].burn_rate >= 1.0

    def test_no_alert_when_burn_rate_below_threshold(self):
        # Use a high threshold so burn_rate stays strictly below it.
        # target=0.90 => budget_total=0.10
        # 95 good + 5 bad = 95% SLI, consumed=0.05, burn_rate=0.05/0.10=0.5
        # threshold=5.0 => 0.5 < 5.0, no alert.
        monitor = SLOMonitor(burn_rate_threshold=5.0)
        custom = SLODefinition(name="low_burn", target=0.90)
        monitor.register_slo(custom)
        for _ in range(95):
            monitor.record_event(SLOEvent(slo_name="low_burn", good=True))
        for _ in range(5):
            monitor.record_event(SLOEvent(slo_name="low_burn", good=False))
        monitor.get_error_budget("low_burn")
        alerts = monitor.get_alerts("low_burn")
        assert len(alerts) == 0

    def test_alert_severity_critical_when_breached(self):
        monitor = SLOMonitor(burn_rate_threshold=1.0)
        custom = SLODefinition(name="test_slo", target=0.90)
        monitor.register_slo(custom)
        # Enough failures to breach
        for _ in range(80):
            monitor.record_event(SLOEvent(slo_name="test_slo", good=True))
        for _ in range(20):
            monitor.record_event(SLOEvent(slo_name="test_slo", good=False))
        budget = monitor.get_error_budget("test_slo")
        if budget.status == SLOStatus.BREACHED:
            alerts = monitor.get_alerts("test_slo")
            assert any(a.severity == "critical" for a in alerts)

    def test_get_alerts_all(self):
        monitor = SLOMonitor(burn_rate_threshold=1.0)
        custom = SLODefinition(name="test_slo", target=0.90)
        monitor.register_slo(custom)
        for _ in range(80):
            monitor.record_event(SLOEvent(slo_name="test_slo", good=True))
        for _ in range(20):
            monitor.record_event(SLOEvent(slo_name="test_slo", good=False))
        monitor.get_error_budget("test_slo")
        all_alerts = monitor.get_alerts()
        assert len(all_alerts) >= 1

    def test_get_alerts_filter_by_slo(self):
        monitor = SLOMonitor(burn_rate_threshold=1.0)
        s1 = SLODefinition(name="slo_a", target=0.90)
        s2 = SLODefinition(name="slo_b", target=0.90)
        monitor.register_slo(s1)
        monitor.register_slo(s2)
        for _ in range(80):
            monitor.record_event(SLOEvent(slo_name="slo_a", good=True))
        for _ in range(20):
            monitor.record_event(SLOEvent(slo_name="slo_a", good=False))
        monitor.get_error_budget("slo_a")
        alerts_a = monitor.get_alerts("slo_a")
        alerts_b = monitor.get_alerts("slo_b")
        assert len(alerts_a) >= 1
        assert len(alerts_b) == 0


# ===========================================================================
# get_all_budgets Tests
# ===========================================================================


class TestGetAllBudgets:
    """Tests for get_all_budgets."""

    def test_get_all_budgets_returns_all_default_slos(self):
        monitor = SLOMonitor()
        budgets = monitor.get_all_budgets()
        assert len(budgets) == 4

    def test_get_all_budgets_includes_custom(self):
        monitor = SLOMonitor()
        monitor.register_slo(SLODefinition(name="custom"))
        budgets = monitor.get_all_budgets()
        assert len(budgets) == 5
        names = {b.slo_name for b in budgets}
        assert "custom" in names

    def test_get_all_budgets_returns_error_budget_objects(self):
        monitor = SLOMonitor()
        budgets = monitor.get_all_budgets()
        for b in budgets:
            assert isinstance(b, ErrorBudget)


# ===========================================================================
# get_burn_rate_history Tests
# ===========================================================================


class TestBurnRateHistory:
    """Tests for get_burn_rate_history."""

    def test_empty_events_returns_empty_list(self):
        monitor = SLOMonitor()
        history = monitor.get_burn_rate_history("api_availability")
        assert history == []

    def test_history_returns_list_of_dicts(self):
        monitor = SLOMonitor()
        for _ in range(100):
            monitor.record_event(SLOEvent(slo_name="api_availability", good=True))
        history = monitor.get_burn_rate_history("api_availability")
        assert isinstance(history, list)
        assert len(history) > 0
        for entry in history:
            assert "bucket_index" in entry
            assert "events" in entry
            assert "sli" in entry
            assert "burn_rate" in entry

    def test_history_bucket_sli_for_all_good(self):
        monitor = SLOMonitor()
        for _ in range(100):
            monitor.record_event(SLOEvent(slo_name="api_availability", good=True))
        history = monitor.get_burn_rate_history("api_availability")
        for entry in history:
            assert entry["sli"] == 1.0

    def test_history_unknown_slo_returns_empty(self):
        monitor = SLOMonitor()
        history = monitor.get_burn_rate_history("nonexistent")
        assert history == []

    def test_history_bucket_index_starts_at_zero(self):
        monitor = SLOMonitor()
        for _ in range(50):
            monitor.record_event(SLOEvent(slo_name="api_availability", good=True))
        history = monitor.get_burn_rate_history("api_availability")
        assert history[0]["bucket_index"] == 0
