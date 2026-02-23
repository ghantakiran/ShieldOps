"""Tests for shieldops.sla.error_budget -- ErrorBudgetTracker."""

from __future__ import annotations

import pytest

from shieldops.sla.error_budget import (
    BudgetAlert,
    BudgetConsumption,
    BudgetPeriod,
    BudgetStatus,
    ErrorBudgetPolicy,
    ErrorBudgetTracker,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tracker(**kwargs) -> ErrorBudgetTracker:
    return ErrorBudgetTracker(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_budget_status_healthy(self):
        assert BudgetStatus.HEALTHY == "healthy"

    def test_budget_status_warning(self):
        assert BudgetStatus.WARNING == "warning"

    def test_budget_status_critical(self):
        assert BudgetStatus.CRITICAL == "critical"

    def test_budget_status_exhausted(self):
        assert BudgetStatus.EXHAUSTED == "exhausted"

    def test_budget_period_daily(self):
        assert BudgetPeriod.DAILY == "daily"

    def test_budget_period_weekly(self):
        assert BudgetPeriod.WEEKLY == "weekly"

    def test_budget_period_monthly(self):
        assert BudgetPeriod.MONTHLY == "monthly"

    def test_budget_period_quarterly(self):
        assert BudgetPeriod.QUARTERLY == "quarterly"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_error_budget_policy_defaults(self):
        p = ErrorBudgetPolicy(service="api", slo_target=0.999)
        assert p.id
        assert p.period == BudgetPeriod.MONTHLY
        assert p.warning_threshold == 0.3
        assert p.critical_threshold == 0.1
        assert p.created_by == ""
        assert p.metadata == {}
        assert p.created_at > 0

    def test_budget_consumption_defaults(self):
        c = BudgetConsumption(policy_id="p1", error_minutes=5.0, total_minutes=1000.0)
        assert c.id
        assert c.description == ""
        assert c.recorded_at > 0

    def test_budget_alert_defaults(self):
        a = BudgetAlert(
            policy_id="p1",
            service="api",
            status=BudgetStatus.WARNING,
            remaining_fraction=0.25,
            message="Budget warning",
        )
        assert a.id
        assert a.created_at > 0


# ---------------------------------------------------------------------------
# Create policy
# ---------------------------------------------------------------------------


class TestCreatePolicy:
    def test_create_basic(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        assert p.service == "api"
        assert p.slo_target == 0.999
        assert p.id

    def test_create_with_all_fields(self):
        t = _tracker()
        p = t.create_policy(
            service="web",
            slo_target=0.995,
            period=BudgetPeriod.WEEKLY,
            warning_threshold=0.4,
            critical_threshold=0.15,
            created_by="sre-team",
            metadata={"team": "platform"},
        )
        assert p.period == BudgetPeriod.WEEKLY
        assert p.warning_threshold == 0.4
        assert p.critical_threshold == 0.15
        assert p.created_by == "sre-team"
        assert p.metadata["team"] == "platform"

    def test_create_uses_default_thresholds(self):
        t = _tracker(warning_threshold=0.5, critical_threshold=0.2)
        p = t.create_policy(service="api", slo_target=0.999)
        assert p.warning_threshold == 0.5
        assert p.critical_threshold == 0.2

    def test_create_overrides_default_thresholds(self):
        t = _tracker(warning_threshold=0.5, critical_threshold=0.2)
        p = t.create_policy(
            service="api",
            slo_target=0.999,
            warning_threshold=0.35,
            critical_threshold=0.05,
        )
        assert p.warning_threshold == 0.35
        assert p.critical_threshold == 0.05

    def test_create_multiple_policies(self):
        t = _tracker()
        t.create_policy(service="api", slo_target=0.999)
        t.create_policy(service="web", slo_target=0.995)
        assert len(t.list_policies()) == 2


# ---------------------------------------------------------------------------
# Record consumption
# ---------------------------------------------------------------------------


class TestRecordConsumption:
    def test_record_basic(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        c = t.record_consumption(p.id, error_minutes=5.0, total_minutes=10000.0)
        assert c.policy_id == p.id
        assert c.error_minutes == 5.0
        assert c.total_minutes == 10000.0

    def test_record_with_description(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        c = t.record_consumption(
            p.id, error_minutes=2.0, total_minutes=5000.0, description="outage incident"
        )
        assert c.description == "outage incident"

    def test_record_policy_not_found(self):
        t = _tracker()
        with pytest.raises(ValueError, match="Policy not found"):
            t.record_consumption("nonexistent", error_minutes=1.0, total_minutes=100.0)

    def test_record_multiple_consumptions(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        t.record_consumption(p.id, error_minutes=2.0, total_minutes=5000.0)
        t.record_consumption(p.id, error_minutes=3.0, total_minutes=5000.0)
        stats = t.get_stats()
        assert stats["total_consumptions"] == 2


# ---------------------------------------------------------------------------
# Get remaining budget
# ---------------------------------------------------------------------------


class TestGetRemainingBudget:
    def test_healthy_status(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        # budget = (1-0.999) * 10000 = 10; consumed = 1; remaining = 9/10 = 0.9
        t.record_consumption(p.id, error_minutes=1.0, total_minutes=10000.0)
        result = t.get_remaining_budget("api")
        assert result["status"] == BudgetStatus.HEALTHY
        assert result["remaining_fraction"] == pytest.approx(0.9, abs=0.01)

    def test_warning_status(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        # budget = 10; consumed = 8; remaining = 2/10 = 0.2 (below 0.3 warning)
        t.record_consumption(p.id, error_minutes=8.0, total_minutes=10000.0)
        result = t.get_remaining_budget("api")
        assert result["status"] == BudgetStatus.WARNING

    def test_critical_status(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        # budget = 10; consumed = 9.5; remaining = 0.5/10 = 0.05 (below 0.1 critical)
        t.record_consumption(p.id, error_minutes=9.5, total_minutes=10000.0)
        result = t.get_remaining_budget("api")
        assert result["status"] == BudgetStatus.CRITICAL

    def test_exhausted_status(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        # budget = 10; consumed = 11 (overrun); remaining clamped to 0
        t.record_consumption(p.id, error_minutes=11.0, total_minutes=10000.0)
        result = t.get_remaining_budget("api")
        assert result["status"] == BudgetStatus.EXHAUSTED
        assert result["remaining_fraction"] == 0.0

    def test_exhausted_when_heavily_over_consumed(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        # budget = 10; consumed = 15; remaining clamped to 0
        t.record_consumption(p.id, error_minutes=15.0, total_minutes=10000.0)
        result = t.get_remaining_budget("api")
        assert result["status"] == BudgetStatus.EXHAUSTED
        assert result["remaining_fraction"] == 0.0

    def test_service_not_found(self):
        t = _tracker()
        result = t.get_remaining_budget("nonexistent")
        assert result["status"] == BudgetStatus.HEALTHY
        assert result["remaining_fraction"] == 1.0
        assert "error" in result

    def test_no_consumption_returns_healthy(self):
        t = _tracker()
        t.create_policy(service="api", slo_target=0.999)
        result = t.get_remaining_budget("api")
        assert result["status"] == BudgetStatus.HEALTHY
        assert result["remaining_fraction"] == 1.0

    def test_aggregates_multiple_consumptions(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        # 2 consumptions: total_minutes = 5000+5000 = 10000
        # budget = (1-0.999)*10000 = 10; error = 2+3 = 5; remaining = 5/10 = 0.5
        t.record_consumption(p.id, error_minutes=2.0, total_minutes=5000.0)
        t.record_consumption(p.id, error_minutes=3.0, total_minutes=5000.0)
        result = t.get_remaining_budget("api")
        assert result["remaining_fraction"] == pytest.approx(0.5, abs=0.01)
        assert result["status"] == BudgetStatus.HEALTHY

    def test_remaining_budget_includes_policy_id(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        t.record_consumption(p.id, error_minutes=1.0, total_minutes=10000.0)
        result = t.get_remaining_budget("api")
        assert result["policy_id"] == p.id

    def test_remaining_budget_includes_slo_target(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        t.record_consumption(p.id, error_minutes=1.0, total_minutes=10000.0)
        result = t.get_remaining_budget("api")
        assert result["slo_target"] == 0.999


# ---------------------------------------------------------------------------
# Check deployment gate
# ---------------------------------------------------------------------------


class TestCheckDeploymentGate:
    def test_allowed_when_healthy(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        t.record_consumption(p.id, error_minutes=1.0, total_minutes=10000.0)
        gate = t.check_deployment_gate("api")
        assert gate["allowed"] is True
        assert gate["status"] == BudgetStatus.HEALTHY

    def test_allowed_when_warning(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        # remaining = 0.2 -> WARNING, but still allowed
        t.record_consumption(p.id, error_minutes=8.0, total_minutes=10000.0)
        gate = t.check_deployment_gate("api")
        assert gate["allowed"] is True
        assert gate["status"] == BudgetStatus.WARNING

    def test_blocked_when_critical(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        # remaining = 0.05 -> CRITICAL, blocked
        t.record_consumption(p.id, error_minutes=9.5, total_minutes=10000.0)
        gate = t.check_deployment_gate("api")
        assert gate["allowed"] is False
        assert gate["status"] == BudgetStatus.CRITICAL

    def test_blocked_when_exhausted(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        # budget = 10; consumed = 11 (overrun) -> EXHAUSTED
        t.record_consumption(p.id, error_minutes=11.0, total_minutes=10000.0)
        gate = t.check_deployment_gate("api")
        assert gate["allowed"] is False
        assert gate["status"] == BudgetStatus.EXHAUSTED

    def test_allowed_when_service_not_found(self):
        t = _tracker()
        gate = t.check_deployment_gate("nonexistent")
        assert gate["allowed"] is True

    def test_gate_includes_reason(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        t.record_consumption(p.id, error_minutes=1.0, total_minutes=10000.0)
        gate = t.check_deployment_gate("api")
        assert "api" in gate["reason"]

    def test_gate_includes_remaining_fraction(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        t.record_consumption(p.id, error_minutes=1.0, total_minutes=10000.0)
        gate = t.check_deployment_gate("api")
        assert "remaining_fraction" in gate


# ---------------------------------------------------------------------------
# List policies
# ---------------------------------------------------------------------------


class TestListPolicies:
    def test_list_empty(self):
        t = _tracker()
        assert len(t.list_policies()) == 0

    def test_list_with_data(self):
        t = _tracker()
        t.create_policy(service="api", slo_target=0.999)
        t.create_policy(service="web", slo_target=0.995)
        policies = t.list_policies()
        assert len(policies) == 2
        names = {p.service for p in policies}
        assert names == {"api", "web"}


# ---------------------------------------------------------------------------
# Get policy
# ---------------------------------------------------------------------------


class TestGetPolicy:
    def test_found(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        result = t.get_policy(p.id)
        assert result is not None
        assert result.service == "api"

    def test_not_found(self):
        t = _tracker()
        assert t.get_policy("nonexistent") is None


# ---------------------------------------------------------------------------
# Delete policy
# ---------------------------------------------------------------------------


class TestDeletePolicy:
    def test_delete_success(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        assert t.delete_policy(p.id) is True
        assert t.get_policy(p.id) is None

    def test_delete_not_found(self):
        t = _tracker()
        assert t.delete_policy("nonexistent") is False

    def test_delete_reduces_count(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        t.create_policy(service="web", slo_target=0.995)
        t.delete_policy(p.id)
        assert len(t.list_policies()) == 1


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        t = _tracker()
        s = t.get_stats()
        assert s["total_policies"] == 0
        assert s["total_consumptions"] == 0
        assert s["total_alerts"] == 0
        assert s["services_tracked"] == 0

    def test_stats_with_data(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        t.record_consumption(p.id, error_minutes=1.0, total_minutes=10000.0)
        s = t.get_stats()
        assert s["total_policies"] == 1
        assert s["total_consumptions"] == 1
        assert s["services_tracked"] == 1

    def test_stats_alerts_generated(self):
        t = _tracker()
        p = t.create_policy(service="api", slo_target=0.999)
        # Push into WARNING to generate an alert
        t.record_consumption(p.id, error_minutes=8.0, total_minutes=10000.0)
        t.get_remaining_budget("api")
        s = t.get_stats()
        assert s["total_alerts"] >= 1

    def test_stats_multiple_services(self):
        t = _tracker()
        t.create_policy(service="api", slo_target=0.999)
        t.create_policy(service="web", slo_target=0.995)
        s = t.get_stats()
        assert s["services_tracked"] == 2
