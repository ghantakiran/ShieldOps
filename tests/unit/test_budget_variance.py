"""Tests for shieldops.billing.budget_variance — BudgetVarianceTracker."""

from __future__ import annotations

from shieldops.billing.budget_variance import (
    BudgetCategory,
    BudgetVarianceReport,
    BudgetVarianceTracker,
    VarianceDetail,
    VarianceRecord,
    VarianceSeverity,
    VarianceType,
)


def _engine(**kw) -> BudgetVarianceTracker:
    return BudgetVarianceTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # VarianceType (5)
    def test_type_over_budget(self):
        assert VarianceType.OVER_BUDGET == "over_budget"

    def test_type_under_budget(self):
        assert VarianceType.UNDER_BUDGET == "under_budget"

    def test_type_on_target(self):
        assert VarianceType.ON_TARGET == "on_target"

    def test_type_trending_over(self):
        assert VarianceType.TRENDING_OVER == "trending_over"

    def test_type_trending_under(self):
        assert VarianceType.TRENDING_UNDER == "trending_under"

    # VarianceSeverity (5)
    def test_severity_critical(self):
        assert VarianceSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert VarianceSeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert VarianceSeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert VarianceSeverity.LOW == "low"

    def test_severity_negligible(self):
        assert VarianceSeverity.NEGLIGIBLE == "negligible"

    # BudgetCategory (5)
    def test_category_infrastructure(self):
        assert BudgetCategory.INFRASTRUCTURE == "infrastructure"

    def test_category_personnel(self):
        assert BudgetCategory.PERSONNEL == "personnel"

    def test_category_licensing(self):
        assert BudgetCategory.LICENSING == "licensing"

    def test_category_services(self):
        assert BudgetCategory.SERVICES == "services"

    def test_category_operations(self):
        assert BudgetCategory.OPERATIONS == "operations"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_variance_record_defaults(self):
        r = VarianceRecord()
        assert r.id
        assert r.budget_name == ""
        assert r.category == BudgetCategory.INFRASTRUCTURE
        assert r.variance_type == VarianceType.ON_TARGET
        assert r.severity == VarianceSeverity.NEGLIGIBLE
        assert r.budgeted_amount == 0.0
        assert r.actual_amount == 0.0
        assert r.variance_pct == 0.0
        assert r.period == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_variance_detail_defaults(self):
        d = VarianceDetail()
        assert d.id
        assert d.budget_name == ""
        assert d.category == BudgetCategory.INFRASTRUCTURE
        assert d.line_item == ""
        assert d.variance_amount == 0.0
        assert d.reason == ""
        assert d.created_at > 0

    def test_budget_variance_report_defaults(self):
        r = BudgetVarianceReport()
        assert r.total_records == 0
        assert r.total_details == 0
        assert r.avg_variance_pct == 0.0
        assert r.by_category == {}
        assert r.by_variance_type == {}
        assert r.over_budget_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_variance
# ---------------------------------------------------------------------------


