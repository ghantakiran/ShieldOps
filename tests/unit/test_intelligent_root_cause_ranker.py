"""Tests for IntelligentRootCauseRanker."""

from __future__ import annotations

from shieldops.analytics.intelligent_root_cause_ranker import (
    CauseCategory,
    ConfidenceLevel,
    IntelligentRootCauseRanker,
    RankingMethod,
)


def _engine(**kw) -> IntelligentRootCauseRanker:
    return IntelligentRootCauseRanker(**kw)


class TestEnums:
    def test_cause_category_values(self):
        assert CauseCategory.INFRASTRUCTURE == "infrastructure"
        assert CauseCategory.APPLICATION == "application"
        assert CauseCategory.CONFIGURATION == "configuration"
        assert CauseCategory.EXTERNAL == "external"

    def test_ranking_method_values(self):
        assert RankingMethod.BAYESIAN == "bayesian"
        assert RankingMethod.FREQUENCY == "frequency"
        assert RankingMethod.RECENCY == "recency"
        assert RankingMethod.IMPACT == "impact"

    def test_confidence_level_values(self):
        assert ConfidenceLevel.DEFINITIVE == "definitive"
        assert ConfidenceLevel.PROBABLE == "probable"
        assert ConfidenceLevel.POSSIBLE == "possible"
        assert ConfidenceLevel.SPECULATIVE == "speculative"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            name="cause-001",
            cause_category=CauseCategory.INFRASTRUCTURE,
            confidence_level=ConfidenceLevel.DEFINITIVE,
            score=95.0,
            service="db",
            team="sre",
        )
        assert r.name == "cause-001"
        assert r.cause_category == CauseCategory.INFRASTRUCTURE
        assert r.score == 95.0

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


class TestRankProbableCauses:
    def test_returns_sorted(self):
        eng = _engine()
        eng.add_record(
            name="high",
            confidence_level=ConfidenceLevel.DEFINITIVE,
            score=90.0,
        )
        eng.add_record(
            name="low",
            confidence_level=ConfidenceLevel.SPECULATIVE,
            score=90.0,
        )
        results = eng.rank_probable_causes()
        assert results[0]["name"] == "high"
        assert results[0]["ranked_score"] > results[1]["ranked_score"]

    def test_empty(self):
        eng = _engine()
        assert eng.rank_probable_causes() == []


class TestComputeCauseCorrelation:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            cause_category=CauseCategory.INFRASTRUCTURE,
            service="db",
            score=80.0,
        )
        eng.add_record(
            name="b",
            cause_category=CauseCategory.INFRASTRUCTURE,
            service="api",
            score=70.0,
        )
        result = eng.compute_cause_correlation()
        infra = result["correlations"]["infrastructure"]
        assert infra["affected_services"] == 2
        assert infra["occurrence_count"] == 2

    def test_empty(self):
        eng = _engine()
        result = eng.compute_cause_correlation()
        assert result["total_causes"] == 0


class TestDetectCascadingFailures:
    def test_with_cascade(self):
        eng = _engine()
        eng.add_record(
            name="a",
            service="db",
            cause_category=CauseCategory.INFRASTRUCTURE,
            score=50.0,
        )
        eng.add_record(
            name="b",
            service="db",
            cause_category=CauseCategory.APPLICATION,
            score=60.0,
        )
        results = eng.detect_cascading_failures()
        assert len(results) == 1
        assert results[0]["is_cascade"] is True

    def test_empty(self):
        eng = _engine()
        assert eng.detect_cascading_failures() == []
