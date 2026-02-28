"""Tests for shieldops.observability.observability_cost — ObservabilityCostAllocator."""

from __future__ import annotations

from shieldops.observability.observability_cost import (
    AllocationTrend,
    CostAllocation,
    CostDriver,
    ObservabilityCostAllocator,
    ObservabilityCostRecord,
    ObservabilityCostReport,
    SignalType,
)


def _engine(**kw) -> ObservabilityCostAllocator:
    return ObservabilityCostAllocator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # SignalType (5)
    def test_signal_metrics(self):
        assert SignalType.METRICS == "metrics"

    def test_signal_logs(self):
        assert SignalType.LOGS == "logs"

    def test_signal_traces(self):
        assert SignalType.TRACES == "traces"

    def test_signal_events(self):
        assert SignalType.EVENTS == "events"

    def test_signal_profiles(self):
        assert SignalType.PROFILES == "profiles"

    # CostDriver (5)
    def test_driver_cardinality(self):
        assert CostDriver.CARDINALITY == "cardinality"

    def test_driver_volume(self):
        assert CostDriver.VOLUME == "volume"

    def test_driver_retention(self):
        assert CostDriver.RETENTION == "retention"

    def test_driver_query_load(self):
        assert CostDriver.QUERY_LOAD == "query_load"

    def test_driver_ingestion_rate(self):
        assert CostDriver.INGESTION_RATE == "ingestion_rate"

    # AllocationTrend (5)
    def test_trend_increasing(self):
        assert AllocationTrend.INCREASING == "increasing"

    def test_trend_stable(self):
        assert AllocationTrend.STABLE == "stable"

    def test_trend_decreasing(self):
        assert AllocationTrend.DECREASING == "decreasing"

    def test_trend_volatile(self):
        assert AllocationTrend.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert AllocationTrend.INSUFFICIENT_DATA == "insufficient_data"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_cost_record_defaults(self):
        r = ObservabilityCostRecord()
        assert r.id
        assert r.team_name == ""
        assert r.signal_type == SignalType.METRICS
        assert r.cost_driver == CostDriver.VOLUME
        assert r.monthly_cost_usd == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_allocation_defaults(self):
        a = CostAllocation()
        assert a.id
        assert a.allocation_name == ""
        assert a.signal_type == SignalType.METRICS
        assert a.cost_driver == CostDriver.VOLUME
        assert a.allocated_amount_usd == 0.0
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ObservabilityCostReport()
        assert r.total_records == 0
        assert r.total_allocations == 0
        assert r.avg_monthly_cost_usd == 0.0
        assert r.by_signal == {}
        assert r.by_driver == {}
        assert r.high_cost_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_cost
# ---------------------------------------------------------------------------


