"""Tests for shieldops.analytics.capacity_utilization_tracker — CapacityUtilizationTracker."""

from __future__ import annotations

from shieldops.analytics.capacity_utilization_tracker import (
    AllocationStrategy,
    CapacityUtilizationReport,
    CapacityUtilizationTracker,
    ResourceType,
    UtilizationLevel,
    UtilizationMetric,
    UtilizationRecord,
)


def _engine(**kw) -> CapacityUtilizationTracker:
    return CapacityUtilizationTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_cpu(self):
        assert ResourceType.CPU == "cpu"

    def test_type_memory(self):
        assert ResourceType.MEMORY == "memory"

    def test_type_storage(self):
        assert ResourceType.STORAGE == "storage"

    def test_type_network(self):
        assert ResourceType.NETWORK == "network"

    def test_type_gpu(self):
        assert ResourceType.GPU == "gpu"

    def test_level_over_utilized(self):
        assert UtilizationLevel.OVER_UTILIZED == "over_utilized"

    def test_level_optimal(self):
        assert UtilizationLevel.OPTIMAL == "optimal"

    def test_level_under_utilized(self):
        assert UtilizationLevel.UNDER_UTILIZED == "under_utilized"

    def test_level_idle(self):
        assert UtilizationLevel.IDLE == "idle"

    def test_level_unknown(self):
        assert UtilizationLevel.UNKNOWN == "unknown"

    def test_strategy_reserved(self):
        assert AllocationStrategy.RESERVED == "reserved"

    def test_strategy_on_demand(self):
        assert AllocationStrategy.ON_DEMAND == "on_demand"

    def test_strategy_spot(self):
        assert AllocationStrategy.SPOT == "spot"

    def test_strategy_burstable(self):
        assert AllocationStrategy.BURSTABLE == "burstable"

    def test_strategy_dedicated(self):
        assert AllocationStrategy.DEDICATED == "dedicated"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_utilization_record_defaults(self):
        r = UtilizationRecord()
        assert r.id
        assert r.resource_id == ""
        assert r.resource_type == ResourceType.CPU
        assert r.utilization_level == UtilizationLevel.UNKNOWN
        assert r.allocation_strategy == AllocationStrategy.ON_DEMAND
        assert r.utilization_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_utilization_metric_defaults(self):
        m = UtilizationMetric()
        assert m.id
        assert m.resource_id == ""
        assert m.resource_type == ResourceType.CPU
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.created_at > 0

    def test_utilization_report_defaults(self):
        r = CapacityUtilizationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.waste_count == 0
        assert r.avg_utilization_pct == 0.0
        assert r.by_type == {}
        assert r.by_level == {}
        assert r.by_strategy == {}
        assert r.top_wasteful == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_utilization
# ---------------------------------------------------------------------------


