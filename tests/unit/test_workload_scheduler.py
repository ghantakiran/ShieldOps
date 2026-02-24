"""Tests for shieldops.operations.workload_scheduler — WorkloadSchedulingOptimizer."""

from __future__ import annotations

import time

from shieldops.operations.workload_scheduler import (
    ContentionLevel,
    JobPriority,
    ScheduleConflict,
    ScheduleOptimizationReport,
    ScheduleStrategy,
    WorkloadEntry,
    WorkloadSchedulingOptimizer,
)


def _engine(**kw) -> WorkloadSchedulingOptimizer:
    return WorkloadSchedulingOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # JobPriority (5)
    def test_priority_critical(self):
        assert JobPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert JobPriority.HIGH == "high"

    def test_priority_medium(self):
        assert JobPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert JobPriority.LOW == "low"

    def test_priority_background(self):
        assert JobPriority.BACKGROUND == "background"

    # ScheduleStrategy (5)
    def test_strategy_cost_optimized(self):
        assert ScheduleStrategy.COST_OPTIMIZED == "cost_optimized"

    def test_strategy_performance_optimized(self):
        assert ScheduleStrategy.PERFORMANCE_OPTIMIZED == "performance_optimized"

    def test_strategy_balanced(self):
        assert ScheduleStrategy.BALANCED == "balanced"

    def test_strategy_off_peak(self):
        assert ScheduleStrategy.OFF_PEAK == "off_peak"

    def test_strategy_spot_aware(self):
        assert ScheduleStrategy.SPOT_AWARE == "spot_aware"

    # ContentionLevel (5)
    def test_contention_none(self):
        assert ContentionLevel.NONE == "none"

    def test_contention_low(self):
        assert ContentionLevel.LOW == "low"

    def test_contention_moderate(self):
        assert ContentionLevel.MODERATE == "moderate"

    def test_contention_high(self):
        assert ContentionLevel.HIGH == "high"

    def test_contention_critical(self):
        assert ContentionLevel.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_workload_entry_defaults(self):
        w = WorkloadEntry()
        assert w.id
        assert w.workload_name == ""
        assert w.priority == JobPriority.MEDIUM
        assert w.strategy == ScheduleStrategy.BALANCED
        assert w.scheduled_start == 0.0
        assert w.duration_seconds == 3600
        assert w.resource_requirements == {}
        assert w.estimated_cost == 0.0

    def test_schedule_conflict_defaults(self):
        c = ScheduleConflict()
        assert c.id
        assert c.workload_a_id == ""
        assert c.workload_b_id == ""
        assert c.overlap_seconds == 0
        assert c.contention_level == ContentionLevel.LOW
        assert c.recommendation == ""

    def test_schedule_optimization_report_defaults(self):
        r = ScheduleOptimizationReport()
        assert r.total_workloads == 0
        assert r.conflict_count == 0
        assert r.peak_window_start == 0.0
        assert r.peak_window_end == 0.0
        assert r.total_estimated_cost == 0.0
        assert r.potential_savings == 0.0
        assert r.strategy_breakdown == {}
        assert r.recommendations == []


# ---------------------------------------------------------------------------
# register_workload
# ---------------------------------------------------------------------------


class TestRegisterWorkload:
    def test_basic_register(self):
        eng = _engine()
        w = eng.register_workload(
            workload_name="etl-daily",
            priority=JobPriority.HIGH,
            strategy=ScheduleStrategy.COST_OPTIMIZED,
            scheduled_start=1000.0,
            duration_seconds=7200,
            estimated_cost=50.0,
        )
        assert w.workload_name == "etl-daily"
        assert w.priority == JobPriority.HIGH
        assert w.strategy == ScheduleStrategy.COST_OPTIMIZED
        assert w.scheduled_start == 1000.0
        assert w.duration_seconds == 7200
        assert w.estimated_cost == 50.0

    def test_eviction_at_max(self):
        eng = _engine(max_workloads=3)
        for i in range(5):
            eng.register_workload(workload_name=f"job-{i}")
        assert len(eng._workloads) == 3


# ---------------------------------------------------------------------------
# get_workload
# ---------------------------------------------------------------------------


class TestGetWorkload:
    def test_found(self):
        eng = _engine()
        w = eng.register_workload(workload_name="batch-1")
        assert eng.get_workload(w.id) is not None
        assert eng.get_workload(w.id).workload_name == "batch-1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_workload("nonexistent") is None


