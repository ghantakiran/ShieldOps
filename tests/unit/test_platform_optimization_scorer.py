"""Tests for shieldops.analytics.platform_optimization_scorer — PlatformOptimizationScorer."""

from __future__ import annotations

from shieldops.analytics.platform_optimization_scorer import (
    OptimizationDomain,
    OptimizationGrade,
    PlatformOptimizationReport,
    PlatformOptimizationScorer,
    PlatformScoreAnalysis,
    PlatformScoreRecord,
    ScoringSource,
)


def _engine(**kw) -> PlatformOptimizationScorer:
    return PlatformOptimizationScorer(**kw)


class TestEnums:
    def test_optimization_domain_reliability(self):
        assert OptimizationDomain.RELIABILITY == "reliability"

    def test_optimization_domain_performance(self):
        assert OptimizationDomain.PERFORMANCE == "performance"

    def test_optimization_domain_cost(self):
        assert OptimizationDomain.COST == "cost"

    def test_optimization_domain_security(self):
        assert OptimizationDomain.SECURITY == "security"

    def test_optimization_domain_scalability(self):
        assert OptimizationDomain.SCALABILITY == "scalability"

    def test_scoring_source_metric_analysis(self):
        assert ScoringSource.METRIC_ANALYSIS == "metric_analysis"

    def test_scoring_source_benchmark(self):
        assert ScoringSource.BENCHMARK == "benchmark"

    def test_scoring_source_best_practice(self):
        assert ScoringSource.BEST_PRACTICE == "best_practice"

    def test_scoring_source_peer_comparison(self):
        assert ScoringSource.PEER_COMPARISON == "peer_comparison"

    def test_scoring_source_custom(self):
        assert ScoringSource.CUSTOM == "custom"

    def test_optimization_grade_excellent(self):
        assert OptimizationGrade.EXCELLENT == "excellent"

    def test_optimization_grade_good(self):
        assert OptimizationGrade.GOOD == "good"

    def test_optimization_grade_fair(self):
        assert OptimizationGrade.FAIR == "fair"

    def test_optimization_grade_needs_work(self):
        assert OptimizationGrade.NEEDS_WORK == "needs_work"

    def test_optimization_grade_critical(self):
        assert OptimizationGrade.CRITICAL == "critical"


class TestModels:
    def test_record_defaults(self):
        r = PlatformScoreRecord()
        assert r.id
        assert r.name == ""
        assert r.optimization_domain == OptimizationDomain.RELIABILITY
        assert r.scoring_source == ScoringSource.METRIC_ANALYSIS
        assert r.optimization_grade == OptimizationGrade.CRITICAL
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = PlatformScoreAnalysis()
        assert a.id
        assert a.name == ""
        assert a.optimization_domain == OptimizationDomain.RELIABILITY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PlatformOptimizationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_optimization_domain == {}
        assert r.by_scoring_source == {}
        assert r.by_optimization_grade == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            optimization_domain=OptimizationDomain.RELIABILITY,
            scoring_source=ScoringSource.BENCHMARK,
            optimization_grade=OptimizationGrade.EXCELLENT,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.optimization_domain == OptimizationDomain.RELIABILITY
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_optimization_domain(self):
        eng = _engine()
        eng.record_entry(name="a", optimization_domain=OptimizationDomain.RELIABILITY)
        eng.record_entry(name="b", optimization_domain=OptimizationDomain.PERFORMANCE)
        assert len(eng.list_records(optimization_domain=OptimizationDomain.RELIABILITY)) == 1

    def test_filter_by_scoring_source(self):
        eng = _engine()
        eng.record_entry(name="a", scoring_source=ScoringSource.METRIC_ANALYSIS)
        eng.record_entry(name="b", scoring_source=ScoringSource.BENCHMARK)
        assert len(eng.list_records(scoring_source=ScoringSource.METRIC_ANALYSIS)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", optimization_domain=OptimizationDomain.PERFORMANCE, score=90.0)
        eng.record_entry(name="b", optimization_domain=OptimizationDomain.PERFORMANCE, score=70.0)
        result = eng.analyze_distribution()
        assert "performance" in result
        assert result["performance"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