class TestRecordUtilization:
    def test_basic(self):
        eng = _engine()
        r = eng.record_utilization(
            resource_id="RES-001",
            resource_type=ResourceType.CPU,
            utilization_level=UtilizationLevel.IDLE,
            allocation_strategy=AllocationStrategy.ON_DEMAND,
            utilization_pct=5.0,
            service="api-gw",
            team="sre",
        )
        assert r.resource_id == "RES-001"
        assert r.resource_type == ResourceType.CPU
        assert r.utilization_level == UtilizationLevel.IDLE
        assert r.allocation_strategy == AllocationStrategy.ON_DEMAND
        assert r.utilization_pct == 5.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_utilization(resource_id=f"RES-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_utilization
# ---------------------------------------------------------------------------


class TestGetUtilization:
    def test_found(self):
        eng = _engine()
        r = eng.record_utilization(
            resource_id="RES-001",
            utilization_level=UtilizationLevel.OPTIMAL,
        )
        result = eng.get_utilization(r.id)
        assert result is not None
        assert result.utilization_level == UtilizationLevel.OPTIMAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_utilization("nonexistent") is None


# ---------------------------------------------------------------------------
# list_utilizations
# ---------------------------------------------------------------------------


class TestListUtilizations:
    def test_list_all(self):
        eng = _engine()
        eng.record_utilization(resource_id="RES-001")
        eng.record_utilization(resource_id="RES-002")
        assert len(eng.list_utilizations()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_utilization(
            resource_id="RES-001",
            resource_type=ResourceType.CPU,
        )
        eng.record_utilization(
            resource_id="RES-002",
            resource_type=ResourceType.MEMORY,
        )
        results = eng.list_utilizations(resource_type=ResourceType.CPU)
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_utilization(
            resource_id="RES-001",
            utilization_level=UtilizationLevel.OPTIMAL,
        )
        eng.record_utilization(
            resource_id="RES-002",
            utilization_level=UtilizationLevel.IDLE,
        )
        results = eng.list_utilizations(level=UtilizationLevel.OPTIMAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_utilization(resource_id="RES-001", team="sre")
        eng.record_utilization(resource_id="RES-002", team="platform")
        results = eng.list_utilizations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_utilization(resource_id=f"RES-{i}")
        assert len(eng.list_utilizations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            resource_id="RES-001",
            resource_type=ResourceType.MEMORY,
            metric_score=25.0,
            threshold=40.0,
            breached=True,
            description="Below threshold",
        )
        assert m.resource_id == "RES-001"
        assert m.resource_type == ResourceType.MEMORY
        assert m.metric_score == 25.0
        assert m.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(resource_id=f"RES-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_utilization_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeUtilizationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_utilization(
            resource_id="RES-001",
            resource_type=ResourceType.CPU,
            utilization_pct=80.0,
        )
        eng.record_utilization(
            resource_id="RES-002",
            resource_type=ResourceType.CPU,
            utilization_pct=60.0,
        )
        result = eng.analyze_utilization_distribution()
        assert "cpu" in result
        assert result["cpu"]["count"] == 2
        assert result["cpu"]["avg_utilization_pct"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_utilization_distribution() == {}


# ---------------------------------------------------------------------------
# identify_wasteful_resources
# ---------------------------------------------------------------------------


class TestIdentifyWastefulResources:
    def test_detects_idle(self):
        eng = _engine()
        eng.record_utilization(
            resource_id="RES-001",
            utilization_level=UtilizationLevel.IDLE,
        )
        eng.record_utilization(
            resource_id="RES-002",
            utilization_level=UtilizationLevel.OPTIMAL,
        )
        results = eng.identify_wasteful_resources()
        assert len(results) == 1
        assert results[0]["resource_id"] == "RES-001"

    def test_detects_under_utilized(self):
        eng = _engine()
        eng.record_utilization(
            resource_id="RES-001",
            utilization_level=UtilizationLevel.UNDER_UTILIZED,
        )
        results = eng.identify_wasteful_resources()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_wasteful_resources() == []


# ---------------------------------------------------------------------------
# rank_by_utilization
# ---------------------------------------------------------------------------


class TestRankByUtilization:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_utilization(
            resource_id="RES-001",
            service="api-gw",
            utilization_pct=80.0,
        )
        eng.record_utilization(
            resource_id="RES-002",
            service="auth",
            utilization_pct=20.0,
        )
        results = eng.rank_by_utilization()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_utilization_pct"] == 20.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_utilization() == []


# ---------------------------------------------------------------------------
# detect_utilization_trends
# ---------------------------------------------------------------------------


class TestDetectUtilizationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_metric(resource_id="RES-001", metric_score=50.0)
        result = eng.detect_utilization_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_metric(resource_id="RES-001", metric_score=30.0)
        eng.add_metric(resource_id="RES-002", metric_score=30.0)
        eng.add_metric(resource_id="RES-003", metric_score=50.0)
        eng.add_metric(resource_id="RES-004", metric_score=50.0)
        result = eng.detect_utilization_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_utilization_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_utilization(
            resource_id="RES-001",
            resource_type=ResourceType.CPU,
            utilization_level=UtilizationLevel.IDLE,
            utilization_pct=5.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CapacityUtilizationReport)
        assert report.total_records == 1
        assert report.waste_count == 1
        assert len(report.top_wasteful) == 1
        assert len(report.recommendations) > 0

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
        eng.record_utilization(resource_id="RES-001")
        eng.add_metric(resource_id="RES-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["resource_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_utilization(
            resource_id="RES-001",
            resource_type=ResourceType.CPU,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "cpu" in stats["resource_type_distribution"]
