"""Tests for IterationSchedulerEngine."""

from __future__ import annotations

from shieldops.operations.iteration_scheduler_engine import (
    IterationSchedulerEngine,
    IterationStatus,
    ScheduleStrategy,
    TimeConstraint,
)


def _engine(**kw) -> IterationSchedulerEngine:
    return IterationSchedulerEngine(**kw)


class TestEnums:
    def test_schedule_strategy_values(self):
        assert isinstance(ScheduleStrategy.ROUND_ROBIN, str)
        assert isinstance(ScheduleStrategy.PRIORITY, str)
        assert isinstance(ScheduleStrategy.DEADLINE, str)
        assert isinstance(ScheduleStrategy.ADAPTIVE, str)

    def test_iteration_status_values(self):
        assert isinstance(IterationStatus.QUEUED, str)
        assert isinstance(IterationStatus.RUNNING, str)
        assert isinstance(IterationStatus.COMPLETED, str)
        assert isinstance(IterationStatus.CANCELLED, str)

    def test_time_constraint_values(self):
        assert isinstance(TimeConstraint.MINUTES_5, str)
        assert isinstance(TimeConstraint.MINUTES_15, str)
        assert isinstance(TimeConstraint.HOUR_1, str)
        assert isinstance(TimeConstraint.UNLIMITED, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="iter-001",
            strategy=ScheduleStrategy.PRIORITY,
            duration_seconds=120.0,
        )
        assert r.name == "iter-001"
        assert r.duration_seconds == 120.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(name=f"it-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="it-001")
        result = eng.process(r.id)
        assert "analysis_id" in result

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="it-001")
        report = eng.generate_report()
        assert report.total_records > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        assert "total_records" in eng.get_stats()

    def test_populated_count(self):
        eng = _engine()
        eng.record_item(name="i1")
        eng.record_item(name="i2")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(name="i1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestScheduleNextIteration:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            name="it-001",
            service="svc-1",
            status=IterationStatus.QUEUED,
        )
        result = eng.schedule_next_iteration("svc-1")
        assert result["next_iteration"] == "it-001"

    def test_empty(self):
        eng = _engine()
        result = eng.schedule_next_iteration("svc-1")
        assert result["status"] == "no_data"


class TestComputeThroughput:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            name="it-001",
            service="svc-1",
            status=IterationStatus.COMPLETED,
            duration_seconds=60.0,
        )
        result = eng.compute_throughput("svc-1")
        assert result["throughput_per_hour"] == 60.0

    def test_empty(self):
        eng = _engine()
        result = eng.compute_throughput("svc-1")
        assert result["status"] == "no_data"


class TestDetectSchedulingBottlenecks:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            name="it-001",
            service="svc-1",
            status=IterationStatus.QUEUED,
        )
        result = eng.detect_scheduling_bottlenecks("svc-1")
        assert "bottleneck" in result

    def test_empty(self):
        eng = _engine()
        result = eng.detect_scheduling_bottlenecks("svc-1")
        assert result["status"] == "no_data"
