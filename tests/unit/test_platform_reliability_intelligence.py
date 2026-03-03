"""Tests for shieldops.sla.platform_reliability_intelligence — PlatformReliabilityIntelligence."""

from __future__ import annotations

from shieldops.sla.platform_reliability_intelligence import (
    PlatformReliabilityIntelligence,
    PlatformReliabilityIntelligenceAnalysis,
    PlatformReliabilityIntelligenceRecord,
    PlatformReliabilityIntelligenceReport,
    ReliabilityDimension,
    ReliabilityScore,
    ReliabilityTarget,
)


def _engine(**kw) -> PlatformReliabilityIntelligence:
    return PlatformReliabilityIntelligence(**kw)


class TestEnums:
    def test_reliability_dimension_first(self):
        assert ReliabilityDimension.AVAILABILITY == "availability"

    def test_reliability_dimension_second(self):
        assert ReliabilityDimension.LATENCY == "latency"

    def test_reliability_dimension_third(self):
        assert ReliabilityDimension.DURABILITY == "durability"

    def test_reliability_dimension_fourth(self):
        assert ReliabilityDimension.CONSISTENCY == "consistency"

    def test_reliability_dimension_fifth(self):
        assert ReliabilityDimension.SCALABILITY == "scalability"

    def test_reliability_score_first(self):
        assert ReliabilityScore.EXCELLENT == "excellent"

    def test_reliability_score_second(self):
        assert ReliabilityScore.GOOD == "good"

    def test_reliability_score_third(self):
        assert ReliabilityScore.ACCEPTABLE == "acceptable"

    def test_reliability_score_fourth(self):
        assert ReliabilityScore.POOR == "poor"

    def test_reliability_score_fifth(self):
        assert ReliabilityScore.CRITICAL == "critical"

    def test_reliability_target_first(self):
        assert ReliabilityTarget.FIVE_NINES == "five_nines"

    def test_reliability_target_second(self):
        assert ReliabilityTarget.FOUR_NINES == "four_nines"

    def test_reliability_target_third(self):
        assert ReliabilityTarget.THREE_NINES == "three_nines"

    def test_reliability_target_fourth(self):
        assert ReliabilityTarget.TWO_NINES == "two_nines"

    def test_reliability_target_fifth(self):
        assert ReliabilityTarget.CUSTOM == "custom"


class TestModels:
    def test_record_defaults(self):
        r = PlatformReliabilityIntelligenceRecord()
        assert r.id
        assert r.name == ""
        assert r.reliability_dimension == ReliabilityDimension.AVAILABILITY
        assert r.reliability_score == ReliabilityScore.EXCELLENT
        assert r.reliability_target == ReliabilityTarget.FIVE_NINES
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = PlatformReliabilityIntelligenceAnalysis()
        assert a.id
        assert a.name == ""
        assert a.reliability_dimension == ReliabilityDimension.AVAILABILITY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PlatformReliabilityIntelligenceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_reliability_dimension == {}
        assert r.by_reliability_score == {}
        assert r.by_reliability_target == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            reliability_dimension=ReliabilityDimension.AVAILABILITY,
            reliability_score=ReliabilityScore.GOOD,
            reliability_target=ReliabilityTarget.THREE_NINES,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.reliability_dimension == ReliabilityDimension.AVAILABILITY
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

    def test_filter_by_reliability_dimension(self):
        eng = _engine()
        eng.record_item(name="a", reliability_dimension=ReliabilityDimension.LATENCY)
        eng.record_item(name="b", reliability_dimension=ReliabilityDimension.AVAILABILITY)
        assert len(eng.list_records(reliability_dimension=ReliabilityDimension.LATENCY)) == 1

    def test_filter_by_reliability_score(self):
        eng = _engine()
        eng.record_item(name="a", reliability_score=ReliabilityScore.EXCELLENT)
        eng.record_item(name="b", reliability_score=ReliabilityScore.GOOD)
        assert len(eng.list_records(reliability_score=ReliabilityScore.EXCELLENT)) == 1

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
        eng.record_item(name="a", reliability_dimension=ReliabilityDimension.LATENCY, score=90.0)
        eng.record_item(name="b", reliability_dimension=ReliabilityDimension.LATENCY, score=70.0)
        result = eng.analyze_distribution()
        assert "latency" in result
        assert result["latency"]["count"] == 2

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
