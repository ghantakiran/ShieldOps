"""Tests for shieldops.billing.unit_economics_tracker."""

from __future__ import annotations

from shieldops.billing.unit_economics_tracker import (
    EconomicsAnalysis,
    Granularity,
    TrendDirection,
    UnitEconomicsRecord,
    UnitEconomicsReport,
    UnitEconomicsTracker,
    UnitMetric,
)


def _engine(**kw) -> UnitEconomicsTracker:
    return UnitEconomicsTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_unitmetric_cost_per_request(self):
        assert UnitMetric.COST_PER_REQUEST == "cost_per_request"

    def test_unitmetric_cost_per_user(self):
        assert UnitMetric.COST_PER_USER == "cost_per_user"

    def test_unitmetric_cost_per_transaction(self):
        assert UnitMetric.COST_PER_TRANSACTION == "cost_per_transaction"

    def test_unitmetric_cost_per_gb(self):
        assert UnitMetric.COST_PER_GB == "cost_per_gb"

    def test_unitmetric_cost_per_cpu_hour(self):
        assert UnitMetric.COST_PER_CPU_HOUR == "cost_per_cpu_hour"

    def test_granularity_hourly(self):
        assert Granularity.HOURLY == "hourly"

    def test_granularity_daily(self):
        assert Granularity.DAILY == "daily"

    def test_granularity_weekly(self):
        assert Granularity.WEEKLY == "weekly"

    def test_granularity_monthly(self):
        assert Granularity.MONTHLY == "monthly"

    def test_granularity_quarterly(self):
        assert Granularity.QUARTERLY == "quarterly"

    def test_trenddirection_increasing(self):
        assert TrendDirection.INCREASING == "increasing"

    def test_trenddirection_stable(self):
        assert TrendDirection.STABLE == "stable"

    def test_trenddirection_decreasing(self):
        assert TrendDirection.DECREASING == "decreasing"

    def test_trenddirection_volatile(self):
        assert TrendDirection.VOLATILE == "volatile"

    def test_trenddirection_unknown(self):
        assert TrendDirection.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_unit_economics_record_defaults(self):
        r = UnitEconomicsRecord()
        assert r.id
        assert r.unit_metric == UnitMetric.COST_PER_REQUEST
        assert r.granularity == Granularity.DAILY
        assert r.trend_direction == TrendDirection.UNKNOWN
        assert r.unit_cost == 0.0
        assert r.unit_volume == 0.0
        assert r.total_cost == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_economics_analysis_defaults(self):
        a = EconomicsAnalysis()
        assert a.id
        assert a.unit_metric == UnitMetric.COST_PER_REQUEST
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_unit_economics_report_defaults(self):
        r = UnitEconomicsReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.degrading_count == 0
        assert r.avg_unit_cost == 0.0
        assert r.by_unit_metric == {}
        assert r.top_expensive == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_unit_economics
# ---------------------------------------------------------------------------


class TestRecordUnitEconomics:
    def test_basic(self):
        eng = _engine()
        r = eng.record_unit_economics(
            unit_metric=UnitMetric.COST_PER_TRANSACTION,
            granularity=Granularity.DAILY,
            trend_direction=TrendDirection.INCREASING,
            unit_cost=0.005,
            unit_volume=1000000.0,
            total_cost=5000.0,
            service="payments",
            team="fintech",
        )
        assert r.unit_metric == UnitMetric.COST_PER_TRANSACTION
        assert r.unit_cost == 0.005
        assert r.team == "fintech"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for _i in range(5):
            eng.record_unit_economics(unit_metric=UnitMetric.COST_PER_REQUEST)
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_unit_economics
# ---------------------------------------------------------------------------


class TestGetUnitEconomics:
    def test_found(self):
        eng = _engine()
        r = eng.record_unit_economics(
            unit_metric=UnitMetric.COST_PER_GB,
            unit_cost=0.023,
        )
        result = eng.get_unit_economics(r.id)
        assert result is not None
        assert result.unit_metric == UnitMetric.COST_PER_GB

    def test_not_found(self):
        eng = _engine()
        assert eng.get_unit_economics("nonexistent") is None


# ---------------------------------------------------------------------------
# list_unit_economics
# ---------------------------------------------------------------------------


