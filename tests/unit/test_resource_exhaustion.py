"""Tests for shieldops.analytics.resource_exhaustion — ResourceExhaustionForecaster."""

from __future__ import annotations

from shieldops.analytics.resource_exhaustion import (
    ConsumptionTrend,
    ExhaustionRecord,
    ExhaustionReport,
    ExhaustionThreshold,
    ExhaustionUrgency,
    ResourceExhaustionForecaster,
    ResourceType,
)


def _engine(**kw) -> ResourceExhaustionForecaster:
    return ResourceExhaustionForecaster(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ResourceType (5)
    def test_type_cpu(self):
        assert ResourceType.CPU == "cpu"

    def test_type_memory(self):
        assert ResourceType.MEMORY == "memory"

    def test_type_disk(self):
        assert ResourceType.DISK == "disk"

    def test_type_network(self):
        assert ResourceType.NETWORK_BANDWIDTH == "network_bandwidth"

    def test_type_iops(self):
        assert ResourceType.IOPS == "iops"

    # ExhaustionUrgency (5)
    def test_urgency_safe(self):
        assert ExhaustionUrgency.SAFE == "safe"

    def test_urgency_watch(self):
        assert ExhaustionUrgency.WATCH == "watch"

    def test_urgency_warning(self):
        assert ExhaustionUrgency.WARNING == "warning"

    def test_urgency_critical(self):
        assert ExhaustionUrgency.CRITICAL == "critical"

    def test_urgency_imminent(self):
        assert ExhaustionUrgency.IMMINENT == "imminent"

    # ConsumptionTrend (5)
    def test_trend_declining(self):
        assert ConsumptionTrend.DECLINING == "declining"

    def test_trend_stable(self):
        assert ConsumptionTrend.STABLE == "stable"

    def test_trend_gradual(self):
        assert ConsumptionTrend.GRADUAL_INCREASE == "gradual_increase"

    def test_trend_rapid(self):
        assert ConsumptionTrend.RAPID_INCREASE == "rapid_increase"

    def test_trend_spike(self):
        assert ConsumptionTrend.SPIKE == "spike"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = ExhaustionRecord()
        assert r.id
        assert r.resource_id == ""
        assert r.resource_type == ResourceType.CPU
        assert r.resource_name == ""
        assert r.current_usage_pct == 0.0
        assert r.capacity_total == 0.0
        assert r.urgency == ExhaustionUrgency.SAFE
        assert r.trend == ConsumptionTrend.STABLE
        assert r.created_at > 0

    def test_threshold_defaults(self):
        r = ExhaustionThreshold()
        assert r.id
        assert r.resource_type == ResourceType.CPU
        assert r.warning_hours == 48.0
        assert r.critical_hours == 12.0
        assert r.imminent_hours == 2.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = ExhaustionReport()
        assert r.total_resources == 0
        assert r.at_risk_count == 0
        assert r.by_urgency == {}
        assert r.by_type == {}
        assert r.by_trend == {}
        assert r.avg_hours_to_exhaustion == 0.0
        assert r.recommendations == []


# -------------------------------------------------------------------
# record_usage
# -------------------------------------------------------------------


class TestRecordUsage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_usage(
            "res-001",
            ResourceType.CPU,
            "web-cpu",
            current_usage_pct=50.0,
            capacity_total=100.0,
            consumption_rate_per_hour=1.0,
        )
        assert r.resource_id == "res-001"
        assert r.resource_type == ResourceType.CPU
        assert r.resource_name == "web-cpu"

    def test_high_urgency_imminent(self):
        eng = _engine()
        # remaining = 100*(1 - 96/100)=4, hours=4/2.5=1.6 → IMMINENT
        r = eng.record_usage(
            "res-002",
            ResourceType.MEMORY,
            "db-mem",
            current_usage_pct=96.0,
            capacity_total=100.0,
            consumption_rate_per_hour=2.5,
        )
        assert r.urgency == ExhaustionUrgency.IMMINENT
        assert r.estimated_exhaustion_hours == 1.6

    def test_safe_resource(self):
        eng = _engine()
        # remaining = 100*(1 - 10/100)=90, hours=90/0.1=900 → SAFE (>168)
        r = eng.record_usage(
            "res-003",
            ResourceType.DISK,
            "data-disk",
            current_usage_pct=10.0,
            capacity_total=100.0,
            consumption_rate_per_hour=0.1,
        )
        assert r.urgency == ExhaustionUrgency.SAFE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_usage(
                f"res-{i}",
                ResourceType.CPU,
                f"cpu-{i}",
                current_usage_pct=50.0,
                capacity_total=100.0,
                consumption_rate_per_hour=1.0,
            )
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_record
# -------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_usage(
            "res-001",
            ResourceType.CPU,
            "web-cpu",
            current_usage_pct=50.0,
            capacity_total=100.0,
            consumption_rate_per_hour=1.0,
        )
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# -------------------------------------------------------------------
# list_records
# -------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_usage(
            "res-001",
            ResourceType.CPU,
            "cpu-1",
            current_usage_pct=50.0,
            capacity_total=100.0,
            consumption_rate_per_hour=1.0,
        )
        eng.record_usage(
            "res-002",
            ResourceType.MEMORY,
            "mem-1",
            current_usage_pct=60.0,
            capacity_total=100.0,
            consumption_rate_per_hour=1.0,
        )
        assert len(eng.list_records()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_usage(
            "res-001",
            ResourceType.CPU,
            "cpu-1",
            current_usage_pct=50.0,
            capacity_total=100.0,
            consumption_rate_per_hour=1.0,
        )
        eng.record_usage(
            "res-002",
            ResourceType.MEMORY,
            "mem-1",
            current_usage_pct=60.0,
            capacity_total=100.0,
            consumption_rate_per_hour=1.0,
        )
        results = eng.list_records(resource_type=ResourceType.CPU)
        assert len(results) == 1
        assert results[0].resource_type == ResourceType.CPU

    def test_filter_by_urgency(self):
        eng = _engine()
        eng.record_usage(
            "res-001",
            ResourceType.CPU,
            "cpu-safe",
            current_usage_pct=10.0,
            capacity_total=100.0,
            consumption_rate_per_hour=0.01,
        )
        eng.record_usage(
            "res-002",
            ResourceType.MEMORY,
            "mem-imminent",
            current_usage_pct=99.0,
            capacity_total=100.0,
            consumption_rate_per_hour=5.0,
        )
        results = eng.list_records(urgency=ExhaustionUrgency.IMMINENT)
        assert len(results) == 1


# -------------------------------------------------------------------
# forecast_exhaustion
# -------------------------------------------------------------------


class TestForecastExhaustion:
    def test_normal_rate(self):
        eng = _engine()
        result = eng.forecast_exhaustion(
            current_usage_pct=50.0,
            capacity_total=100.0,
            consumption_rate_per_hour=5.0,
        )
        # remaining=50, hours=50/5=10
        assert result["estimated_exhaustion_hours"] == 10.0
        assert result["remaining_capacity"] == 50.0

    def test_zero_rate(self):
        eng = _engine()
        result = eng.forecast_exhaustion(
            current_usage_pct=50.0,
            capacity_total=100.0,
            consumption_rate_per_hour=0.0,
        )
        assert result["estimated_exhaustion_hours"] == 99999.0


# -------------------------------------------------------------------
# set_threshold
# -------------------------------------------------------------------


class TestSetThreshold:
    def test_set_custom(self):
        eng = _engine()
        threshold = eng.set_threshold(
            ResourceType.DISK,
            warning_hours=72.0,
            critical_hours=24.0,
            imminent_hours=4.0,
        )
        assert threshold.resource_type == ResourceType.DISK
        assert threshold.warning_hours == 72.0
        assert len(eng._thresholds) == 1

    def test_affects_classification(self):
        eng = _engine()
        eng.set_threshold(
            ResourceType.DISK,
            warning_hours=72.0,
            critical_hours=24.0,
            imminent_hours=4.0,
        )
        # remaining=10, rate=1, hours=10 → < 24 (critical) but > 4 (imminent) → CRITICAL
        r = eng.record_usage(
            "res-001",
            ResourceType.DISK,
            "data-disk",
            current_usage_pct=90.0,
            capacity_total=100.0,
            consumption_rate_per_hour=1.0,
        )
        assert r.urgency == ExhaustionUrgency.CRITICAL


# -------------------------------------------------------------------
# identify_at_risk_resources
# -------------------------------------------------------------------


class TestIdentifyAtRiskResources:
    def test_has_at_risk(self):
        eng = _engine()
        eng.record_usage(
            "res-001",
            ResourceType.CPU,
            "cpu-risk",
            current_usage_pct=95.0,
            capacity_total=100.0,
            consumption_rate_per_hour=2.5,
        )
        at_risk = eng.identify_at_risk_resources(hours_threshold=48.0)
        assert len(at_risk) == 1
        assert at_risk[0]["resource_id"] == "res-001"

    def test_none_at_risk(self):
        eng = _engine()
        eng.record_usage(
            "res-001",
            ResourceType.DISK,
            "disk-safe",
            current_usage_pct=10.0,
            capacity_total=1000.0,
            consumption_rate_per_hour=0.01,
        )
        at_risk = eng.identify_at_risk_resources(hours_threshold=48.0)
        assert len(at_risk) == 0


# -------------------------------------------------------------------
# compute_consumption_trend
# -------------------------------------------------------------------


class TestComputeConsumptionTrend:
    def test_with_records(self):
        eng = _engine()
        # First half: rate=1.0, second half: rate=3.0 → spike (3.0 > 1.0*2.0)
        for rate in [1.0, 1.0, 3.0, 3.0]:
            eng.record_usage(
                "res-001",
                ResourceType.CPU,
                "cpu-1",
                current_usage_pct=50.0,
                capacity_total=100.0,
                consumption_rate_per_hour=rate,
            )
        result = eng.compute_consumption_trend("res-001")
        assert result["trend"] == "spike"
        assert result["sample_count"] == 4

    def test_no_records(self):
        eng = _engine()
        result = eng.compute_consumption_trend("nonexistent")
        assert result["trend"] == "stable"
        assert result["sample_count"] == 0


# -------------------------------------------------------------------
# rank_by_urgency
# -------------------------------------------------------------------


class TestRankByUrgency:
    def test_mixed_urgencies(self):
        eng = _engine()
        eng.record_usage(
            "res-safe",
            ResourceType.DISK,
            "disk-safe",
            current_usage_pct=10.0,
            capacity_total=1000.0,
            consumption_rate_per_hour=0.01,
        )
        eng.record_usage(
            "res-imminent",
            ResourceType.MEMORY,
            "mem-imminent",
            current_usage_pct=99.0,
            capacity_total=100.0,
            consumption_rate_per_hour=5.0,
        )
        ranked = eng.rank_by_urgency()
        assert len(ranked) == 2
        assert ranked[0]["urgency"] == "imminent"
        assert ranked[1]["urgency"] == "safe"

    def test_same_urgency_sorted_by_hours(self):
        eng = _engine()
        eng.record_usage(
            "res-a",
            ResourceType.CPU,
            "cpu-a",
            current_usage_pct=50.0,
            capacity_total=100.0,
            consumption_rate_per_hour=0.01,
        )
        eng.record_usage(
            "res-b",
            ResourceType.CPU,
            "cpu-b",
            current_usage_pct=80.0,
            capacity_total=100.0,
            consumption_rate_per_hour=0.01,
        )
        ranked = eng.rank_by_urgency()
        # Both are same urgency; one with fewer hours should come first
        assert ranked[0]["estimated_exhaustion_hours"] <= ranked[1]["estimated_exhaustion_hours"]


# -------------------------------------------------------------------
# generate_exhaustion_report
# -------------------------------------------------------------------


class TestGenerateExhaustionReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_exhaustion_report()
        assert report.total_resources == 0
        assert report.at_risk_count == 0

    def test_with_data(self):
        eng = _engine()
        eng.record_usage(
            "res-001",
            ResourceType.CPU,
            "cpu-1",
            current_usage_pct=95.0,
            capacity_total=100.0,
            consumption_rate_per_hour=2.5,
        )
        eng.record_usage(
            "res-002",
            ResourceType.DISK,
            "disk-1",
            current_usage_pct=10.0,
            capacity_total=1000.0,
            consumption_rate_per_hour=0.01,
        )
        report = eng.generate_exhaustion_report()
        assert report.total_resources == 2
        assert report.at_risk_count >= 1
        assert report.by_type != {}


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_usage(
            "res-001",
            ResourceType.CPU,
            "cpu-1",
            current_usage_pct=50.0,
            capacity_total=100.0,
            consumption_rate_per_hour=1.0,
        )
        eng.set_threshold(
            ResourceType.CPU,
            warning_hours=48.0,
            critical_hours=12.0,
            imminent_hours=2.0,
        )
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._thresholds) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_thresholds"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_usage(
            "res-001",
            ResourceType.MEMORY,
            "mem-1",
            current_usage_pct=70.0,
            capacity_total=100.0,
            consumption_rate_per_hour=0.5,
        )
        eng.set_threshold(
            ResourceType.MEMORY,
            warning_hours=48.0,
            critical_hours=12.0,
            imminent_hours=2.0,
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["total_thresholds"] == 1
        assert stats["unique_resources"] == 1
