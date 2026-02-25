"""Tests for shieldops.analytics.latency_budget_tracker — LatencyBudgetTracker."""

from __future__ import annotations

import pytest

from shieldops.analytics.latency_budget_tracker import (
    BudgetCompliance,
    BudgetViolation,
    EndpointTier,
    LatencyBudget,
    LatencyBudgetReport,
    LatencyBudgetTracker,
    LatencyPercentile,
)


def _engine(**kw) -> LatencyBudgetTracker:
    return LatencyBudgetTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # BudgetCompliance (5)
    def test_compliance_within_budget(self):
        assert BudgetCompliance.WITHIN_BUDGET == "within_budget"

    def test_compliance_approaching_limit(self):
        assert BudgetCompliance.APPROACHING_LIMIT == "approaching_limit"

    def test_compliance_over_budget(self):
        assert BudgetCompliance.OVER_BUDGET == "over_budget"

    def test_compliance_chronically_over(self):
        assert BudgetCompliance.CHRONICALLY_OVER == "chronically_over"

    def test_compliance_no_budget_set(self):
        assert BudgetCompliance.NO_BUDGET_SET == "no_budget_set"

    # LatencyPercentile (5)
    def test_percentile_p50(self):
        assert LatencyPercentile.P50 == "p50"

    def test_percentile_p75(self):
        assert LatencyPercentile.P75 == "p75"

    def test_percentile_p90(self):
        assert LatencyPercentile.P90 == "p90"

    def test_percentile_p95(self):
        assert LatencyPercentile.P95 == "p95"

    def test_percentile_p99(self):
        assert LatencyPercentile.P99 == "p99"

    # EndpointTier (5)
    def test_tier_critical(self):
        assert EndpointTier.CRITICAL == "critical"

    def test_tier_high(self):
        assert EndpointTier.HIGH == "high"

    def test_tier_standard(self):
        assert EndpointTier.STANDARD == "standard"

    def test_tier_low_priority(self):
        assert EndpointTier.LOW_PRIORITY == "low_priority"

    def test_tier_batch(self):
        assert EndpointTier.BATCH == "batch"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_latency_budget_defaults(self):
        b = LatencyBudget()
        assert b.id
        assert b.endpoint == ""
        assert b.tier == EndpointTier.STANDARD
        assert b.budget_ms == 200.0
        assert b.percentile == LatencyPercentile.P95
        assert b.current_ms == 0.0
        assert b.compliance == BudgetCompliance.NO_BUDGET_SET
        assert b.violation_count == 0
        assert b.created_at > 0

    def test_budget_violation_defaults(self):
        v = BudgetViolation()
        assert v.id
        assert v.budget_id == ""
        assert v.endpoint == ""
        assert v.measured_ms == 0.0
        assert v.budget_ms == 0.0
        assert v.overage_ms == 0.0
        assert v.created_at > 0

    def test_latency_budget_report_defaults(self):
        r = LatencyBudgetReport()
        assert r.total_budgets == 0
        assert r.total_violations == 0
        assert r.by_compliance == {}
        assert r.by_tier == {}
        assert r.by_percentile == {}
        assert r.chronic_violators == []
        assert r.avg_overage_ms == 0.0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# create_budget
# ---------------------------------------------------------------------------


class TestCreateBudget:
    def test_basic_creation(self):
        eng = _engine()
        b = eng.create_budget(
            endpoint="/api/v1/users",
            budget_ms=100.0,
            tier=EndpointTier.CRITICAL,
            percentile=LatencyPercentile.P99,
        )
        assert b.endpoint == "/api/v1/users"
        assert b.budget_ms == 100.0
        assert b.tier == EndpointTier.CRITICAL
        assert b.percentile == LatencyPercentile.P99
        assert b.compliance == BudgetCompliance.WITHIN_BUDGET

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.create_budget(endpoint=f"/api/v1/ep-{i}")
        assert len(eng._budgets) == 3