# ---------------------------------------------------------------------------
# list_workloads
# ---------------------------------------------------------------------------


class TestListWorkloads:
    def test_list_all(self):
        eng = _engine()
        eng.register_workload(workload_name="a")
        eng.register_workload(workload_name="b")
        assert len(eng.list_workloads()) == 2

    def test_filter_by_priority(self):
        eng = _engine()
        eng.register_workload(workload_name="a", priority=JobPriority.HIGH)
        eng.register_workload(workload_name="b", priority=JobPriority.LOW)
        results = eng.list_workloads(priority=JobPriority.HIGH)
        assert len(results) == 1
        assert results[0].workload_name == "a"

    def test_filter_by_strategy(self):
        eng = _engine()
        eng.register_workload(workload_name="a", strategy=ScheduleStrategy.OFF_PEAK)
        eng.register_workload(workload_name="b", strategy=ScheduleStrategy.BALANCED)
        results = eng.list_workloads(strategy=ScheduleStrategy.OFF_PEAK)
        assert len(results) == 1
        assert results[0].workload_name == "a"


# ---------------------------------------------------------------------------
# update_workload_schedule
# ---------------------------------------------------------------------------


class TestUpdateWorkloadSchedule:
    def test_success(self):
        eng = _engine()
        w = eng.register_workload(workload_name="job", scheduled_start=1000.0)
        result = eng.update_workload_schedule(
            w.id,
            scheduled_start=2000.0,
            duration_seconds=1800,
            strategy=ScheduleStrategy.OFF_PEAK,
        )
        assert result is True
        assert w.scheduled_start == 2000.0
        assert w.duration_seconds == 1800
        assert w.strategy == ScheduleStrategy.OFF_PEAK

    def test_not_found(self):
        eng = _engine()
        assert eng.update_workload_schedule("bad-id", scheduled_start=999.0) is False


# ---------------------------------------------------------------------------
# detect_conflicts
# ---------------------------------------------------------------------------


class TestDetectConflicts:
    def test_no_conflicts(self):
        eng = _engine(conflict_window_seconds=60)
        # Two workloads far apart — no overlap
        eng.register_workload(
            workload_name="a",
            scheduled_start=1000.0,
            duration_seconds=100,
        )
        eng.register_workload(
            workload_name="b",
            scheduled_start=5000.0,
            duration_seconds=100,
        )
        conflicts = eng.detect_conflicts()
        assert len(conflicts) == 0

    def test_with_overlapping_workloads(self):
        eng = _engine(conflict_window_seconds=60)
        # Two workloads that overlap directly
        eng.register_workload(
            workload_name="a",
            scheduled_start=1000.0,
            duration_seconds=600,
        )
        eng.register_workload(
            workload_name="b",
            scheduled_start=1200.0,
            duration_seconds=600,
        )
        conflicts = eng.detect_conflicts()
        assert len(conflicts) >= 1
        assert conflicts[0].overlap_seconds > 0


# ---------------------------------------------------------------------------
# analyze_peak_windows
# ---------------------------------------------------------------------------


class TestAnalyzePeakWindows:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_peak_windows()
        assert result["windows"] == []
        assert result["peak_window"] is None

    def test_with_data(self):
        eng = _engine()
        base = time.time()
        eng.register_workload(workload_name="a", scheduled_start=base, duration_seconds=1800)
        eng.register_workload(workload_name="b", scheduled_start=base + 600, duration_seconds=1800)
        result = eng.analyze_peak_windows(window_hours=1)
        assert result["peak_window"] is not None
        assert result["peak_window"]["workload_count"] >= 1


# ---------------------------------------------------------------------------
# recommend_schedule_shifts
# ---------------------------------------------------------------------------


class TestRecommendScheduleShifts:
    def test_no_shifts_needed(self):
        eng = _engine()
        # Only high-priority workloads — nothing to shift
        base = time.time()
        eng.register_workload(
            workload_name="critical-job",
            priority=JobPriority.CRITICAL,
            scheduled_start=base,
            duration_seconds=3600,
        )
        shifts = eng.recommend_schedule_shifts()
        assert len(shifts) == 0

    def test_with_low_priority_to_shift(self):
        eng = _engine()
        base = time.time()
        # A high-priority workload creating a peak
        eng.register_workload(
            workload_name="critical-job",
            priority=JobPriority.CRITICAL,
            scheduled_start=base,
            duration_seconds=3600,
        )
        # A low-priority workload overlapping with the peak
        eng.register_workload(
            workload_name="background-cleanup",
            priority=JobPriority.LOW,
            scheduled_start=base + 600,
            duration_seconds=1800,
        )
        shifts = eng.recommend_schedule_shifts()
        assert len(shifts) >= 1
        assert shifts[0]["priority"] == "low"
        assert "contention" in shifts[0]["reason"].lower()


