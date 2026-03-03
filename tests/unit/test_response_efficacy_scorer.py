"""Tests for shieldops.security.response_efficacy_scorer — ResponseEfficacyScorer."""

from __future__ import annotations

from shieldops.security.response_efficacy_scorer import (
    EfficacyAnalysis,
    EfficacyGrade,
    EfficacyMetric,
    EfficacyRecord,
    EfficacyReport,
    EfficacyTrend,
    ResponseEfficacyScorer,
)


def _engine(**kw) -> ResponseEfficacyScorer:
    return ResponseEfficacyScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_efficacymetric_val1(self):
        assert EfficacyMetric.CONTAINMENT_SPEED == "containment_speed"

    def test_efficacymetric_val2(self):
        assert EfficacyMetric.ERADICATION_COMPLETENESS == "eradication_completeness"

    def test_efficacymetric_val3(self):
        assert EfficacyMetric.RECOVERY_TIME == "recovery_time"

    def test_efficacymetric_val4(self):
        assert EfficacyMetric.FALSE_POSITIVE_RATE == "false_positive_rate"

    def test_efficacymetric_val5(self):
        assert EfficacyMetric.RECURRENCE_RATE == "recurrence_rate"

    def test_efficacygrade_val1(self):
        assert EfficacyGrade.EXCELLENT == "excellent"

    def test_efficacygrade_val2(self):
        assert EfficacyGrade.GOOD == "good"

    def test_efficacygrade_val3(self):
        assert EfficacyGrade.ACCEPTABLE == "acceptable"

    def test_efficacygrade_val4(self):
        assert EfficacyGrade.POOR == "poor"

    def test_efficacygrade_val5(self):
        assert EfficacyGrade.FAILING == "failing"

    def test_efficacytrend_val1(self):
        assert EfficacyTrend.IMPROVING == "improving"

    def test_efficacytrend_val2(self):
        assert EfficacyTrend.STABLE == "stable"

    def test_efficacytrend_val3(self):
        assert EfficacyTrend.DEGRADING == "degrading"

    def test_efficacytrend_val4(self):
        assert EfficacyTrend.VOLATILE == "volatile"

    def test_efficacytrend_val5(self):
        assert EfficacyTrend.INSUFFICIENT_DATA == "insufficient_data"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = EfficacyRecord()
        assert r.id
        assert r.name == ""
        assert r.efficacy_metric == EfficacyMetric.CONTAINMENT_SPEED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = EfficacyAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = EfficacyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_metric == {}
        assert r.by_grade == {}
        assert r.by_trend == {}
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
        r = eng.record_efficacy(
            name="test",
            efficacy_metric=EfficacyMetric.ERADICATION_COMPLETENESS,
            score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.name == "test"
        assert r.efficacy_metric == EfficacyMetric.ERADICATION_COMPLETENESS
        assert r.score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_efficacy(name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_efficacy(name="test")
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
        eng.record_efficacy(name="a")
        eng.record_efficacy(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_efficacy(name="a", efficacy_metric=EfficacyMetric.CONTAINMENT_SPEED)
        eng.record_efficacy(name="b", efficacy_metric=EfficacyMetric.ERADICATION_COMPLETENESS)
        results = eng.list_records(efficacy_metric=EfficacyMetric.CONTAINMENT_SPEED)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_efficacy(name="a", efficacy_grade=EfficacyGrade.EXCELLENT)
        eng.record_efficacy(name="b", efficacy_grade=EfficacyGrade.GOOD)
        results = eng.list_records(efficacy_grade=EfficacyGrade.EXCELLENT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_efficacy(name="a", team="sec")
        eng.record_efficacy(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_efficacy(name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_efficacy(
            name="a",
            efficacy_metric=EfficacyMetric.CONTAINMENT_SPEED,
            score=90.0,
        )
        eng.record_efficacy(
            name="b",
            efficacy_metric=EfficacyMetric.CONTAINMENT_SPEED,
            score=70.0,
        )
        result = eng.analyze_metric_distribution()
        assert "containment_speed" in result
        assert result["containment_speed"]["count"] == 2
        assert result["containment_speed"]["avg_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_metric_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(score_threshold=80.0)
        eng.record_efficacy(name="a", score=60.0)
        eng.record_efficacy(name="b", score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(score_threshold=80.0)
        eng.record_efficacy(name="a", score=50.0)
        eng.record_efficacy(name="b", score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_efficacy(name="a", service="auth-svc", score=90.0)
        eng.record_efficacy(name="b", service="api-gw", score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_score"] == 50.0

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
            eng.add_analysis(name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="t1", analysis_score=20.0)
        eng.add_analysis(name="t2", analysis_score=20.0)
        eng.add_analysis(name="t3", analysis_score=80.0)
        eng.add_analysis(name="t4", analysis_score=80.0)
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
        eng = _engine(score_threshold=80.0)
        eng.record_efficacy(
            name="test",
            efficacy_metric=EfficacyMetric.ERADICATION_COMPLETENESS,
            score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, EfficacyReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy range" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_efficacy(name="test")
        eng.add_analysis(name="test")
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
        assert stats["metric_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_efficacy(
            name="test",
            efficacy_metric=EfficacyMetric.CONTAINMENT_SPEED,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "containment_speed" in stats["metric_distribution"]
