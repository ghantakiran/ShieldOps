"""Tests for shieldops.security.intel_gap_analyzer — IntelGapAnalyzer."""

from __future__ import annotations

from shieldops.security.intel_gap_analyzer import (
    GapAnalysis,
    GapAnalysisReport,
    GapCategory,
    GapRecord,
    GapSeverity,
    GapStatus,
    IntelGapAnalyzer,
)


def _engine(**kw) -> IntelGapAnalyzer:
    return IntelGapAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_gapcategory_val1(self):
        assert GapCategory.COLLECTION == "collection"

    def test_gapcategory_val2(self):
        assert GapCategory.ANALYSIS == "analysis"

    def test_gapcategory_val3(self):
        assert GapCategory.DISSEMINATION == "dissemination"

    def test_gapcategory_val4(self):
        assert GapCategory.COVERAGE == "coverage"

    def test_gapcategory_val5(self):
        assert GapCategory.TIMELINESS == "timeliness"

    def test_gapseverity_val1(self):
        assert GapSeverity.CRITICAL == "critical"

    def test_gapseverity_val2(self):
        assert GapSeverity.SIGNIFICANT == "significant"

    def test_gapseverity_val3(self):
        assert GapSeverity.MODERATE == "moderate"

    def test_gapseverity_val4(self):
        assert GapSeverity.MINOR == "minor"

    def test_gapseverity_val5(self):
        assert GapSeverity.NEGLIGIBLE == "negligible"

    def test_gapstatus_val1(self):
        assert GapStatus.IDENTIFIED == "identified"

    def test_gapstatus_val2(self):
        assert GapStatus.ASSESSED == "assessed"

    def test_gapstatus_val3(self):
        assert GapStatus.MITIGATING == "mitigating"

    def test_gapstatus_val4(self):
        assert GapStatus.RESOLVED == "resolved"

    def test_gapstatus_val5(self):
        assert GapStatus.ACCEPTED == "accepted"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = GapRecord()
        assert r.id
        assert r.gap_name == ""
        assert r.gap_category == GapCategory.COVERAGE
        assert r.coverage_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = GapAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = GapAnalysisReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_coverage_score == 0.0
        assert r.by_category == {}
        assert r.by_severity == {}
        assert r.by_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_gap(
            gap_name="test",
            gap_category=GapCategory.ANALYSIS,
            coverage_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.gap_name == "test"
        assert r.gap_category == GapCategory.ANALYSIS
        assert r.coverage_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_gap(gap_name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_gap(gap_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_gap(gap_name="a")
        eng.record_gap(gap_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_gap(gap_name="a", gap_category=GapCategory.COLLECTION)
        eng.record_gap(gap_name="b", gap_category=GapCategory.ANALYSIS)
        results = eng.list_records(gap_category=GapCategory.COLLECTION)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_gap(gap_name="a", gap_severity=GapSeverity.CRITICAL)
        eng.record_gap(gap_name="b", gap_severity=GapSeverity.SIGNIFICANT)
        results = eng.list_records(gap_severity=GapSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_gap(gap_name="a", team="sec")
        eng.record_gap(gap_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_gap(gap_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            gap_name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(gap_name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_gap(
            gap_name="a",
            gap_category=GapCategory.COLLECTION,
            coverage_score=90.0,
        )
        eng.record_gap(
            gap_name="b",
            gap_category=GapCategory.COLLECTION,
            coverage_score=70.0,
        )
        result = eng.analyze_category_distribution()
        assert "collection" in result
        assert result["collection"]["count"] == 2
        assert result["collection"]["avg_coverage_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_category_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_gap(gap_name="a", coverage_score=60.0)
        eng.record_gap(gap_name="b", coverage_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["gap_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_gap(gap_name="a", coverage_score=50.0)
        eng.record_gap(gap_name="b", coverage_score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["coverage_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_gap(gap_name="a", service="auth-svc", coverage_score=90.0)
        eng.record_gap(gap_name="b", service="api-gw", coverage_score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_coverage_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(gap_name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(gap_name="t1", analysis_score=20.0)
        eng.add_analysis(gap_name="t2", analysis_score=20.0)
        eng.add_analysis(gap_name="t3", analysis_score=80.0)
        eng.add_analysis(gap_name="t4", analysis_score=80.0)
        result = eng.detect_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_gap(
            gap_name="test",
            gap_category=GapCategory.ANALYSIS,
            coverage_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, GapAnalysisReport)
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


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_gap(gap_name="test")
        eng.add_analysis(gap_name="test")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_gap(
            gap_name="test",
            gap_category=GapCategory.COLLECTION,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "collection" in stats["category_distribution"]
