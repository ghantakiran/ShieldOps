"""Tests for shieldops.analytics.sre_toil_intelligence — SreToilIntelligence."""

from __future__ import annotations

from shieldops.analytics.sre_toil_intelligence import (
    AutomationFeasibility,
    EffortLevel,
    SreToilIntelligence,
    ToilCategory,
    ToilRecord,
)


def _engine(**kw) -> SreToilIntelligence:
    return SreToilIntelligence(**kw)


class TestEnums:
    def test_toil_category(self):
        assert ToilCategory.MANUAL_REMEDIATION == "manual_remediation"

    def test_automation_feasibility(self):
        assert AutomationFeasibility.FULLY_AUTOMATABLE == "fully_automatable"

    def test_effort_level(self):
        assert EffortLevel.LOW == "low"


class TestModels:
    def test_record_defaults(self):
        r = ToilRecord()
        assert r.id
        assert r.created_at > 0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(
            task_name="restart pods",
            toil_category=ToilCategory.MANUAL_REMEDIATION,
            time_spent_minutes=30.0,
            frequency_per_week=5.0,
        )
        assert rec.task_name == "restart pods"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(task_name=f"task-{i}")
        assert len(eng._records) == 3


class TestROI:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            task_name="restart pods",
            time_spent_minutes=30.0,
            frequency_per_week=5.0,
            automation_cost_hours=8.0,
        )
        result = eng.compute_roi("restart pods")
        assert isinstance(result, dict)


class TestPrioritize:
    def test_basic(self):
        eng = _engine()
        eng.add_record(task_name="task-a", time_spent_minutes=60.0, frequency_per_week=10.0)
        eng.add_record(task_name="task-b", time_spent_minutes=5.0, frequency_per_week=1.0)
        result = eng.prioritize_elimination()
        assert isinstance(result, list)


class TestToilBudget:
    def test_basic(self):
        eng = _engine()
        eng.add_record(task_name="task-a", time_spent_minutes=120.0, frequency_per_week=5.0)
        result = eng.compute_toil_budget()
        assert isinstance(result, dict)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(task_name="restart", service="api")
        result = eng.process("restart")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(task_name="task-a")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(task_name="task-a")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(task_name="task-a")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
