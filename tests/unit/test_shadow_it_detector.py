"""Tests for shieldops.security.shadow_it_detector — ShadowITDetector."""

from __future__ import annotations

from shieldops.security.shadow_it_detector import (
    DetectionMethod,
    RiskLevel,
    ShadowCategory,
    ShadowITAnalysis,
    ShadowITDetector,
    ShadowITRecord,
    ShadowITReport,
)


def _engine(**kw) -> ShadowITDetector:
    return ShadowITDetector(**kw)


class TestEnums:
    def test_shadowcategory_val1(self):
        assert ShadowCategory.CLOUD_SERVICE == "cloud_service"

    def test_shadowcategory_val2(self):
        assert ShadowCategory.SAAS_APP == "saas_app"

    def test_shadowcategory_val3(self):
        assert ShadowCategory.PERSONAL_DEVICE == "personal_device"

    def test_shadowcategory_val4(self):
        assert ShadowCategory.UNAUTHORIZED_API == "unauthorized_api"

    def test_shadowcategory_val5(self):
        assert ShadowCategory.ROGUE_SERVER == "rogue_server"

    def test_risklevel_val1(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_risklevel_val2(self):
        assert RiskLevel.HIGH == "high"

    def test_risklevel_val3(self):
        assert RiskLevel.MEDIUM == "medium"

    def test_risklevel_val4(self):
        assert RiskLevel.LOW == "low"

    def test_risklevel_val5(self):
        assert RiskLevel.ACCEPTABLE == "acceptable"

    def test_detectionmethod_val1(self):
        assert DetectionMethod.NETWORK_ANALYSIS == "network_analysis"

    def test_detectionmethod_val2(self):
        assert DetectionMethod.DNS_MONITORING == "dns_monitoring"

    def test_detectionmethod_val3(self):
        assert DetectionMethod.CLOUD_AUDIT == "cloud_audit"

    def test_detectionmethod_val4(self):
        assert DetectionMethod.ENDPOINT_SCAN == "endpoint_scan"

    def test_detectionmethod_val5(self):
        assert DetectionMethod.LOG_ANALYSIS == "log_analysis"


class TestModels:
    def test_record_defaults(self):
        r = ShadowITRecord()
        assert r.id
        assert r.resource_name == ""

    def test_analysis_defaults(self):
        a = ShadowITAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = ShadowITReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_detection(
            resource_name="test",
            shadow_category=ShadowCategory.SAAS_APP,
            risk_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.resource_name == "test"
        assert r.risk_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_detection(resource_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_detection(resource_name="test")
        assert eng.get_detection(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_detection("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_detection(resource_name="a")
        eng.record_detection(resource_name="b")
        assert len(eng.list_detections()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_detection(resource_name="a", shadow_category=ShadowCategory.CLOUD_SERVICE)
        eng.record_detection(resource_name="b", shadow_category=ShadowCategory.SAAS_APP)
        assert len(eng.list_detections(shadow_category=ShadowCategory.CLOUD_SERVICE)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_detection(resource_name="a", risk_level=RiskLevel.CRITICAL)
        eng.record_detection(resource_name="b", risk_level=RiskLevel.HIGH)
        assert len(eng.list_detections(risk_level=RiskLevel.CRITICAL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_detection(resource_name="a", team="sec")
        eng.record_detection(resource_name="b", team="ops")
        assert len(eng.list_detections(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_detection(resource_name=f"t-{i}")
        assert len(eng.list_detections(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            resource_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(resource_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_detection(
            resource_name="a", shadow_category=ShadowCategory.CLOUD_SERVICE, risk_score=90.0
        )
        eng.record_detection(
            resource_name="b", shadow_category=ShadowCategory.CLOUD_SERVICE, risk_score=70.0
        )
        result = eng.analyze_distribution()
        assert ShadowCategory.CLOUD_SERVICE.value in result
        assert result[ShadowCategory.CLOUD_SERVICE.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_detection(resource_name="a", risk_score=60.0)
        eng.record_detection(resource_name="b", risk_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_detection(resource_name="a", risk_score=50.0)
        eng.record_detection(resource_name="b", risk_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_detection(resource_name="a", service="auth", risk_score=90.0)
        eng.record_detection(resource_name="b", service="api", risk_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(resource_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(resource_name="a", analysis_score=20.0)
        eng.add_analysis(resource_name="b", analysis_score=20.0)
        eng.add_analysis(resource_name="c", analysis_score=80.0)
        eng.add_analysis(resource_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_detection(resource_name="test", risk_score=50.0)
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
        eng.record_detection(resource_name="test")
        eng.add_analysis(resource_name="test")
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
        eng.record_detection(resource_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
