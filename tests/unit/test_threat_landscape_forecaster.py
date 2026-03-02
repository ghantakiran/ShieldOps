"""Tests for shieldops.analytics.threat_landscape_forecaster — ThreatLandscapeForecaster."""

from __future__ import annotations

from shieldops.analytics.threat_landscape_forecaster import (
    ForecastAnalysis,
    ForecastConfidence,
    ForecastHorizon,
    ForecastRecord,
    ForecastReport,
    ThreatLandscapeForecaster,
    ThreatTrend,
)


def _engine(**kw) -> ThreatLandscapeForecaster:
    return ThreatLandscapeForecaster(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_forecasthorizon_val1(self):
        assert ForecastHorizon.SHORT_TERM == "short_term"

    def test_forecasthorizon_val2(self):
        assert ForecastHorizon.MEDIUM_TERM == "medium_term"

    def test_forecasthorizon_val3(self):
        assert ForecastHorizon.LONG_TERM == "long_term"

    def test_forecasthorizon_val4(self):
        assert ForecastHorizon.STRATEGIC == "strategic"

    def test_forecasthorizon_val5(self):
        assert ForecastHorizon.TACTICAL == "tactical"

    def test_forecastconfidence_val1(self):
        assert ForecastConfidence.HIGH == "high"

    def test_forecastconfidence_val2(self):
        assert ForecastConfidence.MEDIUM == "medium"

    def test_forecastconfidence_val3(self):
        assert ForecastConfidence.LOW == "low"

    def test_forecastconfidence_val4(self):
        assert ForecastConfidence.SPECULATIVE == "speculative"

    def test_forecastconfidence_val5(self):
        assert ForecastConfidence.UNCERTAIN == "uncertain"

    def test_threattrend_val1(self):
        assert ThreatTrend.ESCALATING == "escalating"

    def test_threattrend_val2(self):
        assert ThreatTrend.STABLE == "stable"

    def test_threattrend_val3(self):
        assert ThreatTrend.DECLINING == "declining"

    def test_threattrend_val4(self):
        assert ThreatTrend.EMERGING == "emerging"

    def test_threattrend_val5(self):
        assert ThreatTrend.CYCLICAL == "cyclical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = ForecastRecord()
        assert r.id
        assert r.forecast_name == ""
        assert r.forecast_horizon == ForecastHorizon.SHORT_TERM
        assert r.forecast_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ForecastAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ForecastReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_forecast_score == 0.0
        assert r.by_horizon == {}
        assert r.by_confidence == {}
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
        r = eng.record_forecast(
            forecast_name="test",
            forecast_horizon=ForecastHorizon.MEDIUM_TERM,
            forecast_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.forecast_name == "test"
        assert r.forecast_horizon == ForecastHorizon.MEDIUM_TERM
        assert r.forecast_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_forecast(forecast_name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_forecast(forecast_name="test")
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
        eng.record_forecast(forecast_name="a")
        eng.record_forecast(forecast_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_forecast(forecast_name="a", forecast_horizon=ForecastHorizon.SHORT_TERM)
        eng.record_forecast(forecast_name="b", forecast_horizon=ForecastHorizon.MEDIUM_TERM)
        results = eng.list_records(forecast_horizon=ForecastHorizon.SHORT_TERM)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_forecast(forecast_name="a", forecast_confidence=ForecastConfidence.HIGH)
        eng.record_forecast(forecast_name="b", forecast_confidence=ForecastConfidence.MEDIUM)
        results = eng.list_records(forecast_confidence=ForecastConfidence.HIGH)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_forecast(forecast_name="a", team="sec")
        eng.record_forecast(forecast_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_forecast(forecast_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            forecast_name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(forecast_name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_forecast(
            forecast_name="a",
            forecast_horizon=ForecastHorizon.SHORT_TERM,
            forecast_score=90.0,
        )
        eng.record_forecast(
            forecast_name="b",
            forecast_horizon=ForecastHorizon.SHORT_TERM,
            forecast_score=70.0,
        )
        result = eng.analyze_horizon_distribution()
        assert "short_term" in result
        assert result["short_term"]["count"] == 2
        assert result["short_term"]["avg_forecast_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_horizon_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_forecast(forecast_name="a", forecast_score=60.0)
        eng.record_forecast(forecast_name="b", forecast_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["forecast_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_forecast(forecast_name="a", forecast_score=50.0)
        eng.record_forecast(forecast_name="b", forecast_score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["forecast_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_forecast(forecast_name="a", service="auth-svc", forecast_score=90.0)
        eng.record_forecast(forecast_name="b", service="api-gw", forecast_score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_forecast_score"] == 50.0

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
            eng.add_analysis(forecast_name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(forecast_name="t1", analysis_score=20.0)
        eng.add_analysis(forecast_name="t2", analysis_score=20.0)
        eng.add_analysis(forecast_name="t3", analysis_score=80.0)
        eng.add_analysis(forecast_name="t4", analysis_score=80.0)
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
        eng.record_forecast(
            forecast_name="test",
            forecast_horizon=ForecastHorizon.MEDIUM_TERM,
            forecast_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ForecastReport)
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
        eng.record_forecast(forecast_name="test")
        eng.add_analysis(forecast_name="test")
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
        assert stats["horizon_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_forecast(
            forecast_name="test",
            forecast_horizon=ForecastHorizon.SHORT_TERM,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "short_term" in stats["horizon_distribution"]