# ---------------------------------------------------------------------------
# get_budget
# ---------------------------------------------------------------------------


class TestGetBudget:
    def test_found(self):
        eng = _engine()
        b = eng.create_budget(endpoint="/api/v1/users")
        result = eng.get_budget(b.id)
        assert result is not None
        assert result.endpoint == "/api/v1/users"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_budget("nonexistent") is None


# ---------------------------------------------------------------------------
# list_budgets
# ---------------------------------------------------------------------------


class TestListBudgets:
    def test_list_all(self):
        eng = _engine()
        eng.create_budget(endpoint="/api/v1/users")
        eng.create_budget(endpoint="/api/v1/orders")
        assert len(eng.list_budgets()) == 2

    def test_filter_by_tier(self):
        eng = _engine()
        eng.create_budget(endpoint="/api/v1/users", tier=EndpointTier.CRITICAL)
        eng.create_budget(endpoint="/api/v1/batch", tier=EndpointTier.BATCH)
        results = eng.list_budgets(tier=EndpointTier.CRITICAL)
        assert len(results) == 1
        assert results[0].endpoint == "/api/v1/users"

    def test_filter_by_compliance(self):
        eng = _engine()
        b = eng.create_budget(endpoint="/api/v1/users", budget_ms=100.0)
        eng.create_budget(endpoint="/api/v1/orders", budget_ms=200.0)
        eng.record_measurement(b.id, 150.0)  # over budget
        results = eng.list_budgets(compliance=BudgetCompliance.OVER_BUDGET)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# record_measurement
# ---------------------------------------------------------------------------


class TestRecordMeasurement:
    def test_within_budget(self):
        eng = _engine()
        b = eng.create_budget(endpoint="/api/v1/users", budget_ms=200.0)
        result = eng.record_measurement(b.id, 100.0)
        assert result["found"] is True
        assert result["violation"] is False
        assert result["compliance"] == BudgetCompliance.WITHIN_BUDGET.value

    def test_over_budget_creates_violation(self):
        eng = _engine()
        b = eng.create_budget(endpoint="/api/v1/users", budget_ms=200.0)
        result = eng.record_measurement(b.id, 250.0)
        assert result["violation"] is True
        assert result["compliance"] == BudgetCompliance.OVER_BUDGET.value
        assert len(eng._violations) == 1
        assert eng._violations[0].overage_ms == pytest.approx(50.0)

    def test_approaching_limit(self):
        eng = _engine()
        b = eng.create_budget(endpoint="/api/v1/users", budget_ms=200.0)
        # 175ms > 200 * 0.85 = 170, so approaching limit
        result = eng.record_measurement(b.id, 175.0)
        assert result["violation"] is False
        assert result["compliance"] == BudgetCompliance.APPROACHING_LIMIT.value

    def test_not_found(self):
        eng = _engine()
        result = eng.record_measurement("nonexistent", 100.0)
        assert result["found"] is False
        assert result["violation"] is False


# ---------------------------------------------------------------------------
# list_violations
# ---------------------------------------------------------------------------


class TestListViolations:
    def test_list_all(self):
        eng = _engine()
        b = eng.create_budget(endpoint="/api/v1/users", budget_ms=100.0)
        eng.record_measurement(b.id, 150.0)
        eng.record_measurement(b.id, 200.0)
        assert len(eng.list_violations()) == 2

    def test_filter_by_budget_id(self):
        eng = _engine()
        b1 = eng.create_budget(endpoint="/api/v1/users", budget_ms=100.0)
        b2 = eng.create_budget(endpoint="/api/v1/orders", budget_ms=100.0)
        eng.record_measurement(b1.id, 150.0)
        eng.record_measurement(b2.id, 200.0)
        results = eng.list_violations(budget_id=b1.id)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# check_compliance
# ---------------------------------------------------------------------------


