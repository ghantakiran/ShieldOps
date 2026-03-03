"""Tests for shieldops.analytics.resilience_score_calculator."""

from __future__ import annotations

from shieldops.analytics.resilience_score_calculator import (
    AssessmentScope,
    ResilienceAnalysis,
    ResilienceDimension,
    ResilienceScore,
    ResilienceScoreCalculator,
    ResilienceScoreReport,
    ScoreCategory,
)


def _engine(**kw) -> ResilienceScoreCalculator:
    return ResilienceScoreCalculator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_dimension_availability(self):
        assert ResilienceDimension.AVAILABILITY == "availability"

    def test_dimension_recoverability(self):
        assert ResilienceDimension.RECOVERABILITY == "recoverability"

    def test_dimension_scalability(self):
        assert ResilienceDimension.SCALABILITY == "scalability"

    def test_dimension_observability(self):
        assert ResilienceDimension.OBSERVABILITY == "observability"

    def test_dimension_redundancy(self):
        assert ResilienceDimension.REDUNDANCY == "redundancy"

    def test_category_excellent(self):
        assert ScoreCategory.EXCELLENT == "excellent"

    def test_category_good(self):
        assert ScoreCategory.GOOD == "good"

    def test_category_fair(self):
        assert ScoreCategory.FAIR == "fair"

    def test_category_poor(self):
        assert ScoreCategory.POOR == "poor"

    def test_category_critical(self):
        assert ScoreCategory.CRITICAL == "critical"

    def test_scope_service(self):
        assert AssessmentScope.SERVICE == "service"

    def test_scope_team(self):
        assert AssessmentScope.TEAM == "team"

    def test_scope_platform(self):
        assert AssessmentScope.PLATFORM == "platform"

    def test_scope_region(self):
        assert AssessmentScope.REGION == "region"

    def test_scope_global(self):
        assert AssessmentScope.GLOBAL == "global"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_resilience_score_defaults(self):
        r = ResilienceScore()
        assert r.id
        assert r.dimension == ResilienceDimension.AVAILABILITY
        assert r.category == ScoreCategory.GOOD
        assert r.scope == AssessmentScope.SERVICE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_resilience_analysis_defaults(self):
        a = ResilienceAnalysis()
        assert a.id
        assert a.dimension == ResilienceDimension.AVAILABILITY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_resilience_score_report_defaults(self):
        r = ResilienceScoreReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_dimension == {}
        assert r.by_category == {}
        assert r.by_scope == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self):
        eng = _engine()
        assert eng._max_records == 200000
        assert eng._threshold == 50.0
        assert eng._records == []
        assert eng._analyses == []

    def test_custom_max_records(self):
        eng = _engine(max_records=1000)
        assert eng._max_records == 1000

    def test_custom_threshold(self):
        eng = _engine(threshold=65.0)
        assert eng._threshold == 65.0


# ---------------------------------------------------------------------------
# record_score / get_score
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_record_basic(self):
        eng = _engine()
        r = eng.record_score(
            service="api-gw",
            dimension=ResilienceDimension.RECOVERABILITY,
            category=ScoreCategory.EXCELLENT,
            scope=AssessmentScope.PLATFORM,
            score=92.0,
            team="platform",
        )
        assert r.service == "api-gw"
        assert r.dimension == ResilienceDimension.RECOVERABILITY
        assert r.category == ScoreCategory.EXCELLENT
        assert r.scope == AssessmentScope.PLATFORM
        assert r.score == 92.0
        assert r.team == "platform"

    def test_record_stored(self):
        eng = _engine()
        eng.record_score(service="svc-a")
        assert len(eng._records) == 1

    def test_get_found(self):
        eng = _engine()
        r = eng.record_score(service="svc-a", score=75.0)
        result = eng.get_score(r.id)
        assert result is not None
        assert result.score == 75.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_score("nonexistent") is None


# ---------------------------------------------------------------------------
# list_scores
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_score(service="svc-a")
        eng.record_score(service="svc-b")
        assert len(eng.list_scores()) == 2

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_score(service="svc-a", dimension=ResilienceDimension.AVAILABILITY)
        eng.record_score(service="svc-b", dimension=ResilienceDimension.SCALABILITY)
        results = eng.list_scores(dimension=ResilienceDimension.AVAILABILITY)
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_score(service="svc-a", category=ScoreCategory.EXCELLENT)
        eng.record_score(service="svc-b", category=ScoreCategory.POOR)
        results = eng.list_scores(category=ScoreCategory.EXCELLENT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_score(service="svc-a", team="platform")
        eng.record_score(service="svc-b", team="security")
        assert len(eng.list_scores(team="platform")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_score(service=f"svc-{i}")
        assert len(eng.list_scores(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            dimension=ResilienceDimension.REDUNDANCY,
            analysis_score=55.0,
            threshold=50.0,
            breached=True,
            description="redundancy gap",
        )
        assert a.dimension == ResilienceDimension.REDUNDANCY
        assert a.analysis_score == 55.0
        assert a.breached is True

    def test_stored(self):
        eng = _engine()
        eng.add_analysis()
        assert len(eng._analyses) == 1

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _ in range(5):
            eng.add_analysis()
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_score(service="s1", dimension=ResilienceDimension.AVAILABILITY, score=80.0)
        eng.record_score(service="s2", dimension=ResilienceDimension.AVAILABILITY, score=60.0)
        result = eng.analyze_distribution()
        assert "availability" in result
        assert result["availability"]["count"] == 2
        assert result["availability"]["avg_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_score_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_score(service="svc-a", score=60.0)
        eng.record_score(service="svc-b", score=90.0)
        results = eng.identify_score_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_score(service="svc-a", score=50.0)
        eng.record_score(service="svc-b", score=30.0)
        results = eng.identify_score_gaps()
        assert results[0]["score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_score(service="svc-a", score=90.0)
        eng.record_score(service="svc-b", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "svc-b"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_score_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_score_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_score(
            service="svc-a",
            dimension=ResilienceDimension.SCALABILITY,
            category=ScoreCategory.FAIR,
            scope=AssessmentScope.TEAM,
            score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ResilienceScoreReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_score(service="svc-a")
        eng.add_analysis()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_score(
            service="svc-a",
            dimension=ResilienceDimension.AVAILABILITY,
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert "availability" in stats["dimension_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_score(service=f"svc-{i}")
        assert len(eng._records) == 3
