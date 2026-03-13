"""Tests for AuditTimelineOptimizer."""

from __future__ import annotations

from shieldops.audit.audit_timeline_optimizer import (
    AuditTimelineOptimizer,
    TaskPhase,
    TaskPriority,
    TimelineStatus,
)


def _engine(**kw) -> AuditTimelineOptimizer:
    return AuditTimelineOptimizer(**kw)


class TestEnums:
    def test_task_phase_values(self):
        for v in TaskPhase:
            assert isinstance(v.value, str)

    def test_timeline_status_values(self):
        for v in TimelineStatus:
            assert isinstance(v.value, str)

    def test_task_priority_values(self):
        for v in TaskPriority:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(task_id="t1")
        assert r.task_id == "t1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(task_id=f"t-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(task_id="t1", duration_days=10.0, planned_days=8.0)
        a = eng.process(r.id)
        assert hasattr(a, "task_id")
        assert a.task_id == "t1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(task_id="t1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(task_id="t1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(task_id="t1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeOptimalTimeline:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(audit_id="a1", task_id="t1", duration_days=10.0, planned_days=8.0)
        result = eng.compute_optimal_timeline()
        assert len(result) == 1
        assert result[0]["audit_id"] == "a1"

    def test_empty(self):
        assert _engine().compute_optimal_timeline() == []


class TestDetectPreparationBottlenecks:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            task_id="t1",
            duration_days=15.0,
            planned_days=10.0,
            slack_days=0.0,
        )
        result = eng.detect_preparation_bottlenecks()
        assert len(result) == 1
        assert result[0]["overrun"] == 5.0

    def test_empty(self):
        assert _engine().detect_preparation_bottlenecks() == []


class TestRankAuditTasksByCriticalPath:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(task_id="t1", duration_days=10.0, planned_days=5.0, slack_days=0.0)
        eng.add_record(task_id="t2", duration_days=5.0, planned_days=10.0, slack_days=5.0)
        result = eng.rank_audit_tasks_by_critical_path()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_audit_tasks_by_critical_path() == []
