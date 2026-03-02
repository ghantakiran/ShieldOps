"""Tests for shieldops.billing.spot_instance_manager."""

from __future__ import annotations

from shieldops.billing.spot_instance_manager import (
    InstanceFamily,
    InterruptionBehavior,
    SpotAnalysis,
    SpotInstanceManager,
    SpotInstanceRecord,
    SpotInstanceReport,
    SpotStrategy,
)


def _engine(**kw) -> SpotInstanceManager:
    return SpotInstanceManager(**kw)


class TestEnums:
    def test_spotstrategy_lowest_price(self):
        assert SpotStrategy.LOWEST_PRICE == "lowest_price"

    def test_spotstrategy_capacity_optimized(self):
        assert SpotStrategy.CAPACITY_OPTIMIZED == "capacity_optimized"

    def test_spotstrategy_diversified(self):
        assert SpotStrategy.DIVERSIFIED == "diversified"

    def test_spotstrategy_price_capacity(self):
        assert SpotStrategy.PRICE_CAPACITY == "price_capacity"

    def test_spotstrategy_custom(self):
        assert SpotStrategy.CUSTOM == "custom"

    def test_instancefamily_general(self):
        assert InstanceFamily.GENERAL == "general"

    def test_instancefamily_compute(self):
        assert InstanceFamily.COMPUTE == "compute"

    def test_instancefamily_memory(self):
        assert InstanceFamily.MEMORY == "memory"

    def test_instancefamily_storage(self):
        assert InstanceFamily.STORAGE == "storage"

    def test_instancefamily_accelerated(self):
        assert InstanceFamily.ACCELERATED == "accelerated"

    def test_interruptionbehavior_terminate(self):
        assert InterruptionBehavior.TERMINATE == "terminate"

    def test_interruptionbehavior_stop(self):
        assert InterruptionBehavior.STOP == "stop"

    def test_interruptionbehavior_hibernate(self):
        assert InterruptionBehavior.HIBERNATE == "hibernate"

    def test_interruptionbehavior_rebalance(self):
        assert InterruptionBehavior.REBALANCE == "rebalance"

    def test_interruptionbehavior_migrate(self):
        assert InterruptionBehavior.MIGRATE == "migrate"


class TestModels:
    def test_spot_instance_record_defaults(self):
        r = SpotInstanceRecord()
        assert r.id
        assert r.spot_strategy == SpotStrategy.CAPACITY_OPTIMIZED
        assert r.instance_family == InstanceFamily.GENERAL
        assert r.interruption_behavior == InterruptionBehavior.TERMINATE
        assert r.spot_price == 0.0
        assert r.on_demand_price == 0.0
        assert r.savings_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_spot_analysis_defaults(self):
        a = SpotAnalysis()
        assert a.id
        assert a.spot_strategy == SpotStrategy.CAPACITY_OPTIMIZED
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_spot_instance_report_defaults(self):
        r = SpotInstanceReport()
        assert r.id
        assert r.total_records == 0
        assert r.high_savings_count == 0
        assert r.avg_savings_pct == 0.0
        assert r.by_spot_strategy == {}
        assert r.by_instance_family == {}
        assert r.by_interruption_behavior == {}
        assert r.top_opportunities == []
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordSpotInstance:
    def test_basic(self):
        eng = _engine()
        r = eng.record_spot_instance(
            spot_strategy=SpotStrategy.DIVERSIFIED,
            instance_family=InstanceFamily.COMPUTE,
            interruption_behavior=InterruptionBehavior.HIBERNATE,
            spot_price=0.05,
            on_demand_price=0.20,
            savings_pct=75.0,
            service="batch-processor",
            team="data",
        )
        assert r.spot_strategy == SpotStrategy.DIVERSIFIED
        assert r.savings_pct == 75.0
        assert r.team == "data"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for _i in range(5):
            eng.record_spot_instance(spot_strategy=SpotStrategy.LOWEST_PRICE)
        assert len(eng._records) == 3


class TestGetSpotInstance:
    def test_found(self):
        eng = _engine()
        r = eng.record_spot_instance(savings_pct=60.0)
        result = eng.get_spot_instance(r.id)
        assert result is not None
        assert result.savings_pct == 60.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_spot_instance("nonexistent") is None


