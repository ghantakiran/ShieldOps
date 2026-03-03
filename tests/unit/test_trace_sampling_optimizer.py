"""Tests for shieldops.observability.trace_sampling_optimizer — TraceSamplingOptimizer."""

from __future__ import annotations

from shieldops.observability.trace_sampling_optimizer import (
    SamplingAnalysis,
    SamplingEfficiency,
    SamplingRecord,
    SamplingStrategy,
    SamplingTarget,
    TraceSamplingOptimizer,
    TraceSamplingReport,
)


def _engine(**kw) -> TraceSamplingOptimizer:
    return TraceSamplingOptimizer(**kw)


class TestEnums:
    def test_sampling_strategy_head_based(self):
        assert SamplingStrategy.HEAD_BASED == "head_based"

    def test_sampling_strategy_tail_based(self):
        assert SamplingStrategy.TAIL_BASED == "tail_based"

    def test_sampling_strategy_priority(self):
        assert SamplingStrategy.PRIORITY == "priority"

    def test_sampling_strategy_adaptive(self):
        assert SamplingStrategy.ADAPTIVE == "adaptive"

    def test_sampling_strategy_hybrid(self):
        assert SamplingStrategy.HYBRID == "hybrid"

    def test_sampling_target_cost_reduction(self):
        assert SamplingTarget.COST_REDUCTION == "cost_reduction"

    def test_sampling_target_error_capture(self):
        assert SamplingTarget.ERROR_CAPTURE == "error_capture"

    def test_sampling_target_latency_focus(self):
        assert SamplingTarget.LATENCY_FOCUS == "latency_focus"

    def test_sampling_target_coverage(self):
        assert SamplingTarget.COVERAGE == "coverage"

    def test_sampling_target_balanced(self):
        assert SamplingTarget.BALANCED == "balanced"

    def test_sampling_efficiency_optimal(self):
        assert SamplingEfficiency.OPTIMAL == "optimal"

    def test_sampling_efficiency_acceptable(self):
        assert SamplingEfficiency.ACCEPTABLE == "acceptable"

    def test_sampling_efficiency_inefficient(self):
        assert SamplingEfficiency.INEFFICIENT == "inefficient"

    def test_sampling_efficiency_wasteful(self):
        assert SamplingEfficiency.WASTEFUL == "wasteful"

    def test_sampling_efficiency_unknown(self):
        assert SamplingEfficiency.UNKNOWN == "unknown"


class TestModels:
    def test_record_defaults(self):
        r = SamplingRecord()
        assert r.id
        assert r.name == ""
        assert r.sampling_strategy == SamplingStrategy.HEAD_BASED
        assert r.sampling_target == SamplingTarget.COST_REDUCTION
        assert r.sampling_efficiency == SamplingEfficiency.UNKNOWN
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = SamplingAnalysis()
        assert a.id
        assert a.name == ""
        assert a.sampling_strategy == SamplingStrategy.HEAD_BASED
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = TraceSamplingReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_sampling_strategy == {}
        assert r.by_sampling_target == {}
        assert r.by_sampling_efficiency == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            sampling_strategy=SamplingStrategy.HEAD_BASED,
            sampling_target=SamplingTarget.ERROR_CAPTURE,
            sampling_efficiency=SamplingEfficiency.OPTIMAL,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.sampling_strategy == SamplingStrategy.HEAD_BASED
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

    def test_filter_by_sampling_strategy(self):
        eng = _engine()
        eng.record_entry(name="a", sampling_strategy=SamplingStrategy.HEAD_BASED)
        eng.record_entry(name="b", sampling_strategy=SamplingStrategy.TAIL_BASED)
        assert len(eng.list_records(sampling_strategy=SamplingStrategy.HEAD_BASED)) == 1

    def test_filter_by_sampling_target(self):
        eng = _engine()
        eng.record_entry(name="a", sampling_target=SamplingTarget.COST_REDUCTION)
        eng.record_entry(name="b", sampling_target=SamplingTarget.ERROR_CAPTURE)
        assert len(eng.list_records(sampling_target=SamplingTarget.COST_REDUCTION)) == 1

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
        eng.record_entry(name="a", sampling_strategy=SamplingStrategy.TAIL_BASED, score=90.0)
        eng.record_entry(name="b", sampling_strategy=SamplingStrategy.TAIL_BASED, score=70.0)
        result = eng.analyze_distribution()
        assert "tail_based" in result
        assert result["tail_based"]["count"] == 2

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
