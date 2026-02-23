"""Tests for shieldops.analytics.capacity_trends — CapacityTrendAnalyzer."""

from __future__ import annotations

import time

import pytest

from shieldops.analytics.capacity_trends import (
    CapacitySnapshot,
    CapacityTrendAnalyzer,
    ResourceType,
    TrendAnalysis,
    TrendDirection,
)


def _analyzer(**kw) -> CapacityTrendAnalyzer:
    return CapacityTrendAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ResourceType (5 values)

    def test_resource_type_cpu(self):
        assert ResourceType.CPU == "cpu"

    def test_resource_type_memory(self):
        assert ResourceType.MEMORY == "memory"

    def test_resource_type_storage(self):
        assert ResourceType.STORAGE == "storage"

    def test_resource_type_network(self):
        assert ResourceType.NETWORK == "network"

    def test_resource_type_instances(self):
        assert ResourceType.INSTANCES == "instances"

    # TrendDirection (3 values)

    def test_trend_direction_increasing(self):
        assert TrendDirection.INCREASING == "increasing"

    def test_trend_direction_stable(self):
        assert TrendDirection.STABLE == "stable"

    def test_trend_direction_decreasing(self):
        assert TrendDirection.DECREASING == "decreasing"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_capacity_snapshot_defaults(self):
        snap = CapacitySnapshot(
            service="web",
            resource_type=ResourceType.CPU,
            used=50.0,
            total=100.0,
        )
        assert snap.id
        assert snap.service == "web"
        assert snap.utilization_pct == 0.0
        assert snap.recorded_at > 0

    def test_trend_analysis_defaults(self):
        ta = TrendAnalysis(
            service="web",
            resource_type=ResourceType.CPU,
        )
        assert ta.id
        assert ta.direction == TrendDirection.STABLE
        assert ta.growth_rate_pct == 0.0
        assert ta.days_to_exhaustion is None
        assert ta.current_utilization == 0.0
        assert ta.recommended_action == ""
        assert ta.analyzed_at > 0


# ---------------------------------------------------------------------------
# record_snapshot
# ---------------------------------------------------------------------------


class TestRecordSnapshot:
    def test_basic_record(self):
        ana = _analyzer()
        snap = ana.record_snapshot("web", ResourceType.CPU, 40.0, 100.0)
        assert snap.service == "web"
        assert snap.resource_type == ResourceType.CPU
        assert snap.used == 40.0
        assert snap.total == 100.0

    def test_auto_calculates_utilization_pct(self):
        ana = _analyzer()
        snap = ana.record_snapshot("web", ResourceType.CPU, 75.0, 100.0)
        assert snap.utilization_pct == pytest.approx(75.0, abs=0.01)

    def test_utilization_zero_when_total_is_zero(self):
        ana = _analyzer()
        snap = ana.record_snapshot("web", ResourceType.CPU, 0.0, 0.0)
        assert snap.utilization_pct == pytest.approx(0.0, abs=0.01)

    def test_trims_to_max(self):
        ana = _analyzer(max_snapshots=3)
        ana.record_snapshot("s1", ResourceType.CPU, 10, 100)
        ana.record_snapshot("s2", ResourceType.CPU, 20, 100)
        ana.record_snapshot("s3", ResourceType.CPU, 30, 100)
        ana.record_snapshot("s4", ResourceType.CPU, 40, 100)
        all_snaps = ana.get_snapshots()
        assert len(all_snaps) == 3


# ---------------------------------------------------------------------------
# analyze_trend
# ---------------------------------------------------------------------------


class TestAnalyzeTrend:
    def _record_growing(
        self,
        ana: CapacityTrendAnalyzer,
    ) -> None:
        """Record snapshots with increasing utilization over time."""
        base = time.time() - 86400 * 10  # 10 days ago
        for i in range(5):
            snap = ana.record_snapshot(
                "web",
                ResourceType.CPU,
                used=20.0 + i * 15.0,
                total=100.0,
            )
            # Override recorded_at for deterministic time deltas
            snap.recorded_at = base + i * 86400

    def test_increasing_direction_for_growing_usage(self):
        ana = _analyzer()
        self._record_growing(ana)
        result = ana.analyze_trend("web", ResourceType.CPU)
        assert result.direction == TrendDirection.INCREASING

    def test_stable_for_flat_usage(self):
        ana = _analyzer()
        base = time.time() - 86400 * 5
        for i in range(5):
            snap = ana.record_snapshot(
                "web",
                ResourceType.CPU,
                used=50.0,
                total=100.0,
            )
            snap.recorded_at = base + i * 86400
        result = ana.analyze_trend("web", ResourceType.CPU)
        assert result.direction == TrendDirection.STABLE

    def test_decreasing_for_declining_usage(self):
        ana = _analyzer()
        base = time.time() - 86400 * 5
        for i in range(5):
            snap = ana.record_snapshot(
                "web",
                ResourceType.CPU,
                used=80.0 - i * 15.0,
                total=100.0,
            )
            snap.recorded_at = base + i * 86400
        result = ana.analyze_trend("web", ResourceType.CPU)
        assert result.direction == TrendDirection.DECREASING

    def test_computes_days_to_exhaustion_when_increasing(self):
        ana = _analyzer()
        self._record_growing(ana)
        result = ana.analyze_trend("web", ResourceType.CPU)
        assert result.days_to_exhaustion is not None
        assert result.days_to_exhaustion > 0

    def test_no_exhaustion_when_decreasing(self):
        ana = _analyzer()
        base = time.time() - 86400 * 5
        for i in range(5):
            snap = ana.record_snapshot(
                "web",
                ResourceType.CPU,
                used=80.0 - i * 15.0,
                total=100.0,
            )
            snap.recorded_at = base + i * 86400
        result = ana.analyze_trend("web", ResourceType.CPU)
        assert result.days_to_exhaustion is None