class TestCheckCompliance:
    def test_found(self):
        eng = _engine()
        b = eng.create_budget(endpoint="/api/v1/users", budget_ms=200.0)
        eng.record_measurement(b.id, 100.0)
        result = eng.check_compliance(b.id)
        assert result["found"] is True
        assert result["compliance"] == BudgetCompliance.WITHIN_BUDGET.value
        assert result["current_ms"] == 100.0

    def test_not_found(self):
        eng = _engine()
        result = eng.check_compliance("nonexistent")
        assert result["found"] is False
        assert result["compliance"] == BudgetCompliance.NO_BUDGET_SET.value


# ---------------------------------------------------------------------------
# find_chronic_violators
# ---------------------------------------------------------------------------


class TestFindChronicViolators:
    def test_finds_chronic(self):
        eng = _engine(chronic_violation_threshold=3)
        b = eng.create_budget(endpoint="/api/v1/users", budget_ms=100.0)
        for _ in range(3):
            eng.record_measurement(b.id, 200.0)
        chronic = eng.find_chronic_violators()
        assert len(chronic) == 1
        assert chronic[0].endpoint == "/api/v1/users"

    def test_none_chronic(self):
        eng = _engine(chronic_violation_threshold=10)
        b = eng.create_budget(endpoint="/api/v1/users", budget_ms=100.0)
        eng.record_measurement(b.id, 200.0)
        assert len(eng.find_chronic_violators()) == 0


# ---------------------------------------------------------------------------
# adjust_budget
# ---------------------------------------------------------------------------


class TestAdjustBudget:
    def test_adjust_within(self):
        eng = _engine()
        b = eng.create_budget(endpoint="/api/v1/users", budget_ms=200.0)
        eng.record_measurement(b.id, 100.0)
        result = eng.adjust_budget(b.id, 300.0)
        assert result is True
        assert b.budget_ms == 300.0
        assert b.compliance == BudgetCompliance.WITHIN_BUDGET

    def test_adjust_triggers_over(self):
        eng = _engine()
        b = eng.create_budget(endpoint="/api/v1/users", budget_ms=200.0)
        eng.record_measurement(b.id, 150.0)
        result = eng.adjust_budget(b.id, 100.0)
        assert result is True
        assert b.compliance == BudgetCompliance.OVER_BUDGET

    def test_not_found(self):
        eng = _engine()
        assert eng.adjust_budget("nonexistent", 300.0) is False


# ---------------------------------------------------------------------------
# generate_budget_report
# ---------------------------------------------------------------------------


class TestGenerateBudgetReport:
    def test_basic_report(self):
        eng = _engine(chronic_violation_threshold=2)
        b = eng.create_budget(
            endpoint="/api/v1/users",
            budget_ms=100.0,
            tier=EndpointTier.CRITICAL,
        )
        eng.record_measurement(b.id, 150.0)
        eng.record_measurement(b.id, 200.0)
        report = eng.generate_budget_report()
        assert isinstance(report, LatencyBudgetReport)
        assert report.total_budgets == 1
        assert report.total_violations == 2
        assert len(report.by_compliance) > 0
        assert len(report.by_tier) > 0
        assert report.avg_overage_ms > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_budget_report()
        assert report.total_budgets == 0
        assert report.total_violations == 0
        assert report.avg_overage_ms == 0.0
        assert "All endpoints within latency budgets" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        b = eng.create_budget(endpoint="/api/v1/users", budget_ms=100.0)
        eng.record_measurement(b.id, 200.0)
        count = eng.clear_data()
        assert count == 1
        assert len(eng._budgets) == 0
        assert len(eng._violations) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_budgets"] == 0
        assert stats["total_violations"] == 0
        assert stats["compliance_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        b = eng.create_budget(endpoint="/api/v1/users", budget_ms=200.0)
        eng.record_measurement(b.id, 100.0)
        stats = eng.get_stats()
        assert stats["total_budgets"] == 1
        assert stats["chronic_violation_threshold"] == 10
        assert "within_budget" in stats["compliance_distribution"]
