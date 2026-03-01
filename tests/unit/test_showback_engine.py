"""Tests for shieldops.billing.showback_engine — ShowbackEngine."""

from __future__ import annotations

from shieldops.billing.showback_engine import (
    ShowbackAccuracy,
    ShowbackAllocation,
    ShowbackCategory,
    ShowbackEngine,
    ShowbackGranularity,
    ShowbackRecord,
    ShowbackReport,
)


def _engine(**kw) -> ShowbackEngine:
    return ShowbackEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_compute(self):
        assert ShowbackCategory.COMPUTE == "compute"

    def test_category_storage(self):
        assert ShowbackCategory.STORAGE == "storage"

    def test_category_network(self):
        assert ShowbackCategory.NETWORK == "network"

    def test_category_database(self):
        assert ShowbackCategory.DATABASE == "database"

    def test_category_platform_services(self):
        assert ShowbackCategory.PLATFORM_SERVICES == "platform_services"

    def test_granularity_hourly(self):
        assert ShowbackGranularity.HOURLY == "hourly"

    def test_granularity_daily(self):
        assert ShowbackGranularity.DAILY == "daily"

    def test_granularity_weekly(self):
        assert ShowbackGranularity.WEEKLY == "weekly"

    def test_granularity_monthly(self):
        assert ShowbackGranularity.MONTHLY == "monthly"

    def test_granularity_quarterly(self):
        assert ShowbackGranularity.QUARTERLY == "quarterly"

    def test_accuracy_exact(self):
        assert ShowbackAccuracy.EXACT == "exact"

    def test_accuracy_estimated(self):
        assert ShowbackAccuracy.ESTIMATED == "estimated"

    def test_accuracy_projected(self):
        assert ShowbackAccuracy.PROJECTED == "projected"

    def test_accuracy_approximate(self):
        assert ShowbackAccuracy.APPROXIMATE == "approximate"

    def test_accuracy_unknown(self):
        assert ShowbackAccuracy.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_showback_record_defaults(self):
        r = ShowbackRecord()
        assert r.id
        assert r.consumer_id == ""
        assert r.showback_category == ShowbackCategory.COMPUTE
        assert r.showback_granularity == ShowbackGranularity.MONTHLY
        assert r.showback_accuracy == ShowbackAccuracy.UNKNOWN
        assert r.cost_amount == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_showback_allocation_defaults(self):
        a = ShowbackAllocation()
        assert a.id
        assert a.consumer_id == ""
        assert a.showback_category == ShowbackCategory.COMPUTE
        assert a.allocation_amount == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_showback_report_defaults(self):
        r = ShowbackReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_allocations == 0
        assert r.over_budget_count == 0
        assert r.avg_cost_amount == 0.0
        assert r.by_category == {}
        assert r.by_granularity == {}
        assert r.by_accuracy == {}
        assert r.top_consumers == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_showback
# ---------------------------------------------------------------------------