class TestListUnitEconomics:
    def test_list_all(self):
        eng = _engine()
        eng.record_unit_economics(unit_metric=UnitMetric.COST_PER_REQUEST)
        eng.record_unit_economics(unit_metric=UnitMetric.COST_PER_GB)
        assert len(eng.list_unit_economics()) == 2

    def test_filter_by_metric(self):
        eng = _engine()
        eng.record_unit_economics(unit_metric=UnitMetric.COST_PER_REQUEST)
        eng.record_unit_economics(unit_metric=UnitMetric.COST_PER_GB)
        results = eng.list_unit_economics(unit_metric=UnitMetric.COST_PER_REQUEST)
        assert len(results) == 1

    def test_filter_by_granularity(self):
        eng = _engine()
        eng.record_unit_economics(granularity=Granularity.DAILY)
        eng.record_unit_economics(granularity=Granularity.MONTHLY)
        results = eng.list_unit_economics(granularity=Granularity.DAILY)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_unit_economics(team="fintech")
        eng.record_unit_economics(team="platform")
        results = eng.list_unit_economics(team="fintech")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for _i in range(10):
            eng.record_unit_economics(unit_metric=UnitMetric.COST_PER_REQUEST)
        assert len(eng.list_unit_economics(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            unit_metric=UnitMetric.COST_PER_USER,
            analysis_score=88.0,
            threshold=70.0,
            breached=True,
            description="unit cost rising",
        )
        assert a.unit_metric == UnitMetric.COST_PER_USER
        assert a.analysis_score == 88.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(5):
            eng.add_analysis(unit_metric=UnitMetric.COST_PER_REQUEST)
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_metric_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeMetricDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_unit_economics(unit_metric=UnitMetric.COST_PER_REQUEST, unit_cost=0.001)
        eng.record_unit_economics(unit_metric=UnitMetric.COST_PER_REQUEST, unit_cost=0.003)
        result = eng.analyze_metric_distribution()
        assert "cost_per_request" in result
        assert result["cost_per_request"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_metric_distribution() == {}


# ---------------------------------------------------------------------------
# identify_increasing_costs
# ---------------------------------------------------------------------------


class TestIdentifyIncreasingCosts:
    def test_finds_increasing(self):
        eng = _engine()
        eng.record_unit_economics(trend_direction=TrendDirection.INCREASING, unit_cost=0.01)
        eng.record_unit_economics(trend_direction=TrendDirection.STABLE, unit_cost=0.005)
        results = eng.identify_increasing_costs()
        assert len(results) == 1

    def test_sorted_descending_by_cost(self):
        eng = _engine()
        eng.record_unit_economics(trend_direction=TrendDirection.INCREASING, unit_cost=0.05)
        eng.record_unit_economics(trend_direction=TrendDirection.INCREASING, unit_cost=0.01)
        results = eng.identify_increasing_costs()
        assert results[0]["unit_cost"] == 0.05

    def test_empty(self):
        eng = _engine()
        assert eng.identify_increasing_costs() == []


# ---------------------------------------------------------------------------
# rank_by_unit_cost
# ---------------------------------------------------------------------------


class TestRankByUnitCost:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_unit_economics(service="ec2", unit_cost=0.10)
        eng.record_unit_economics(service="s3", unit_cost=0.02)
        results = eng.rank_by_unit_cost()
        assert results[0]["service"] == "ec2"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_unit_cost() == []


# ---------------------------------------------------------------------------
# detect_cost_trends
# ---------------------------------------------------------------------------


class TestDetectCostTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(unit_metric=UnitMetric.COST_PER_REQUEST, analysis_score=50.0)
        result = eng.detect_cost_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_cost_trends()
        assert result["trend"] == "improving"

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
        eng.record_unit_economics(
            unit_metric=UnitMetric.COST_PER_REQUEST,
            trend_direction=TrendDirection.INCREASING,
            unit_cost=0.05,
        )
        report = eng.generate_report()
        assert isinstance(report, UnitEconomicsReport)
        assert report.total_records == 1
        assert report.degrading_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_unit_economics(unit_metric=UnitMetric.COST_PER_REQUEST)
        eng.add_analysis(unit_metric=UnitMetric.COST_PER_REQUEST)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["unit_metric_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_unit_economics(
            unit_metric=UnitMetric.COST_PER_REQUEST,
            service="api",
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert "cost_per_request" in stats["unit_metric_distribution"]