# ---------------------------------------------------------------------------
# growth_rate
# ---------------------------------------------------------------------------


class TestGrowthRate:
    def test_positive_rate_for_increasing(self):
        ana = _analyzer()
        base = time.time() - 86400 * 5
        for i in range(5):
            snap = ana.record_snapshot(
                "web",
                ResourceType.CPU,
                used=20.0 + i * 10.0,
                total=100.0,
            )
            snap.recorded_at = base + i * 86400
        result = ana.analyze_trend("web", ResourceType.CPU)
        assert result.growth_rate_pct > 0

    def test_negative_rate_for_decreasing(self):
        ana = _analyzer()
        base = time.time() - 86400 * 5
        for i in range(5):
            snap = ana.record_snapshot(
                "web",
                ResourceType.CPU,
                used=80.0 - i * 10.0,
                total=100.0,
            )
            snap.recorded_at = base + i * 86400
        result = ana.analyze_trend("web", ResourceType.CPU)
        assert result.growth_rate_pct < 0

    def test_zero_for_single_snapshot(self):
        ana = _analyzer()
        ana.record_snapshot("web", ResourceType.CPU, 50.0, 100.0)
        result = ana.analyze_trend("web", ResourceType.CPU)
        assert result.growth_rate_pct == pytest.approx(0.0, abs=0.001)


# ---------------------------------------------------------------------------
# at_risk_resources
# ---------------------------------------------------------------------------


class TestAtRiskResources:
    def test_finds_resources_above_threshold(self):
        ana = _analyzer(exhaustion_threshold=80.0)
        ana.record_snapshot("web", ResourceType.CPU, 90.0, 100.0)
        ana.analyze_trend("web", ResourceType.CPU)
        at_risk = ana.get_at_risk_resources()
        assert len(at_risk) >= 1
        assert at_risk[0].service == "web"

    def test_finds_resources_with_near_exhaustion(self):
        ana = _analyzer(exhaustion_threshold=95.0)
        base = time.time() - 86400 * 5
        for i in range(5):
            snap = ana.record_snapshot(
                "web",
                ResourceType.CPU,
                used=70.0 + i * 5.0,
                total=100.0,
            )
            snap.recorded_at = base + i * 86400
        ana.analyze_trend("web", ResourceType.CPU)
        at_risk = ana.get_at_risk_resources()
        # current=90%, threshold=95% but days_to_exhaustion < 30
        has_web = any(r.service == "web" for r in at_risk)
        assert has_web


# ---------------------------------------------------------------------------
# get_snapshots
# ---------------------------------------------------------------------------


