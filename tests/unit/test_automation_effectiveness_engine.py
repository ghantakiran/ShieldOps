"""Tests for AutomationEffectivenessEngine."""

from __future__ import annotations

from shieldops.analytics.automation_effectiveness_engine import (
    AutomationEffectivenessEngine,
    AutomationType,
    EffectivenessMetric,
    MaturityLevel,
)


def _engine(**kw) -> AutomationEffectivenessEngine:
    return AutomationEffectivenessEngine(**kw)


class TestEnums:
    def test_automation_type_values(self):
        assert AutomationType.RUNBOOK == "runbook"
        assert AutomationType.POLICY == "policy"
        assert AutomationType.WORKFLOW == "workflow"
        assert AutomationType.SELF_HEALING == "self_healing"

    def test_effectiveness_metric_values(self):
        assert EffectivenessMetric.SUCCESS_RATE == "success_rate"
        assert EffectivenessMetric.TIME_SAVED == "time_saved"
        assert EffectivenessMetric.ERROR_REDUCTION == "error_reduction"
        assert EffectivenessMetric.COST_SAVINGS == "cost_savings"

    def test_maturity_level_values(self):
        assert MaturityLevel.MANUAL == "manual"
        assert MaturityLevel.SCRIPTED == "scripted"
        assert MaturityLevel.AUTOMATED == "automated"
        assert MaturityLevel.AUTONOMOUS == "autonomous"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            name="auto-001",
            automation_type=AutomationType.WORKFLOW,
            maturity_level=MaturityLevel.AUTOMATED,
            score=85.0,
            service="ci",
            team="platform",
        )
        assert r.name == "auto-001"
        assert r.automation_type == AutomationType.WORKFLOW
        assert r.score == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="test", score=40.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.add_record(name="t", service="a", team="b")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.add_record(name="test")
        eng.add_analysis(name="test")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestComputeAutomationRoi:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            automation_type=AutomationType.RUNBOOK,
            score=80.0,
        )
        eng.add_record(
            name="b",
            automation_type=AutomationType.SELF_HEALING,
            score=80.0,
        )
        result = eng.compute_automation_roi()
        roi = result["roi_by_type"]
        assert roi["runbook"]["roi_ratio"] > roi["self_healing"]["roi_ratio"]

    def test_empty(self):
        eng = _engine()
        result = eng.compute_automation_roi()
        assert result["total_automations"] == 0


class TestIdentifyAutomationGaps:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            service="web",
            automation_type=AutomationType.RUNBOOK,
            score=80.0,
        )
        gaps = eng.identify_automation_gaps()
        assert len(gaps) == 1
        assert len(gaps[0]["missing_types"]) == 3

    def test_empty(self):
        eng = _engine()
        assert eng.identify_automation_gaps() == []


class TestBenchmarkEffectiveness:
    def test_with_data(self):
        eng = _engine(threshold=50.0)
        eng.add_record(
            name="a",
            maturity_level=MaturityLevel.AUTONOMOUS,
            score=90.0,
        )
        eng.add_record(
            name="b",
            maturity_level=MaturityLevel.MANUAL,
            score=30.0,
        )
        result = eng.benchmark_effectiveness()
        bm = result["benchmarks"]
        assert bm["autonomous"]["meets_threshold"] is True
        assert bm["manual"]["meets_threshold"] is False

    def test_empty(self):
        eng = _engine()
        result = eng.benchmark_effectiveness()
        assert result["total_records"] == 0
