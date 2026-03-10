"""Tests for IncidentLearningSynthesizer."""

from __future__ import annotations

from shieldops.incidents.incident_learning_synthesizer import (
    ApplicabilityScope,
    IncidentLearningSynthesizer,
    KnowledgeSource,
    LearningType,
)


def _engine(**kw) -> IncidentLearningSynthesizer:
    return IncidentLearningSynthesizer(**kw)


class TestEnums:
    def test_learning_type_values(self):
        assert LearningType.PATTERN == "pattern"
        assert LearningType.ANTIPATTERN == "antipattern"
        assert LearningType.BEST_PRACTICE == "best_practice"
        assert LearningType.FAILURE_MODE == "failure_mode"

    def test_knowledge_source_values(self):
        assert KnowledgeSource.POSTMORTEM == "postmortem"
        assert KnowledgeSource.RUNBOOK == "runbook"
        assert KnowledgeSource.ALERT_HISTORY == "alert_history"
        assert KnowledgeSource.CHANGE_LOG == "change_log"

    def test_applicability_scope_values(self):
        assert ApplicabilityScope.SERVICE == "service"
        assert ApplicabilityScope.TEAM == "team"
        assert ApplicabilityScope.ORGANIZATION == "organization"
        assert ApplicabilityScope.INDUSTRY == "industry"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            name="learn-001",
            learning_type=LearningType.BEST_PRACTICE,
            knowledge_source=KnowledgeSource.POSTMORTEM,
            score=80.0,
            service="api",
            team="sre",
        )
        assert r.name == "learn-001"
        assert r.learning_type == LearningType.BEST_PRACTICE
        assert r.score == 80.0

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


class TestExtractLearnings:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            learning_type=LearningType.PATTERN,
            score=80.0,
        )
        eng.add_record(
            name="b",
            learning_type=LearningType.ANTIPATTERN,
            score=30.0,
        )
        results = eng.extract_learnings()
        assert len(results) == 2
        assert results[0]["avg_score"] > results[1]["avg_score"]

    def test_empty(self):
        eng = _engine()
        assert eng.extract_learnings() == []


class TestSynthesizeRecommendations:
    def test_with_antipatterns(self):
        eng = _engine(threshold=80.0)
        eng.add_record(
            name="a",
            learning_type=LearningType.ANTIPATTERN,
            applicability_scope=ApplicabilityScope.TEAM,
            score=30.0,
        )
        results = eng.synthesize_recommendations()
        assert len(results) >= 1
        assert results[0]["antipattern_count"] == 1

    def test_empty(self):
        eng = _engine()
        assert eng.synthesize_recommendations() == []


class TestComputeLearningCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            service="api",
            learning_type=LearningType.PATTERN,
            knowledge_source=KnowledgeSource.POSTMORTEM,
        )
        result = eng.compute_learning_coverage()
        assert result["total_services"] == 1
        cov = result["service_coverage"]
        assert len(cov) == 1
        assert cov[0]["type_coverage_pct"] == 25.0

    def test_empty(self):
        eng = _engine()
        result = eng.compute_learning_coverage()
        assert result["total_services"] == 0
