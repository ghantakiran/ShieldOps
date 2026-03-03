"""Tests for shieldops.security.api_exposure_analyzer — APIExposureAnalyzer."""

from __future__ import annotations

from shieldops.security.api_exposure_analyzer import (
    APIExposureAnalysis,
    APIExposureAnalyzer,
    APIExposureRecord,
    APIExposureReport,
    APIRisk,
    APIType,
    ExposureLevel,
)


def _engine(**kw) -> APIExposureAnalyzer:
    return APIExposureAnalyzer(**kw)


class TestEnums:
    def test_apitype_val1(self):
        assert APIType.REST == "rest"

    def test_apitype_val2(self):
        assert APIType.GRAPHQL == "graphql"

    def test_apitype_val3(self):
        assert APIType.GRPC == "grpc"

    def test_apitype_val4(self):
        assert APIType.WEBSOCKET == "websocket"

    def test_apitype_val5(self):
        assert APIType.SOAP == "soap"

    def test_exposurelevel_val1(self):
        assert ExposureLevel.PUBLIC == "public"

    def test_exposurelevel_val2(self):
        assert ExposureLevel.PARTNER == "partner"

    def test_exposurelevel_val3(self):
        assert ExposureLevel.INTERNAL == "internal"

    def test_exposurelevel_val4(self):
        assert ExposureLevel.DEPRECATED == "deprecated"

    def test_exposurelevel_val5(self):
        assert ExposureLevel.SHADOW == "shadow"

    def test_apirisk_val1(self):
        assert APIRisk.CRITICAL == "critical"

    def test_apirisk_val2(self):
        assert APIRisk.HIGH == "high"

    def test_apirisk_val3(self):
        assert APIRisk.MEDIUM == "medium"

    def test_apirisk_val4(self):
        assert APIRisk.LOW == "low"

    def test_apirisk_val5(self):
        assert APIRisk.MINIMAL == "minimal"


class TestModels:
    def test_record_defaults(self):
        r = APIExposureRecord()
        assert r.id
        assert r.endpoint_name == ""

    def test_analysis_defaults(self):
        a = APIExposureAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = APIExposureReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_exposure(
            endpoint_name="test",
            api_type=APIType.GRAPHQL,
            risk_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.endpoint_name == "test"
        assert r.risk_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_exposure(endpoint_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_exposure(endpoint_name="test")
        assert eng.get_exposure(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_exposure("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_exposure(endpoint_name="a")
        eng.record_exposure(endpoint_name="b")
        assert len(eng.list_exposures()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_exposure(endpoint_name="a", api_type=APIType.REST)
        eng.record_exposure(endpoint_name="b", api_type=APIType.GRAPHQL)
        assert len(eng.list_exposures(api_type=APIType.REST)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_exposure(endpoint_name="a", exposure_level=ExposureLevel.PUBLIC)
        eng.record_exposure(endpoint_name="b", exposure_level=ExposureLevel.PARTNER)
        assert len(eng.list_exposures(exposure_level=ExposureLevel.PUBLIC)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_exposure(endpoint_name="a", team="sec")
        eng.record_exposure(endpoint_name="b", team="ops")
        assert len(eng.list_exposures(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_exposure(endpoint_name=f"t-{i}")
        assert len(eng.list_exposures(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            endpoint_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(endpoint_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_exposure(endpoint_name="a", api_type=APIType.REST, risk_score=90.0)
        eng.record_exposure(endpoint_name="b", api_type=APIType.REST, risk_score=70.0)
        result = eng.analyze_distribution()
        assert APIType.REST.value in result
        assert result[APIType.REST.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_exposure(endpoint_name="a", risk_score=60.0)
        eng.record_exposure(endpoint_name="b", risk_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_exposure(endpoint_name="a", risk_score=50.0)
        eng.record_exposure(endpoint_name="b", risk_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_exposure(endpoint_name="a", service="auth", risk_score=90.0)
        eng.record_exposure(endpoint_name="b", service="api", risk_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(endpoint_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(endpoint_name="a", analysis_score=20.0)
        eng.add_analysis(endpoint_name="b", analysis_score=20.0)
        eng.add_analysis(endpoint_name="c", analysis_score=80.0)
        eng.add_analysis(endpoint_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_exposure(endpoint_name="test", risk_score=50.0)
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
        eng.record_exposure(endpoint_name="test")
        eng.add_analysis(endpoint_name="test")
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
        eng.record_exposure(endpoint_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