# ---------------------------------------------------------------------------
# estimate_cost_savings
# ---------------------------------------------------------------------------


class TestEstimateCostSavings:
    def test_empty(self):
        eng = _engine()
        result = eng.estimate_cost_savings()
        assert result["total_estimated_cost"] == 0.0
        assert result["potential_savings"] == 0.0
        assert result["movable_workload_count"] == 0

    def test_with_savings(self):
        eng = _engine()
        # A low-priority balanced workload that can move to off-peak
        eng.register_workload(
            workload_name="reports",
            priority=JobPriority.LOW,
            strategy=ScheduleStrategy.BALANCED,
            estimated_cost=100.0,
        )
        # A high-priority workload that should NOT be moved
        eng.register_workload(
            workload_name="realtime-ingest",
            priority=JobPriority.HIGH,
            strategy=ScheduleStrategy.PERFORMANCE_OPTIMIZED,
            estimated_cost=200.0,
        )
        result = eng.estimate_cost_savings()
        assert result["total_estimated_cost"] == 300.0
        assert result["movable_workload_count"] == 1
        assert result["potential_savings"] == 30.0  # 100 * 0.3
        assert result["savings_percentage"] == 10.0  # 30 / 300 * 100


# ---------------------------------------------------------------------------
# generate_optimization_report
# ---------------------------------------------------------------------------


class TestGenerateOptimizationReport:
    def test_basic_report(self):
        eng = _engine()
        base = time.time()
        eng.register_workload(
            workload_name="etl",
            priority=JobPriority.HIGH,
            strategy=ScheduleStrategy.BALANCED,
            scheduled_start=base,
            duration_seconds=3600,
            estimated_cost=50.0,
        )
        eng.register_workload(
            workload_name="backup",
            priority=JobPriority.LOW,
            strategy=ScheduleStrategy.OFF_PEAK,
            scheduled_start=base + 1800,
            duration_seconds=3600,
            estimated_cost=20.0,
        )
        report = eng.generate_optimization_report()
        assert report.total_workloads == 2
        assert report.total_estimated_cost == 70.0
        assert ScheduleStrategy.BALANCED.value in report.strategy_breakdown


# ---------------------------------------------------------------------------
# delete_workload
# ---------------------------------------------------------------------------


class TestDeleteWorkload:
    def test_success(self):
        eng = _engine()
        w = eng.register_workload(workload_name="deletable")
        assert eng.delete_workload(w.id) is True
        assert eng.get_workload(w.id) is None
        assert len(eng._workloads) == 0

    def test_not_found(self):
        eng = _engine()
        assert eng.delete_workload("bad-id") is False


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_both_lists(self):
        eng = _engine()
        base = time.time()
        eng.register_workload(
            workload_name="a",
            scheduled_start=base,
            duration_seconds=600,
        )
        eng.register_workload(
            workload_name="b",
            scheduled_start=base + 100,
            duration_seconds=600,
        )
        eng.detect_conflicts()
        assert len(eng._workloads) > 0
        assert len(eng._conflicts) > 0
        eng.clear_data()
        assert len(eng._workloads) == 0
        assert len(eng._conflicts) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_workloads"] == 0
        assert stats["total_conflicts"] == 0
        assert stats["unique_workload_names"] == 0
        assert stats["priorities"] == []
        assert stats["strategies"] == []

    def test_populated(self):
        eng = _engine()
        eng.register_workload(
            workload_name="etl",
            priority=JobPriority.HIGH,
            strategy=ScheduleStrategy.BALANCED,
        )
        eng.register_workload(
            workload_name="backup",
            priority=JobPriority.LOW,
            strategy=ScheduleStrategy.OFF_PEAK,
        )
        stats = eng.get_stats()
        assert stats["total_workloads"] == 2
        assert stats["unique_workload_names"] == 2
        assert "high" in stats["priorities"]
        assert "low" in stats["priorities"]
        assert "balanced" in stats["strategies"]
        assert "off_peak" in stats["strategies"]
