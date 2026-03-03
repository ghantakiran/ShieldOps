"""Tests for shieldops.analytics.innovation_readiness_scorer — InnovationReadinessScorer."""

from __future__ import annotations

from shieldops.analytics.innovation_readiness_scorer import (
    InnovationBarrier,
    InnovationReadinessScorer,
    InnovationReadinessScorerAnalysis,
    InnovationReadinessScorerRecord,
    InnovationReadinessScorerReport,
    ReadinessDimension,
    ReadinessLevel,
)


def _engine(**kw) -> InnovationReadinessScorer:
    return InnovationReadinessScorer(**kw)


class TestEnums:
    def test_readiness_dimension_first(self):
        assert ReadinessDimension.TECHNOLOGY == "technology"

    def test_readiness_dimension_second(self):
        assert ReadinessDimension.PROCESS == "process"

    def test_readiness_dimension_third(self):
        assert ReadinessDimension.PEOPLE == "people"

    def test_readiness_dimension_fourth(self):
        assert ReadinessDimension.CULTURE == "culture"

    def test_readiness_dimension_fifth(self):
        assert ReadinessDimension.GOVERNANCE == "governance"

    def test_readiness_level_first(self):
        assert ReadinessLevel.PIONEER == "pioneer"

    def test_readiness_level_second(self):
        assert ReadinessLevel.EARLY_ADOPTER == "early_adopter"

    def test_readiness_level_third(self):
        assert ReadinessLevel.MAINSTREAM == "mainstream"

    def test_readiness_level_fourth(self):
        assert ReadinessLevel.LATE_ADOPTER == "late_adopter"

    def test_readiness_level_fifth(self):
        assert ReadinessLevel.LAGGARD == "laggard"

    def test_innovation_barrier_first(self):
        assert InnovationBarrier.TECHNICAL == "technical"

    def test_innovation_barrier_second(self):
        assert InnovationBarrier.ORGANIZATIONAL == "organizational"

    def test_innovation_barrier_third(self):
        assert InnovationBarrier.FINANCIAL == "financial"

    def test_innovation_barrier_fourth(self):
        assert InnovationBarrier.CULTURAL == "cultural"

    def test_innovation_barrier_fifth(self):
        assert InnovationBarrier.REGULATORY == "regulatory"


class TestModels:
    def test_record_defaults(self):
        r = InnovationReadinessScorerRecord()
        assert r.id
        assert r.name == ""
        assert r.readiness_dimension == ReadinessDimension.TECHNOLOGY
        assert r.readiness_level == ReadinessLevel.PIONEER
        assert r.innovation_barrier == InnovationBarrier.TECHNICAL
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = InnovationReadinessScorerAnalysis()
        assert a.id
        assert a.name == ""
        assert a.readiness_dimension == ReadinessDimension.TECHNOLOGY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = InnovationReadinessScorerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_readiness_dimension == {}
        assert r.by_readiness_level == {}
        assert r.by_innovation_barrier == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            readiness_dimension=ReadinessDimension.TECHNOLOGY,
            readiness_level=ReadinessLevel.EARLY_ADOPTER,
            innovation_barrier=InnovationBarrier.FINANCIAL,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.readiness_dimension == ReadinessDimension.TECHNOLOGY
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_readiness_dimension(self):
        eng = _engine()
        eng.record_item(name="a", readiness_dimension=ReadinessDimension.PROCESS)
        eng.record_item(name="b", readiness_dimension=ReadinessDimension.TECHNOLOGY)
        assert len(eng.list_records(readiness_dimension=ReadinessDimension.PROCESS)) == 1

    def test_filter_by_readiness_level(self):
        eng = _engine()
        eng.record_item(name="a", readiness_level=ReadinessLevel.PIONEER)
        eng.record_item(name="b", readiness_level=ReadinessLevel.EARLY_ADOPTER)
        assert len(eng.list_records(readiness_level=ReadinessLevel.PIONEER)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
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
        eng.record_item(name="a", readiness_dimension=ReadinessDimension.PROCESS, score=90.0)
        eng.record_item(name="b", readiness_dimension=ReadinessDimension.PROCESS, score=70.0)
        result = eng.analyze_distribution()
        assert "process" in result
        assert result["process"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(name="a", service="auth", score=90.0)
        eng.record_item(name="b", service="api", score=50.0)
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
        eng.record_item(name="test", score=50.0)
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
        eng.record_item(name="test")
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
        eng.record_item(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