class TestListSpotInstances:
    def test_list_all(self):
        eng = _engine()
        eng.record_spot_instance(spot_strategy=SpotStrategy.LOWEST_PRICE)
        eng.record_spot_instance(spot_strategy=SpotStrategy.DIVERSIFIED)
        assert len(eng.list_spot_instances()) == 2

    def test_filter_by_strategy(self):
        eng = _engine()
        eng.record_spot_instance(spot_strategy=SpotStrategy.LOWEST_PRICE)
        eng.record_spot_instance(spot_strategy=SpotStrategy.DIVERSIFIED)
        results = eng.list_spot_instances(spot_strategy=SpotStrategy.LOWEST_PRICE)
        assert len(results) == 1

    def test_filter_by_family(self):
        eng = _engine()
        eng.record_spot_instance(instance_family=InstanceFamily.COMPUTE)
        eng.record_spot_instance(instance_family=InstanceFamily.MEMORY)
        results = eng.list_spot_instances(instance_family=InstanceFamily.COMPUTE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_spot_instance(team="data")
        eng.record_spot_instance(team="platform")
        results = eng.list_spot_instances(team="data")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for _i in range(10):
            eng.record_spot_instance(spot_strategy=SpotStrategy.LOWEST_PRICE)
        assert len(eng.list_spot_instances(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            spot_strategy=SpotStrategy.CAPACITY_OPTIMIZED,
            analysis_score=85.0,
            threshold=70.0,
            breached=True,
            description="spot interruption risk high",
        )
        assert a.spot_strategy == SpotStrategy.CAPACITY_OPTIMIZED
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(5):
            eng.add_analysis(spot_strategy=SpotStrategy.LOWEST_PRICE)
        assert len(eng._analyses) == 2


class TestAnalyzeStrategyDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_spot_instance(spot_strategy=SpotStrategy.LOWEST_PRICE, savings_pct=70.0)
        eng.record_spot_instance(spot_strategy=SpotStrategy.LOWEST_PRICE, savings_pct=50.0)
        result = eng.analyze_strategy_distribution()
        assert "lowest_price" in result
        assert result["lowest_price"]["count"] == 2
        assert result["lowest_price"]["avg_savings_pct"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_strategy_distribution() == {}


class TestIdentifyHighSavingsSpots:
    def test_detects_above_threshold(self):
        eng = _engine(savings_threshold=50.0)
        eng.record_spot_instance(savings_pct=75.0)
        eng.record_spot_instance(savings_pct=20.0)
        results = eng.identify_high_savings_spots()
        assert len(results) == 1

    def test_sorted_descending(self):
        eng = _engine(savings_threshold=30.0)
        eng.record_spot_instance(savings_pct=80.0)
        eng.record_spot_instance(savings_pct=50.0)
        results = eng.identify_high_savings_spots()
        assert results[0]["savings_pct"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_savings_spots() == []


class TestRankBySavings:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_spot_instance(service="batch-svc", savings_pct=75.0)
        eng.record_spot_instance(service="api-svc", savings_pct=30.0)
        results = eng.rank_by_savings()
        assert results[0]["service"] == "batch-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_savings() == []


class TestDetectSavingsTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_savings_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=90.0)
        eng.add_analysis(analysis_score=90.0)
        result = eng.detect_savings_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_savings_trends()
        assert result["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(savings_threshold=40.0)
        eng.record_spot_instance(
            spot_strategy=SpotStrategy.CAPACITY_OPTIMIZED,
            instance_family=InstanceFamily.COMPUTE,
            interruption_behavior=InterruptionBehavior.REBALANCE,
            savings_pct=60.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SpotInstanceReport)
        assert report.total_records == 1
        assert report.high_savings_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_spot_instance(spot_strategy=SpotStrategy.LOWEST_PRICE)
        eng.add_analysis(spot_strategy=SpotStrategy.LOWEST_PRICE)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["spot_strategy_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_spot_instance(
            spot_strategy=SpotStrategy.CAPACITY_OPTIMIZED,
            service="batch",
            team="data",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "capacity_optimized" in stats["spot_strategy_distribution"]