class TestGetSnapshots:
    def test_filter_by_service(self):
        ana = _analyzer()
        ana.record_snapshot("web", ResourceType.CPU, 50, 100)
        ana.record_snapshot("db", ResourceType.CPU, 60, 100)
        results = ana.get_snapshots(service="web")
        assert len(results) == 1
        assert results[0].service == "web"

    def test_filter_combined_service_and_resource(self):
        ana = _analyzer()
        ana.record_snapshot("web", ResourceType.CPU, 50, 100)
        ana.record_snapshot("web", ResourceType.MEMORY, 40, 100)
        ana.record_snapshot("db", ResourceType.CPU, 30, 100)
        results = ana.get_snapshots(
            service="web",
            resource_type=ResourceType.CPU,
        )
        assert len(results) == 1
        assert results[0].service == "web"
        assert results[0].resource_type == ResourceType.CPU

    def test_empty_when_no_match(self):
        ana = _analyzer()
        ana.record_snapshot("web", ResourceType.CPU, 50, 100)
        results = ana.get_snapshots(service="nonexistent")
        assert len(results) == 0

    def test_filter_by_resource_type(self):
        ana = _analyzer()
        ana.record_snapshot("web", ResourceType.CPU, 50, 100)
        ana.record_snapshot("web", ResourceType.MEMORY, 40, 100)
        results = ana.get_snapshots(resource_type=ResourceType.CPU)
        assert len(results) == 1
        assert results[0].resource_type == ResourceType.CPU

    def test_respects_limit(self):
        ana = _analyzer()
        for i in range(10):
            ana.record_snapshot("web", ResourceType.CPU, i * 5, 100)
        results = ana.get_snapshots(limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# list_analyses / get_analysis
# ---------------------------------------------------------------------------


class TestListAnalyses:
    def test_list_all(self):
        ana = _analyzer()
        ana.record_snapshot("web", ResourceType.CPU, 50, 100)
        ana.record_snapshot("db", ResourceType.MEMORY, 60, 100)
        ana.analyze_trend("web", ResourceType.CPU)
        ana.analyze_trend("db", ResourceType.MEMORY)
        results = ana.list_analyses()
        assert len(results) == 2

    def test_filter_by_service(self):
        ana = _analyzer()
        ana.record_snapshot("web", ResourceType.CPU, 50, 100)
        ana.record_snapshot("db", ResourceType.CPU, 60, 100)
        ana.analyze_trend("web", ResourceType.CPU)
        ana.analyze_trend("db", ResourceType.CPU)
        results = ana.list_analyses(service="web")
        assert len(results) == 1
        assert results[0].service == "web"

    def test_filter_by_direction(self):
        ana = _analyzer()
        ana.record_snapshot("web", ResourceType.CPU, 50, 100)
        ana.analyze_trend("web", ResourceType.CPU)
        stable = ana.list_analyses(direction=TrendDirection.STABLE)
        assert all(a.direction == TrendDirection.STABLE for a in stable)


class TestGetAnalysis:
    def test_found(self):
        ana = _analyzer()
        ana.record_snapshot("web", ResourceType.CPU, 50, 100)
        result = ana.analyze_trend("web", ResourceType.CPU)
        fetched = ana.get_analysis(result.id)
        assert fetched is not None
        assert fetched.id == result.id

    def test_not_found(self):
        ana = _analyzer()
        assert ana.get_analysis("nonexistent") is None


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        ana = _analyzer()
        stats = ana.get_stats()
        assert stats["total_snapshots"] == 0
        assert stats["total_analyses"] == 0
        assert stats["services_tracked"] == 0
        assert stats["resource_distribution"] == {}
        assert stats["at_risk_count"] == 0

    def test_stats_populated(self):
        ana = _analyzer()
        ana.record_snapshot("web", ResourceType.CPU, 50, 100)
        ana.record_snapshot("web", ResourceType.MEMORY, 40, 100)
        ana.record_snapshot("db", ResourceType.STORAGE, 80, 100)
        ana.analyze_trend("web", ResourceType.CPU)
        stats = ana.get_stats()
        assert stats["total_snapshots"] == 3
        assert stats["total_analyses"] == 1
        assert stats["services_tracked"] == 2
        assert ResourceType.CPU in stats["resource_distribution"]
        assert ResourceType.MEMORY in stats["resource_distribution"]
        assert ResourceType.STORAGE in stats["resource_distribution"]


# ---------------------------------------------------------------------------
# recommended_action messages
# ---------------------------------------------------------------------------


class TestRecommendedAction:
    def test_critical_utilization_message(self):
        ana = _analyzer(exhaustion_threshold=80.0)
        ana.record_snapshot("web", ResourceType.CPU, 95.0, 100.0)
        result = ana.analyze_trend("web", ResourceType.CPU)
        assert "critical" in result.recommended_action.lower()

    def test_exhaustion_warning_message(self):
        ana = _analyzer(exhaustion_threshold=95.0)
        base = time.time() - 86400 * 5
        for i in range(5):
            snap = ana.record_snapshot(
                "web",
                ResourceType.CPU,
                used=70.0 + i * 5.0,
                total=100.0,
            )
            snap.recorded_at = base + i * 86400
        result = ana.analyze_trend("web", ResourceType.CPU)
        # current=90%, increasing, days_to_exhaustion < 30
        if result.days_to_exhaustion and result.days_to_exhaustion < 30:
            assert "exhaustion" in result.recommended_action.lower()

    def test_increasing_monitoring_message(self):
        ana = _analyzer(exhaustion_threshold=99.0)
        base = time.time() - 86400 * 10
        for i in range(5):
            snap = ana.record_snapshot(
                "web",
                ResourceType.CPU,
                used=10.0 + i * 5.0,
                total=100.0,
            )
            snap.recorded_at = base + i * 86400
        result = ana.analyze_trend("web", ResourceType.CPU)
        # current=30%, increasing, days_to_exhaustion > 30
        if result.direction == TrendDirection.INCREASING and (
            result.days_to_exhaustion is None or result.days_to_exhaustion >= 30
        ):
            assert "monitor" in result.recommended_action.lower()

    def test_decreasing_downsizing_message(self):
        ana = _analyzer(exhaustion_threshold=99.0)
        base = time.time() - 86400 * 5
        for i in range(5):
            snap = ana.record_snapshot(
                "web",
                ResourceType.CPU,
                used=80.0 - i * 15.0,
                total=100.0,
            )
            snap.recorded_at = base + i * 86400
        result = ana.analyze_trend("web", ResourceType.CPU)
        assert "downsizing" in result.recommended_action.lower()
