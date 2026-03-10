"""Tests for ResilienceExperimentEngine."""

from __future__ import annotations

from shieldops.operations.resilience_experiment_engine import (
    ExperimentCategory,
    ExperimentStatus,
    ResilienceExperimentEngine,
    ResilienceOutcome,
)


def _engine(**kw) -> ResilienceExperimentEngine:
    return ResilienceExperimentEngine(**kw)


class TestEnums:
    def test_experiment_category_values(self):
        assert ExperimentCategory.LATENCY == "latency"
        assert ExperimentCategory.FAILURE == "failure"

    def test_experiment_status_values(self):
        assert ExperimentStatus.PLANNED == "planned"
        assert ExperimentStatus.RUNNING == "running"

    def test_resilience_outcome_values(self):
        assert ResilienceOutcome.PASSED == "passed"
        assert ResilienceOutcome.FAILED == "failed"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(name="exp-1", score=85.0)
        assert r.name == "exp-1"
        assert r.score == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"exp-{i}")
        assert len(eng._records) == 3


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="test", score=40.0)
        report = eng.generate_report()
        assert report.total_records >= 1

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
        eng.record_item(name="a", team="t1")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.record_item(name="x")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(name="a", score=70.0)
        result = eng.analyze_distribution()
        assert isinstance(result, dict)


class TestIdentifyGaps:
    def test_returns_list(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=30.0)
        result = eng.identify_gaps()
        assert isinstance(result, list)


class TestDetectTrends:
    def test_insufficient(self):
        eng = _engine()
        r = eng.detect_trends()
        assert r["trend"] == "insufficient_data"
