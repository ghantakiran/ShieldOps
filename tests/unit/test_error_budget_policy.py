"""Tests for shieldops.sla.error_budget_policy — ErrorBudgetPolicyEngine."""

from __future__ import annotations

from shieldops.sla.error_budget_policy import (
    BudgetPolicyReport,
    BudgetStatus,
    BudgetViolation,
    BudgetWindow,
    ErrorBudgetPolicy,
    ErrorBudgetPolicyEngine,
    PolicyAction,
)


def _engine(**kw) -> ErrorBudgetPolicyEngine:
    return ErrorBudgetPolicyEngine(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # BudgetStatus (5)
    def test_status_healthy(self):
        assert BudgetStatus.HEALTHY == "healthy"

    def test_status_warning(self):
        assert BudgetStatus.WARNING == "warning"

    def test_status_critical(self):
        assert BudgetStatus.CRITICAL == "critical"

    def test_status_exhausted(self):
        assert BudgetStatus.EXHAUSTED == "exhausted"

    def test_status_frozen(self):
        assert BudgetStatus.FROZEN == "frozen"

    # PolicyAction (5)
    def test_action_notify(self):
        assert PolicyAction.NOTIFY == "notify"

    def test_action_slow_down(self):
        assert PolicyAction.SLOW_DOWN == "slow_down"

    def test_action_freeze_deploys(self):
        assert PolicyAction.FREEZE_DEPLOYS == "freeze_deploys"

    def test_action_escalate(self):
        assert PolicyAction.ESCALATE == "escalate"

    def test_action_auto_rollback(self):
        assert PolicyAction.AUTO_ROLLBACK == "auto_rollback"

    # BudgetWindow (5)
    def test_window_hourly(self):
        assert BudgetWindow.HOURLY == "hourly"

    def test_window_daily(self):
        assert BudgetWindow.DAILY == "daily"

    def test_window_weekly(self):
        assert BudgetWindow.WEEKLY == "weekly"

    def test_window_monthly(self):
        assert BudgetWindow.MONTHLY == "monthly"

    def test_window_quarterly(self):
        assert BudgetWindow.QUARTERLY == "quarterly"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_policy_defaults(self):
        p = ErrorBudgetPolicy()
        assert p.id
        assert p.service_name == ""
        assert p.slo_target_pct == 99.9
        assert p.window == BudgetWindow.MONTHLY
        assert p.remaining_budget_pct == 100.0
        assert p.status == BudgetStatus.HEALTHY
        assert p.actions == []
        assert p.consumed_pct == 0.0
        assert p.created_at > 0

    def test_violation_defaults(self):
        v = BudgetViolation()
        assert v.id
        assert v.policy_id == ""
        assert v.service_name == ""
        assert v.consumed_pct == 0.0
        assert v.action_taken == ""
        assert v.violated_at > 0

    def test_report_defaults(self):
        r = BudgetPolicyReport()
        assert r.total_policies == 0
        assert r.total_violations == 0
        assert r.avg_remaining_budget == 0.0
        assert r.by_status == {}
        assert r.by_window == {}
        assert r.critical_services == []
        assert r.recommendations == []


# -------------------------------------------------------------------
# create_policy
# -------------------------------------------------------------------


class TestCreatePolicy:
    def test_basic_create(self):
        eng = _engine()
        p = eng.create_policy("api-gateway")
        assert p.service_name == "api-gateway"
        assert p.slo_target_pct == 99.9
        assert p.remaining_budget_pct == 100.0

    def test_custom_window(self):
        eng = _engine()
        p = eng.create_policy("web", window=BudgetWindow.WEEKLY)
        assert p.window == BudgetWindow.WEEKLY

    def test_unique_ids(self):
        eng = _engine()
        p1 = eng.create_policy("svc1")
        p2 = eng.create_policy("svc2")
        assert p1.id != p2.id

    def test_eviction_at_max(self):
        eng = _engine(max_policies=3)
        for i in range(5):
            eng.create_policy(f"svc{i}")
        assert len(eng._policies) == 3


# -------------------------------------------------------------------
# get_policy
# -------------------------------------------------------------------


class TestGetPolicy:
    def test_found(self):
        eng = _engine()
        p = eng.create_policy("test")
        assert eng.get_policy(p.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_policy("nonexistent") is None


# -------------------------------------------------------------------
# list_policies
# -------------------------------------------------------------------


class TestListPolicies:
    def test_list_all(self):
        eng = _engine()
        eng.create_policy("svc1")
        eng.create_policy("svc2")
        assert len(eng.list_policies()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.create_policy("api")
        eng.create_policy("web")
        results = eng.list_policies(service_name="api")
        assert len(results) == 1
        assert results[0].service_name == "api"

    def test_filter_by_status(self):
        eng = _engine()
        eng.create_policy("svc1")
        p2 = eng.create_policy("svc2")
        eng.consume_budget(p2.id, 90.0)
        results = eng.list_policies(status=BudgetStatus.CRITICAL)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.create_policy(f"svc{i}")
        results = eng.list_policies(limit=3)
        assert len(results) == 3


# -------------------------------------------------------------------
# consume_budget
# -------------------------------------------------------------------


class TestConsumeBudget:
    def test_basic_consume(self):
        eng = _engine()
        p = eng.create_policy("test")
        result = eng.consume_budget(p.id, 30.0)
        assert result["consumed_pct"] == 30.0
        assert result["remaining_pct"] == 70.0

    def test_status_warning(self):
        eng = _engine()
        p = eng.create_policy("test")
        eng.consume_budget(p.id, 55.0)
        assert p.status == BudgetStatus.WARNING

    def test_status_critical(self):
        eng = _engine()
        p = eng.create_policy("test")
        eng.consume_budget(p.id, 85.0)
        assert p.status == BudgetStatus.CRITICAL

    def test_status_exhausted(self):
        eng = _engine()
        p = eng.create_policy("test")
        eng.consume_budget(p.id, 100.0)
        assert p.status == BudgetStatus.EXHAUSTED

    def test_not_found(self):
        eng = _engine()
        result = eng.consume_budget("bad", 10.0)
        assert result.get("error") == "policy_not_found"


# -------------------------------------------------------------------
# evaluate_policy
# -------------------------------------------------------------------


class TestEvaluatePolicy:
    def test_healthy_no_actions(self):
        eng = _engine()
        p = eng.create_policy("test")
        result = eng.evaluate_policy(p.id)
        assert result["actions"] == []

    def test_warning_notify(self):
        eng = _engine()
        p = eng.create_policy("test")
        eng.consume_budget(p.id, 55.0)
        result = eng.evaluate_policy(p.id)
        assert "notify" in result["actions"]

    def test_exhausted_freeze(self):
        eng = _engine()
        p = eng.create_policy("test")
        eng.consume_budget(p.id, 100.0)
        result = eng.evaluate_policy(p.id)
        assert "freeze_deploys" in result["actions"]
        assert "auto_rollback" in result["actions"]

    def test_not_found(self):
        eng = _engine()
        result = eng.evaluate_policy("bad")
        assert result.get("error") == "policy_not_found"


# -------------------------------------------------------------------
# trigger_action
# -------------------------------------------------------------------


class TestTriggerAction:
    def test_trigger(self):
        eng = _engine()
        p = eng.create_policy("test")
        result = eng.trigger_action(p.id, PolicyAction.NOTIFY)
        assert result["triggered"] is True
        assert result["action"] == "notify"

    def test_records_violation(self):
        eng = _engine()
        p = eng.create_policy("test")
        eng.trigger_action(p.id, PolicyAction.ESCALATE)
        assert len(eng._violations) == 1
        assert eng._violations[0].action_taken == "escalate"

    def test_not_found(self):
        eng = _engine()
        result = eng.trigger_action("bad", PolicyAction.NOTIFY)
        assert result.get("error") == "policy_not_found"


# -------------------------------------------------------------------
# calculate_burn_rate
# -------------------------------------------------------------------


class TestCalculateBurnRate:
    def test_burn_rate(self):
        eng = _engine()
        p = eng.create_policy("test")
        eng.consume_budget(p.id, 50.0)
        result = eng.calculate_burn_rate(p.id)
        assert result["burn_rate_pct_per_hour"] > 0

    def test_no_consumption(self):
        eng = _engine()
        p = eng.create_policy("test")
        result = eng.calculate_burn_rate(p.id)
        assert result["burn_rate_pct_per_hour"] == 0.0

    def test_not_found(self):
        eng = _engine()
        result = eng.calculate_burn_rate("bad")
        assert result.get("error") == "policy_not_found"


# -------------------------------------------------------------------
# reset_budget
# -------------------------------------------------------------------


class TestResetBudget:
    def test_reset(self):
        eng = _engine()
        p = eng.create_policy("test")
        eng.consume_budget(p.id, 90.0)
        assert p.status == BudgetStatus.CRITICAL
        result = eng.reset_budget(p.id)
        assert result["remaining_pct"] == 100.0
        assert p.status == BudgetStatus.HEALTHY

    def test_not_found(self):
        eng = _engine()
        result = eng.reset_budget("bad")
        assert result.get("error") == "policy_not_found"


# -------------------------------------------------------------------
# generate_budget_report
# -------------------------------------------------------------------


class TestGenerateBudgetReport:
    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_budget_report()
        assert report.total_policies == 0
        assert report.total_violations == 0

    def test_populated_report(self):
        eng = _engine()
        eng.create_policy("api")
        p2 = eng.create_policy("web")
        eng.consume_budget(p2.id, 100.0)
        eng.evaluate_policy(p2.id)
        report = eng.generate_budget_report()
        assert report.total_policies == 2
        assert "web" in report.critical_services
        assert report.total_violations > 0

    def test_recommendations_for_critical(self):
        eng = _engine()
        p = eng.create_policy("critical-svc")
        eng.consume_budget(p.id, 100.0)
        report = eng.generate_budget_report()
        assert len(report.recommendations) > 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.create_policy("test")
        eng.clear_data()
        assert len(eng._policies) == 0
        assert len(eng._violations) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_policies"] == 0
        assert stats["total_violations"] == 0

    def test_populated(self):
        eng = _engine()
        p = eng.create_policy("test")
        eng.consume_budget(p.id, 85.0)
        stats = eng.get_stats()
        assert stats["total_policies"] == 1
        assert stats["critical"] == 1
