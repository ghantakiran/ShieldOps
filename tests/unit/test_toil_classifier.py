"""Tests for shieldops.operations.toil_classifier — OperationalToilClassifier."""

from __future__ import annotations

from shieldops.operations.toil_classifier import (
    AutomationPotential,
    OperationalToilClassifier,
    ToilCategory,
    ToilClassification,
    ToilClassifierReport,
    ToilImpact,
    ToilRecord,
)


def _engine(**kw) -> OperationalToilClassifier:
    return OperationalToilClassifier(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ToilCategory (5)
    def test_category_manual_intervention(self):
        assert ToilCategory.MANUAL_INTERVENTION == "manual_intervention"

    def test_category_repetitive_task(self):
        assert ToilCategory.REPETITIVE_TASK == "repetitive_task"

    def test_category_interrupt_driven(self):
        assert ToilCategory.INTERRUPT_DRIVEN == "interrupt_driven"

    def test_category_scaling_limitation(self):
        assert ToilCategory.SCALING_LIMITATION == "scaling_limitation"

    def test_category_process_overhead(self):
        assert ToilCategory.PROCESS_OVERHEAD == "process_overhead"

    # ToilImpact (5)
    def test_impact_critical(self):
        assert ToilImpact.CRITICAL == "critical"

    def test_impact_high(self):
        assert ToilImpact.HIGH == "high"

    def test_impact_moderate(self):
        assert ToilImpact.MODERATE == "moderate"

    def test_impact_low(self):
        assert ToilImpact.LOW == "low"

    def test_impact_minimal(self):
        assert ToilImpact.MINIMAL == "minimal"

    # AutomationPotential (5)
    def test_potential_fully_automatable(self):
        assert AutomationPotential.FULLY_AUTOMATABLE == "fully_automatable"

    def test_potential_mostly_automatable(self):
        assert AutomationPotential.MOSTLY_AUTOMATABLE == "mostly_automatable"

    def test_potential_partially_automatable(self):
        assert AutomationPotential.PARTIALLY_AUTOMATABLE == "partially_automatable"

    def test_potential_difficult_to_automate(self):
        assert AutomationPotential.DIFFICULT_TO_AUTOMATE == "difficult_to_automate"

    def test_potential_not_automatable(self):
        assert AutomationPotential.NOT_AUTOMATABLE == "not_automatable"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_toil_record_defaults(self):
        r = ToilRecord()
        assert r.id
        assert r.task_name == ""
        assert r.category == ToilCategory.MANUAL_INTERVENTION
        assert r.impact == ToilImpact.MODERATE
        assert r.automation_potential == AutomationPotential.PARTIALLY_AUTOMATABLE
        assert r.hours_per_week == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_toil_classification_defaults(self):
        r = ToilClassification()
        assert r.id
        assert r.task_name == ""
        assert r.category == ToilCategory.MANUAL_INTERVENTION
        assert r.impact == ToilImpact.MODERATE
        assert r.automation_potential == AutomationPotential.PARTIALLY_AUTOMATABLE
        assert r.estimated_savings_hours == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_toil_classifier_report_defaults(self):
        r = ToilClassifierReport()
        assert r.total_toil_records == 0
        assert r.total_classifications == 0
        assert r.total_hours_per_week == 0.0
        assert r.by_category == {}
        assert r.by_impact == {}
        assert r.high_impact_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_toil
# -------------------------------------------------------------------


class TestRecordToil:
    def test_basic(self):
        eng = _engine()
        r = eng.record_toil(
            "deploy-restart",
            category=ToilCategory.MANUAL_INTERVENTION,
            impact=ToilImpact.HIGH,
        )
        assert r.task_name == "deploy-restart"
        assert r.category == ToilCategory.MANUAL_INTERVENTION

    def test_with_automation_potential(self):
        eng = _engine()
        r = eng.record_toil(
            "log-review",
            automation_potential=AutomationPotential.FULLY_AUTOMATABLE,
        )
        assert r.automation_potential == AutomationPotential.FULLY_AUTOMATABLE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_toil(f"task-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_toil
# -------------------------------------------------------------------


class TestGetToil:
    def test_found(self):
        eng = _engine()
        r = eng.record_toil("task-a")
        assert eng.get_toil(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_toil("nonexistent") is None


# -------------------------------------------------------------------
# list_toils
# -------------------------------------------------------------------


class TestListToils:
    def test_list_all(self):
        eng = _engine()
        eng.record_toil("task-a")
        eng.record_toil("task-b")
        assert len(eng.list_toils()) == 2

    def test_filter_by_task_name(self):
        eng = _engine()
        eng.record_toil("task-a")
        eng.record_toil("task-b")
        results = eng.list_toils(task_name="task-a")
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_toil("task-a", category=ToilCategory.REPETITIVE_TASK)
        eng.record_toil("task-b", category=ToilCategory.INTERRUPT_DRIVEN)
        results = eng.list_toils(category=ToilCategory.REPETITIVE_TASK)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_classification
# -------------------------------------------------------------------


class TestAddClassification:
    def test_basic(self):
        eng = _engine()
        c = eng.add_classification(
            "deploy-restart",
            category=ToilCategory.MANUAL_INTERVENTION,
            impact=ToilImpact.HIGH,
            automation_potential=AutomationPotential.FULLY_AUTOMATABLE,
            estimated_savings_hours=10.0,
        )
        assert c.task_name == "deploy-restart"
        assert c.estimated_savings_hours == 10.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_classification(f"task-{i}")
        assert len(eng._classifications) == 2


# -------------------------------------------------------------------
# analyze_toil_by_category
# -------------------------------------------------------------------


class TestAnalyzeToilByCategory:
    def test_with_data(self):
        eng = _engine()
        eng.record_toil("task-a", impact=ToilImpact.HIGH, hours_per_week=10.0)
        eng.record_toil("task-a", impact=ToilImpact.LOW, hours_per_week=5.0)
        result = eng.analyze_toil_by_category("task-a")
        assert result["task_name"] == "task-a"
        assert result["record_count"] == 2
        assert result["total_hours_per_week"] == 15.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_toil_by_category("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_high_impact_toil
# -------------------------------------------------------------------


class TestIdentifyHighImpactToil:
    def test_with_high_impact(self):
        eng = _engine()
        eng.record_toil("task-a", impact=ToilImpact.CRITICAL)
        eng.record_toil("task-a", impact=ToilImpact.HIGH)
        eng.record_toil("task-b", impact=ToilImpact.MINIMAL)
        results = eng.identify_high_impact_toil()
        assert len(results) == 1
        assert results[0]["task_name"] == "task-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact_toil() == []


# -------------------------------------------------------------------
# rank_by_automation_potential
# -------------------------------------------------------------------


class TestRankByAutomationPotential:
    def test_with_data(self):
        eng = _engine()
        eng.record_toil("task-a", hours_per_week=20.0)
        eng.record_toil("task-a", hours_per_week=10.0)
        eng.record_toil("task-b", hours_per_week=5.0)
        results = eng.rank_by_automation_potential()
        assert results[0]["task_name"] == "task-a"
        assert results[0]["avg_hours_per_week"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_automation_potential() == []


# -------------------------------------------------------------------
# detect_toil_trends
# -------------------------------------------------------------------


class TestDetectToilTrends:
    def test_with_trends(self):
        eng = _engine(max_toil_hours_weekly=5.0)
        for _ in range(5):
            eng.record_toil("task-a", hours_per_week=10.0)
        eng.record_toil("task-b", hours_per_week=2.0)
        results = eng.detect_toil_trends()
        assert len(results) == 1
        assert results[0]["task_name"] == "task-a"
        assert results[0]["trend_detected"] is True

    def test_no_trends(self):
        eng = _engine(max_toil_hours_weekly=5.0)
        eng.record_toil("task-a", hours_per_week=10.0)
        assert eng.detect_toil_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(max_toil_hours_weekly=5.0)
        eng.record_toil("task-a", impact=ToilImpact.HIGH, hours_per_week=10.0)
        eng.record_toil("task-b", impact=ToilImpact.LOW, hours_per_week=2.0)
        eng.add_classification("task-a")
        report = eng.generate_report()
        assert report.total_toil_records == 2
        assert report.total_classifications == 1
        assert report.by_category != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_toil_records == 0
        assert "acceptable" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_toil("task-a")
        eng.add_classification("task-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._classifications) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_toil_records"] == 0
        assert stats["total_classifications"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_toil("task-a", category=ToilCategory.MANUAL_INTERVENTION)
        eng.record_toil("task-b", category=ToilCategory.REPETITIVE_TASK)
        eng.add_classification("task-a")
        stats = eng.get_stats()
        assert stats["total_toil_records"] == 2
        assert stats["total_classifications"] == 1
        assert stats["unique_tasks"] == 2