class TestRecordShowback:
    def test_basic(self):
        eng = _engine()
        r = eng.record_showback(
            consumer_id="team-alpha",
            showback_category=ShowbackCategory.COMPUTE,
            showback_granularity=ShowbackGranularity.MONTHLY,
            showback_accuracy=ShowbackAccuracy.EXACT,
            cost_amount=1500.0,
            service="api-gateway",
            team="platform",
        )
        assert r.consumer_id == "team-alpha"
        assert r.showback_category == ShowbackCategory.COMPUTE
        assert r.showback_granularity == ShowbackGranularity.MONTHLY
        assert r.showback_accuracy == ShowbackAccuracy.EXACT
        assert r.cost_amount == 1500.0
        assert r.service == "api-gateway"
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_showback(consumer_id=f"team-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_showback
# ---------------------------------------------------------------------------


class TestGetShowback:
    def test_found(self):
        eng = _engine()
        r = eng.record_showback(
            consumer_id="team-alpha",
            showback_accuracy=ShowbackAccuracy.ESTIMATED,
        )
        result = eng.get_showback(r.id)
        assert result is not None
        assert result.showback_accuracy == ShowbackAccuracy.ESTIMATED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_showback("nonexistent") is None


# ---------------------------------------------------------------------------
# list_showbacks
# ---------------------------------------------------------------------------


class TestListShowbacks:
    def test_list_all(self):
        eng = _engine()
        eng.record_showback(consumer_id="team-alpha")
        eng.record_showback(consumer_id="team-beta")
        assert len(eng.list_showbacks()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_showback(
            consumer_id="team-alpha",
            showback_category=ShowbackCategory.COMPUTE,
        )
        eng.record_showback(
            consumer_id="team-beta",
            showback_category=ShowbackCategory.STORAGE,
        )
        results = eng.list_showbacks(category=ShowbackCategory.COMPUTE)
        assert len(results) == 1

    def test_filter_by_granularity(self):
        eng = _engine()
        eng.record_showback(
            consumer_id="team-alpha",
            showback_granularity=ShowbackGranularity.MONTHLY,
        )
        eng.record_showback(
            consumer_id="team-beta",
            showback_granularity=ShowbackGranularity.DAILY,
        )
        results = eng.list_showbacks(granularity=ShowbackGranularity.MONTHLY)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_showback(consumer_id="team-alpha", service="api")
        eng.record_showback(consumer_id="team-beta", service="web")
        results = eng.list_showbacks(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_showback(consumer_id="team-alpha", team="sre")
        eng.record_showback(consumer_id="team-beta", team="platform")
        results = eng.list_showbacks(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_showback(consumer_id=f"team-{i}")
        assert len(eng.list_showbacks(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_allocation
# ---------------------------------------------------------------------------


class TestAddAllocation:
    def test_basic(self):
        eng = _engine()
        a = eng.add_allocation(
            consumer_id="team-alpha",
            showback_category=ShowbackCategory.DATABASE,
            allocation_amount=2000.0,
            threshold=2500.0,
            breached=False,
            description="Database allocation within budget",
        )
        assert a.consumer_id == "team-alpha"
        assert a.showback_category == ShowbackCategory.DATABASE
        assert a.allocation_amount == 2000.0
        assert a.threshold == 2500.0
        assert a.breached is False
        assert a.description == "Database allocation within budget"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_allocation(consumer_id=f"team-{i}")
        assert len(eng._allocations) == 2


# ---------------------------------------------------------------------------
# analyze_cost_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeCostDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_showback(
            consumer_id="team-alpha",
            showback_category=ShowbackCategory.COMPUTE,
            cost_amount=1000.0,
        )
        eng.record_showback(
            consumer_id="team-beta",
            showback_category=ShowbackCategory.COMPUTE,
            cost_amount=2000.0,
        )
        result = eng.analyze_cost_distribution()
        assert "compute" in result
        assert result["compute"]["count"] == 2
        assert result["compute"]["avg_cost_amount"] == 1500.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_cost_distribution() == {}


# ---------------------------------------------------------------------------
# identify_over_budget_consumers
# ---------------------------------------------------------------------------


class TestIdentifyOverBudgetConsumers:
    def test_detects_over_budget(self):
        eng = _engine()
        eng.add_allocation(
            consumer_id="team-alpha",
            breached=True,
        )
        eng.add_allocation(
            consumer_id="team-beta",
            breached=False,
        )
        results = eng.identify_over_budget_consumers()
        assert len(results) == 1
        assert results[0]["consumer_id"] == "team-alpha"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_over_budget_consumers() == []


# ---------------------------------------------------------------------------
# rank_by_cost_amount
# ---------------------------------------------------------------------------


class TestRankByCostAmount:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_showback(consumer_id="team-alpha", service="api", cost_amount=900.0)
        eng.record_showback(consumer_id="team-beta", service="api", cost_amount=800.0)
        eng.record_showback(consumer_id="team-gamma", service="web", cost_amount=500.0)
        results = eng.rank_by_cost_amount()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["total_cost_amount"] == 1700.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cost_amount() == []


# ---------------------------------------------------------------------------
# detect_cost_trends
# ---------------------------------------------------------------------------


class TestDetectCostTrends:
    def test_stable(self):
        eng = _engine()
        for val in [100.0, 100.0, 100.0, 100.0]:
            eng.add_allocation(consumer_id="team-alpha", allocation_amount=val)
        result = eng.detect_cost_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [50.0, 50.0, 200.0, 200.0]:
            eng.add_allocation(consumer_id="team-alpha", allocation_amount=val)
        result = eng.detect_cost_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_cost_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_showback(
            consumer_id="team-alpha",
            showback_category=ShowbackCategory.COMPUTE,
            cost_amount=1500.0,
            service="api",
            team="platform",
        )
        eng.add_allocation(
            consumer_id="team-alpha",
            breached=True,
        )
        report = eng.generate_report()
        assert isinstance(report, ShowbackReport)
        assert report.total_records == 1
        assert report.over_budget_count == 1
        assert report.avg_cost_amount == 1500.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_showback(consumer_id="team-alpha")
        eng.add_allocation(consumer_id="team-alpha")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._allocations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_allocations"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_showback(
            consumer_id="team-alpha",
            showback_category=ShowbackCategory.STORAGE,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_teams"] == 1
        assert "storage" in stats["category_distribution"]