class TestRecordCost:
    def test_basic(self):
        eng = _engine()
        r = eng.record_cost(
            "platform-team",
            signal_type=SignalType.LOGS,
            cost_driver=CostDriver.VOLUME,
            monthly_cost_usd=500.0,
        )
        assert r.team_name == "platform-team"
        assert r.monthly_cost_usd == 500.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_cost(f"team-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_cost
# ---------------------------------------------------------------------------


class TestGetCost:
    def test_found(self):
        eng = _engine()
        r = eng.record_cost("platform-team", monthly_cost_usd=100.0)
        assert eng.get_cost(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_cost("nonexistent") is None


# ---------------------------------------------------------------------------
# list_costs
# ---------------------------------------------------------------------------


class TestListCosts:
    def test_list_all(self):
        eng = _engine()
        eng.record_cost("team-a")
        eng.record_cost("team-b")
        assert len(eng.list_costs()) == 2

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_cost("team-a")
        eng.record_cost("team-b")
        results = eng.list_costs(team_name="team-a")
        assert len(results) == 1

    def test_filter_by_signal(self):
        eng = _engine()
        eng.record_cost("t1", signal_type=SignalType.LOGS)
        eng.record_cost("t2", signal_type=SignalType.TRACES)
        results = eng.list_costs(signal_type=SignalType.LOGS)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# add_allocation
# ---------------------------------------------------------------------------


class TestAddAllocation:
    def test_basic(self):
        eng = _engine()
        a = eng.add_allocation(
            "logs-allocation",
            signal_type=SignalType.LOGS,
            allocated_amount_usd=2000.0,
        )
        assert a.allocation_name == "logs-allocation"
        assert a.allocated_amount_usd == 2000.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_allocation(f"alloc-{i}")
        assert len(eng._allocations) == 2


# ---------------------------------------------------------------------------
# analyze_team_costs
# ---------------------------------------------------------------------------


class TestAnalyzeTeamCosts:
    def test_with_data(self):
        eng = _engine(high_cost_threshold=1000.0)
        eng.record_cost("platform-team", monthly_cost_usd=500.0)
        eng.record_cost("platform-team", monthly_cost_usd=300.0)
        result = eng.analyze_team_costs("platform-team")
        assert result["team_name"] == "platform-team"
        assert result["avg_monthly_cost_usd"] == 400.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_team_costs("ghost")
        assert result["status"] == "no_data"


# ---------------------------------------------------------------------------
# identify_high_cost_teams
# ---------------------------------------------------------------------------


class TestIdentifyHighCostTeams:
    def test_with_high(self):
        eng = _engine(high_cost_threshold=500.0)
        eng.record_cost("team-a", monthly_cost_usd=800.0)
        eng.record_cost("team-a", monthly_cost_usd=900.0)
        eng.record_cost("team-b", monthly_cost_usd=100.0)
        results = eng.identify_high_cost_teams()
        assert len(results) == 1
        assert results[0]["team_name"] == "team-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_cost_teams() == []


# ---------------------------------------------------------------------------
# rank_by_monthly_cost
# ---------------------------------------------------------------------------


class TestRankByMonthlyCost:
    def test_with_data(self):
        eng = _engine()
        eng.record_cost("team-a", monthly_cost_usd=100.0)
        eng.record_cost("team-b", monthly_cost_usd=500.0)
        results = eng.rank_by_monthly_cost()
        assert results[0]["team_name"] == "team-b"
        assert results[0]["avg_monthly_cost_usd"] == 500.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_monthly_cost() == []


# ---------------------------------------------------------------------------
# detect_cost_trends
# ---------------------------------------------------------------------------


class TestDetectCostTrends:
    def test_with_enough_data(self):
        eng = _engine()
        eng.record_cost("team-a", monthly_cost_usd=100.0)
        eng.record_cost("team-a", monthly_cost_usd=110.0)
        eng.record_cost("team-a", monthly_cost_usd=300.0)
        eng.record_cost("team-a", monthly_cost_usd=350.0)
        results = eng.detect_cost_trends()
        assert len(results) == 1
        assert results[0]["team_name"] == "team-a"
        assert results[0]["trend"] == AllocationTrend.INCREASING.value

    def test_insufficient_data(self):
        eng = _engine()
        eng.record_cost("team-a", monthly_cost_usd=100.0)
        eng.record_cost("team-a", monthly_cost_usd=110.0)
        results = eng.detect_cost_trends()
        assert len(results) == 0


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(high_cost_threshold=500.0)
        eng.record_cost("team-a", monthly_cost_usd=800.0, signal_type=SignalType.LOGS)
        eng.add_allocation("logs-alloc")
        report = eng.generate_report()
        assert isinstance(report, ObservabilityCostReport)
        assert report.total_records == 1
        assert report.total_allocations == 1
        assert report.high_cost_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within acceptable bounds" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_cost("team-a")
        eng.add_allocation("alloc-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._allocations) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_allocations"] == 0
        assert stats["signal_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_cost("team-a", signal_type=SignalType.LOGS)
        eng.record_cost("team-b", signal_type=SignalType.TRACES)
        eng.add_allocation("alloc-a")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_allocations"] == 1
        assert stats["unique_teams"] == 2
