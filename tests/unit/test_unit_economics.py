"""Tests for shieldops.billing.unit_economics — CostUnitEconomicsEngine."""

from __future__ import annotations

from shieldops.billing.unit_economics import (
    CostTier,
    CostUnitEconomicsEngine,
    EfficiencyTrend,
    UnitBenchmark,
    UnitCostRecord,
    UnitEconomicsReport,
    UnitType,
)


def _engine(**kw) -> CostUnitEconomicsEngine:
    return CostUnitEconomicsEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # UnitType (5)
    def test_unit_per_request(self):
        assert UnitType.PER_REQUEST == "per_request"

    def test_unit_per_user(self):
        assert UnitType.PER_USER == "per_user"

    def test_unit_per_transaction(self):
        assert UnitType.PER_TRANSACTION == "per_transaction"

    def test_unit_per_gb_processed(self):
        assert UnitType.PER_GB_PROCESSED == "per_gb_processed"

    def test_unit_per_event(self):
        assert UnitType.PER_EVENT == "per_event"

    # EfficiencyTrend (5)
    def test_trend_improving(self):
        assert EfficiencyTrend.IMPROVING == "improving"

    def test_trend_stable(self):
        assert EfficiencyTrend.STABLE == "stable"

    def test_trend_degrading(self):
        assert EfficiencyTrend.DEGRADING == "degrading"

    def test_trend_volatile(self):
        assert EfficiencyTrend.VOLATILE == "volatile"

    def test_trend_unknown(self):
        assert EfficiencyTrend.UNKNOWN == "unknown"

    # CostTier (5)
    def test_tier_very_low(self):
        assert CostTier.VERY_LOW == "very_low"

    def test_tier_low(self):
        assert CostTier.LOW == "low"

    def test_tier_moderate(self):
        assert CostTier.MODERATE == "moderate"

    def test_tier_high(self):
        assert CostTier.HIGH == "high"

    def test_tier_very_high(self):
        assert CostTier.VERY_HIGH == "very_high"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_unit_cost_record_defaults(self):
        r = UnitCostRecord()
        assert r.id
        assert r.service_name == ""
        assert r.unit_type == UnitType.PER_REQUEST
        assert r.total_cost == 0.0
        assert r.total_units == 0
        assert r.cost_per_unit == 0.0
        assert r.tier == CostTier.MODERATE
        assert r.team == ""
        assert r.period == ""
        assert r.created_at > 0

    def test_unit_benchmark_defaults(self):
        b = UnitBenchmark()
        assert b.id
        assert b.service_name == ""
        assert b.unit_type == UnitType.PER_REQUEST
        assert b.avg_cost_per_unit == 0.0
        assert b.p50_cost == 0.0
        assert b.p90_cost == 0.0
        assert b.industry_avg == 0.0
        assert b.sample_count == 0
        assert b.created_at > 0

    def test_unit_economics_report_defaults(self):
        r = UnitEconomicsReport()
        assert r.total_records == 0
        assert r.avg_cost_per_unit == 0.0
        assert r.by_unit_type == {}
        assert r.by_tier == {}
        assert r.expensive_services == []
        assert r.trend == ""
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_unit_cost
# ---------------------------------------------------------------------------