class TestRecordVariance:
    def test_basic(self):
        eng = _engine()
        r = eng.record_variance(
            budget_name="infra-q1",
            category=BudgetCategory.INFRASTRUCTURE,
            budgeted_amount=10000.0,
            actual_amount=12000.0,
            variance_pct=20.0,
        )
        assert r.budget_name == "infra-q1"
        assert r.variance_pct == 20.0
        assert r.variance_type == VarianceType.OVER_BUDGET

    def test_auto_type_under_budget(self):
        eng = _engine()
        r = eng.record_variance("infra", variance_pct=-20.0)
        assert r.variance_type == VarianceType.UNDER_BUDGET

    def test_auto_type_on_target(self):
        eng = _engine()
        r = eng.record_variance("infra", variance_pct=2.0)
        assert r.variance_type == VarianceType.ON_TARGET

    def test_auto_severity_critical(self):
        eng = _engine()
        r = eng.record_variance("infra", variance_pct=60.0)
        assert r.severity == VarianceSeverity.CRITICAL

    def test_explicit_type_overrides(self):
        eng = _engine()
        r = eng.record_variance(
            "infra",
            variance_type=VarianceType.TRENDING_OVER,
            variance_pct=2.0,
        )
        assert r.variance_type == VarianceType.TRENDING_OVER

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_variance(f"budget-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_variance
# ---------------------------------------------------------------------------


class TestGetVariance:
    def test_found(self):
        eng = _engine()
        r = eng.record_variance("infra-q1")
        assert eng.get_variance(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_variance("nonexistent") is None


# ---------------------------------------------------------------------------
# list_variances
# ---------------------------------------------------------------------------


class TestListVariances:
    def test_list_all(self):
        eng = _engine()
        eng.record_variance("infra")
        eng.record_variance("personnel")
        assert len(eng.list_variances()) == 2

    def test_filter_by_budget_name(self):
        eng = _engine()
        eng.record_variance("infra")
        eng.record_variance("personnel")
        results = eng.list_variances(budget_name="infra")
        assert len(results) == 1
        assert results[0].budget_name == "infra"

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_variance("infra", category=BudgetCategory.INFRASTRUCTURE)
        eng.record_variance("pers", category=BudgetCategory.PERSONNEL)
        results = eng.list_variances(category=BudgetCategory.PERSONNEL)
        assert len(results) == 1
        assert results[0].category == BudgetCategory.PERSONNEL


# ---------------------------------------------------------------------------
# add_detail
# ---------------------------------------------------------------------------


class TestAddDetail:
    def test_basic(self):
        eng = _engine()
        d = eng.add_detail(
            budget_name="infra",
            line_item="EC2 instances",
            variance_amount=500.0,
            reason="unexpected scaling",
        )
        assert d.budget_name == "infra"
        assert d.line_item == "EC2 instances"
        assert d.variance_amount == 500.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_detail(budget_name=f"b-{i}")
        assert len(eng._details) == 2


# ---------------------------------------------------------------------------
# analyze_variance_by_category
# ---------------------------------------------------------------------------


class TestAnalyzeVarianceByCategory:
    def test_with_data(self):
        eng = _engine(max_variance_pct=15.0)
        eng.record_variance(
            "infra1",
            category=BudgetCategory.INFRASTRUCTURE,
            budgeted_amount=10000.0,
            actual_amount=12000.0,
            variance_pct=20.0,
        )
        eng.record_variance(
            "infra2",
            category=BudgetCategory.INFRASTRUCTURE,
            budgeted_amount=5000.0,
            actual_amount=6000.0,
            variance_pct=20.0,
        )
        result = eng.analyze_variance_by_category(BudgetCategory.INFRASTRUCTURE)
        assert result["category"] == "infrastructure"
        assert result["total_records"] == 2
        assert result["avg_variance_pct"] == 20.0
        assert result["exceeds_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_variance_by_category(BudgetCategory.PERSONNEL)
        assert result["status"] == "no_data"


# ---------------------------------------------------------------------------
# identify_over_budget_items
# ---------------------------------------------------------------------------


class TestIdentifyOverBudgetItems:
    def test_with_over_budget(self):
        eng = _engine()
        eng.record_variance("infra", variance_type=VarianceType.OVER_BUDGET, variance_pct=25.0)
        eng.record_variance("pers", variance_type=VarianceType.ON_TARGET, variance_pct=2.0)
        results = eng.identify_over_budget_items()
        assert len(results) == 1
        assert results[0]["variance_type"] == "over_budget"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_over_budget_items() == []


# ---------------------------------------------------------------------------
# rank_by_variance_pct
# ---------------------------------------------------------------------------


class TestRankByVariancePct:
    def test_sorted_by_abs_descending(self):
        eng = _engine()
        eng.record_variance("infra", variance_pct=10.0)
        eng.record_variance("pers", variance_pct=-40.0)
        results = eng.rank_by_variance_pct()
        assert results[0]["abs_variance_pct"] == 40.0
        assert results[1]["abs_variance_pct"] == 10.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_variance_pct() == []


# ---------------------------------------------------------------------------
# detect_variance_trends
# ---------------------------------------------------------------------------


class TestDetectVarianceTrends:
    def test_worsening_trend(self):
        eng = _engine()
        eng.record_variance("infra", variance_pct=10.0)
        eng.record_variance("infra", variance_pct=30.0)
        trends = eng.detect_variance_trends()
        assert len(trends) == 1
        assert trends[0]["worsening"] is True
        assert trends[0]["variance_delta"] == 20.0

    def test_single_record_no_trend(self):
        eng = _engine()
        eng.record_variance("infra", variance_pct=10.0)
        trends = eng.detect_variance_trends()
        assert len(trends) == 0


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(max_variance_pct=15.0)
        eng.record_variance("infra", variance_type=VarianceType.OVER_BUDGET, variance_pct=30.0)
        eng.add_detail("infra", line_item="EC2")
        report = eng.generate_report()
        assert isinstance(report, BudgetVarianceReport)
        assert report.total_records == 1
        assert report.total_details == 1
        assert report.over_budget_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within acceptable limits" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_variance("infra")
        eng.add_detail("infra")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._details) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_details"] == 0
        assert stats["severity_distribution"] == {}
        assert stats["unique_budgets"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_variance("infra", variance_pct=60.0)
        eng.record_variance("pers", variance_pct=2.0)
        eng.add_detail("infra")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_details"] == 1
        assert stats["unique_budgets"] == 2
        assert "critical" in stats["severity_distribution"]
