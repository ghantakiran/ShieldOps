"""Tests for shieldops.security.detection_coverage_analyzer — DetectionCoverageAnalyzer."""

from __future__ import annotations

from shieldops.security.detection_coverage_analyzer import (
    CoverageAnalysis,
    CoverageArea,
    CoverageLevel,
    CoverageRecord,
    CoverageReport,
    DetectionCoverageAnalyzer,
    DetectionFramework,
)


def _engine(**kw) -> DetectionCoverageAnalyzer:
    return DetectionCoverageAnalyzer(**kw)


class TestEnums:
    def test_coveragearea_val1(self):
        assert CoverageArea.NETWORK == "network"

    def test_coveragearea_val2(self):
        assert CoverageArea.ENDPOINT == "endpoint"

    def test_coveragearea_val3(self):
        assert CoverageArea.CLOUD == "cloud"

    def test_coveragearea_val4(self):
        assert CoverageArea.IDENTITY == "identity"

    def test_coveragearea_val5(self):
        assert CoverageArea.APPLICATION == "application"

    def test_coveragelevel_val1(self):
        assert CoverageLevel.COMPREHENSIVE == "comprehensive"

    def test_coveragelevel_val2(self):
        assert CoverageLevel.SUBSTANTIAL == "substantial"

    def test_coveragelevel_val3(self):
        assert CoverageLevel.MODERATE == "moderate"

    def test_coveragelevel_val4(self):
        assert CoverageLevel.BASIC == "basic"

    def test_coveragelevel_val5(self):
        assert CoverageLevel.NONE == "none"

    def test_detectionframework_val1(self):
        assert DetectionFramework.MITRE_ATTACK == "mitre_attack"

    def test_detectionframework_val2(self):
        assert DetectionFramework.KILL_CHAIN == "kill_chain"

    def test_detectionframework_val3(self):
        assert DetectionFramework.DIAMOND_MODEL == "diamond_model"

    def test_detectionframework_val4(self):
        assert DetectionFramework.NIST == "nist"

    def test_detectionframework_val5(self):
        assert DetectionFramework.CUSTOM == "custom"


class TestModels:
    def test_record_defaults(self):
        r = CoverageRecord()
        assert r.id
        assert r.area_name == ""

    def test_analysis_defaults(self):
        a = CoverageAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = CoverageReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_coverage(
            area_name="test",
            coverage_area=CoverageArea.ENDPOINT,
            coverage_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.area_name == "test"
        assert r.coverage_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_coverage(area_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_coverage(area_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_coverage(area_name="a")
        eng.record_coverage(area_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_coverage(area_name="a", coverage_area=CoverageArea.NETWORK)
        eng.record_coverage(area_name="b", coverage_area=CoverageArea.ENDPOINT)
        assert len(eng.list_records(coverage_area=CoverageArea.NETWORK)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_coverage(area_name="a", coverage_level=CoverageLevel.COMPREHENSIVE)
        eng.record_coverage(area_name="b", coverage_level=CoverageLevel.SUBSTANTIAL)
        assert len(eng.list_records(coverage_level=CoverageLevel.COMPREHENSIVE)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_coverage(area_name="a", team="sec")
        eng.record_coverage(area_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_coverage(area_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            area_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(area_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_coverage(area_name="a", coverage_area=CoverageArea.NETWORK, coverage_score=90.0)
        eng.record_coverage(area_name="b", coverage_area=CoverageArea.NETWORK, coverage_score=70.0)
        result = eng.analyze_distribution()
        assert CoverageArea.NETWORK.value in result
        assert result[CoverageArea.NETWORK.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_coverage(area_name="a", coverage_score=60.0)
        eng.record_coverage(area_name="b", coverage_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_coverage(area_name="a", coverage_score=50.0)
        eng.record_coverage(area_name="b", coverage_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["coverage_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_coverage(area_name="a", service="auth", coverage_score=90.0)
        eng.record_coverage(area_name="b", service="api", coverage_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(area_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(area_name="a", analysis_score=20.0)
        eng.add_analysis(area_name="b", analysis_score=20.0)
        eng.add_analysis(area_name="c", analysis_score=80.0)
        eng.add_analysis(area_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_coverage(area_name="test", coverage_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_coverage(area_name="test")
        eng.add_analysis(area_name="test")
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
        eng.record_coverage(area_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