class TestRecordUnitCost:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_unit_cost(
            service_name="api-gateway",
            unit_type=UnitType.PER_REQUEST,
            total_cost=100.0,
            total_units=10000,
            team="platform",
            period="2026-01",
        )
        assert rec.service_name == "api-gateway"
        assert rec.unit_type == UnitType.PER_REQUEST
        assert rec.total_cost == 100.0
        assert rec.total_units == 10000
        assert rec.team == "platform"
        assert rec.period == "2026-01"

    def test_cost_per_unit_computed(self):
        eng = _engine()
        rec = eng.record_unit_cost(
            service_name="api-gateway",
            total_cost=50.0,
            total_units=1000,
        )
        assert rec.cost_per_unit == 0.05

    def test_tier_classification(self):
        eng = _engine(high_cost_threshold=0.01)
        # cost_per_unit = 100/1000 = 0.1, which is > 0.01*5=0.05 => VERY_HIGH
        rec = eng.record_unit_cost(
            service_name="expensive-svc",
            total_cost=100.0,
            total_units=1000,
        )
        assert rec.tier == CostTier.VERY_HIGH

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_unit_cost(service_name=f"svc-{i}", total_cost=10.0, total_units=100)
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        rec = eng.record_unit_cost("api-gw", total_cost=10.0, total_units=100)
        result = eng.get_record(rec.id)
        assert result is not None
        assert result.service_name == "api-gw"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_unit_cost("svc-a", total_cost=10.0, total_units=100)
        eng.record_unit_cost("svc-b", total_cost=20.0, total_units=200)
        assert len(eng.list_records()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_unit_cost("svc-a", total_cost=10.0, total_units=100)
        eng.record_unit_cost("svc-b", total_cost=20.0, total_units=200)
        results = eng.list_records(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_unit_type(self):
        eng = _engine()
        eng.record_unit_cost("svc-a", unit_type=UnitType.PER_USER, total_cost=10.0, total_units=10)
        eng.record_unit_cost("svc-b", unit_type=UnitType.PER_EVENT, total_cost=5.0, total_units=50)
        results = eng.list_records(unit_type=UnitType.PER_USER)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# compute_cost_per_unit
# ---------------------------------------------------------------------------


class TestComputeCostPerUnit:
    def test_normal(self):
        eng = _engine()
        result = eng.compute_cost_per_unit(total_cost=100.0, total_units=2000)
        assert result["cost_per_unit"] == 0.05
        assert result["total_cost"] == 100.0
        assert result["total_units"] == 2000
        assert "tier" in result
        assert "above_threshold" in result

    def test_zero_units(self):
        eng = _engine()
        result = eng.compute_cost_per_unit(total_cost=100.0, total_units=0)
        assert result["cost_per_unit"] == 0.0


# ---------------------------------------------------------------------------
# create_benchmark
# ---------------------------------------------------------------------------


class TestCreateBenchmark:
    def test_with_data(self):
        eng = _engine()
        eng.record_unit_cost("api-gw", total_cost=10.0, total_units=1000)
        eng.record_unit_cost("api-gw", total_cost=20.0, total_units=1000)
        benchmark = eng.create_benchmark("api-gw")
        assert benchmark.service_name == "api-gw"
        assert benchmark.sample_count == 2
        assert benchmark.avg_cost_per_unit > 0
        assert benchmark.p50_cost > 0
        assert benchmark.p90_cost > 0
        assert benchmark.industry_avg > 0

    def test_no_data(self):
        eng = _engine()
        benchmark = eng.create_benchmark("unknown-svc")
        assert benchmark.sample_count == 0
        assert benchmark.avg_cost_per_unit == 0.0
        assert benchmark.p50_cost == 0.0


# ---------------------------------------------------------------------------
# identify_expensive_services
# ---------------------------------------------------------------------------


class TestIdentifyExpensiveServices:
    def test_has_expensive(self):
        eng = _engine(high_cost_threshold=0.01)
        # cost_per_unit = 50/100 = 0.5 => far above 0.01
        eng.record_unit_cost("expensive-svc", total_cost=50.0, total_units=100)
        # cost_per_unit = 1/100000 = 0.00001 => below threshold
        eng.record_unit_cost("cheap-svc", total_cost=1.0, total_units=100000)
        results = eng.identify_expensive_services()
        assert len(results) == 1
        assert results[0]["service_name"] == "expensive-svc"

    def test_none_expensive(self):
        eng = _engine(high_cost_threshold=1.0)
        eng.record_unit_cost("cheap-svc", total_cost=1.0, total_units=100000)
        results = eng.identify_expensive_services()
        assert results == []


# ---------------------------------------------------------------------------
# compute_efficiency_trend
# ---------------------------------------------------------------------------


class TestComputeEfficiencyTrend:
    def test_with_history(self):
        eng = _engine()
        # Older records: higher cost
        eng.record_unit_cost("api-gw", total_cost=100.0, total_units=1000)
        eng.record_unit_cost("api-gw", total_cost=100.0, total_units=1000)
        # Recent records: lower cost
        eng.record_unit_cost("api-gw", total_cost=10.0, total_units=1000)
        eng.record_unit_cost("api-gw", total_cost=10.0, total_units=1000)
        result = eng.compute_efficiency_trend("api-gw")
        assert result["service_name"] == "api-gw"
        assert result["trend"] == EfficiencyTrend.IMPROVING.value
        assert result["sample_count"] == 4

    def test_no_history(self):
        eng = _engine()
        result = eng.compute_efficiency_trend("unknown-svc")
        assert result["trend"] == EfficiencyTrend.UNKNOWN.value
        assert result["reason"] == "Insufficient data"


# ---------------------------------------------------------------------------
# rank_by_cost_efficiency
# ---------------------------------------------------------------------------


class TestRankByCostEfficiency:
    def test_multiple_services(self):
        eng = _engine()
        eng.record_unit_cost("cheap", total_cost=1.0, total_units=10000)
        eng.record_unit_cost("expensive", total_cost=500.0, total_units=100)
        ranked = eng.rank_by_cost_efficiency()
        assert len(ranked) == 2
        # Most expensive first
        assert ranked[0]["service_name"] == "expensive"
        assert ranked[0]["avg_cost_per_unit"] > ranked[1]["avg_cost_per_unit"]

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cost_efficiency() == []


# ---------------------------------------------------------------------------
# generate_economics_report
# ---------------------------------------------------------------------------


class TestGenerateEconomicsReport:
    def test_basic_report(self):
        eng = _engine(high_cost_threshold=0.01)
        eng.record_unit_cost("svc-a", total_cost=100.0, total_units=1000, team="platform")
        eng.record_unit_cost("svc-b", total_cost=50.0, total_units=5000, team="data")
        eng.record_unit_cost("svc-a", total_cost=80.0, total_units=1000, team="platform")
        eng.record_unit_cost("svc-b", total_cost=40.0, total_units=5000, team="data")
        report = eng.generate_economics_report()
        assert report.total_records == 4
        assert report.avg_cost_per_unit > 0
        assert len(report.by_tier) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_economics_report()
        assert report.total_records == 0
        assert report.avg_cost_per_unit == 0.0
        assert report.trend == EfficiencyTrend.UNKNOWN.value


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_unit_cost("svc-a", total_cost=10.0, total_units=100)
        eng.create_benchmark("svc-a")
        assert len(eng._records) == 1
        assert len(eng._benchmarks) == 1
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._benchmarks) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_benchmarks"] == 0
        assert stats["high_cost_threshold"] == 0.01
        assert stats["tier_distribution"] == {}
        assert stats["unique_services"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_unit_cost("svc-a", total_cost=10.0, total_units=100)
        eng.record_unit_cost("svc-b", total_cost=20.0, total_units=200)
        eng.create_benchmark("svc-a")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_benchmarks"] == 1
        assert stats["unique_services"] == 2
        assert len(stats["tier_distribution"]) > 0
