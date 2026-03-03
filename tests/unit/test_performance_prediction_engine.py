"""Tests for shieldops.analytics.performance_prediction_engine — PerformancePredictionEngine."""

from __future__ import annotations

from shieldops.analytics.performance_prediction_engine import (
    DegradationRisk,
    PerformanceMetric,
    PerformancePredictionEngine,
    PerformancePredictionEngineAnalysis,
    PerformancePredictionEngineRecord,
    PerformancePredictionEngineReport,
    PredictionWindow,
)


def _engine(**kw) -> PerformancePredictionEngine:
    return PerformancePredictionEngine(**kw)


class TestEnums:
    def test_performance_metric_first(self):
        assert PerformanceMetric.LATENCY_P50 == "latency_p50"

    def test_performance_metric_second(self):
        assert PerformanceMetric.LATENCY_P95 == "latency_p95"

    def test_performance_metric_third(self):
        assert PerformanceMetric.LATENCY_P99 == "latency_p99"

    def test_performance_metric_fourth(self):
        assert PerformanceMetric.THROUGHPUT == "throughput"

    def test_performance_metric_fifth(self):
        assert PerformanceMetric.ERROR_RATE == "error_rate"

    def test_prediction_window_first(self):
        assert PredictionWindow.NEXT_HOUR == "next_hour"

    def test_prediction_window_second(self):
        assert PredictionWindow.NEXT_DAY == "next_day"

    def test_prediction_window_third(self):
        assert PredictionWindow.NEXT_WEEK == "next_week"

    def test_prediction_window_fourth(self):
        assert PredictionWindow.NEXT_MONTH == "next_month"

    def test_prediction_window_fifth(self):
        assert PredictionWindow.NEXT_QUARTER == "next_quarter"

    def test_degradation_risk_first(self):
        assert DegradationRisk.CRITICAL == "critical"

    def test_degradation_risk_second(self):
        assert DegradationRisk.HIGH == "high"

    def test_degradation_risk_third(self):
        assert DegradationRisk.MODERATE == "moderate"

    def test_degradation_risk_fourth(self):
        assert DegradationRisk.LOW == "low"

    def test_degradation_risk_fifth(self):
        assert DegradationRisk.NONE == "none"


class TestModels:
    def test_record_defaults(self):
        r = PerformancePredictionEngineRecord()
        assert r.id
        assert r.name == ""
        assert r.performance_metric == PerformanceMetric.LATENCY_P50
        assert r.prediction_window == PredictionWindow.NEXT_HOUR
        assert r.degradation_risk == DegradationRisk.CRITICAL
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = PerformancePredictionEngineAnalysis()
        assert a.id
        assert a.name == ""
        assert a.performance_metric == PerformanceMetric.LATENCY_P50
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PerformancePredictionEngineReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_performance_metric == {}
        assert r.by_prediction_window == {}
        assert r.by_degradation_risk == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            performance_metric=PerformanceMetric.LATENCY_P50,
            prediction_window=PredictionWindow.NEXT_DAY,
            degradation_risk=DegradationRisk.MODERATE,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.performance_metric == PerformanceMetric.LATENCY_P50
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

    def test_filter_by_performance_metric(self):
        eng = _engine()
        eng.record_item(name="a", performance_metric=PerformanceMetric.LATENCY_P95)
        eng.record_item(name="b", performance_metric=PerformanceMetric.LATENCY_P50)
        assert len(eng.list_records(performance_metric=PerformanceMetric.LATENCY_P95)) == 1

    def test_filter_by_prediction_window(self):
        eng = _engine()
        eng.record_item(name="a", prediction_window=PredictionWindow.NEXT_HOUR)
        eng.record_item(name="b", prediction_window=PredictionWindow.NEXT_DAY)
        assert len(eng.list_records(prediction_window=PredictionWindow.NEXT_HOUR)) == 1

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
        eng.record_item(name="a", performance_metric=PerformanceMetric.LATENCY_P95, score=90.0)
        eng.record_item(name="b", performance_metric=PerformanceMetric.LATENCY_P95, score=70.0)
        result = eng.analyze_distribution()
        assert "latency_p95" in result
        assert result["latency_p95"]["count"] == 2

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
