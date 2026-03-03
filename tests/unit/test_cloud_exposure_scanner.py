"""Tests for shieldops.security.cloud_exposure_scanner — CloudExposureScanner."""

from __future__ import annotations

from shieldops.security.cloud_exposure_scanner import (
    CloudExposureAnalysis,
    CloudExposureRecord,
    CloudExposureReport,
    CloudExposureScanner,
    CloudProvider,
    ExposureCategory,
    RemediationStatus,
)


def _engine(**kw) -> CloudExposureScanner:
    return CloudExposureScanner(**kw)


class TestEnums:
    def test_cloudprovider_val1(self):
        assert CloudProvider.AWS == "aws"

    def test_cloudprovider_val2(self):
        assert CloudProvider.GCP == "gcp"

    def test_cloudprovider_val3(self):
        assert CloudProvider.AZURE == "azure"

    def test_cloudprovider_val4(self):
        assert CloudProvider.MULTI_CLOUD == "multi_cloud"

    def test_cloudprovider_val5(self):
        assert CloudProvider.PRIVATE == "private"

    def test_exposurecategory_val1(self):
        assert ExposureCategory.STORAGE_BUCKET == "storage_bucket"

    def test_exposurecategory_val2(self):
        assert ExposureCategory.DATABASE == "database"

    def test_exposurecategory_val3(self):
        assert ExposureCategory.API_GATEWAY == "api_gateway"

    def test_exposurecategory_val4(self):
        assert ExposureCategory.COMPUTE_INSTANCE == "compute_instance"

    def test_exposurecategory_val5(self):
        assert ExposureCategory.NETWORK == "network"

    def test_remediationstatus_val1(self):
        assert RemediationStatus.OPEN == "open"

    def test_remediationstatus_val2(self):
        assert RemediationStatus.IN_PROGRESS == "in_progress"

    def test_remediationstatus_val3(self):
        assert RemediationStatus.RESOLVED == "resolved"

    def test_remediationstatus_val4(self):
        assert RemediationStatus.ACCEPTED == "accepted"

    def test_remediationstatus_val5(self):
        assert RemediationStatus.DEFERRED == "deferred"


class TestModels:
    def test_record_defaults(self):
        r = CloudExposureRecord()
        assert r.id
        assert r.resource_name == ""

    def test_analysis_defaults(self):
        a = CloudExposureAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = CloudExposureReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_exposure(
            resource_name="test",
            cloud_provider=CloudProvider.GCP,
            risk_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.resource_name == "test"
        assert r.risk_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_exposure(resource_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_exposure(resource_name="test")
        assert eng.get_exposure(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_exposure("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_exposure(resource_name="a")
        eng.record_exposure(resource_name="b")
        assert len(eng.list_exposures()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_exposure(resource_name="a", cloud_provider=CloudProvider.AWS)
        eng.record_exposure(resource_name="b", cloud_provider=CloudProvider.GCP)
        assert len(eng.list_exposures(cloud_provider=CloudProvider.AWS)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_exposure(resource_name="a", exposure_category=ExposureCategory.STORAGE_BUCKET)
        eng.record_exposure(resource_name="b", exposure_category=ExposureCategory.DATABASE)
        assert len(eng.list_exposures(exposure_category=ExposureCategory.STORAGE_BUCKET)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_exposure(resource_name="a", team="sec")
        eng.record_exposure(resource_name="b", team="ops")
        assert len(eng.list_exposures(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_exposure(resource_name=f"t-{i}")
        assert len(eng.list_exposures(limit=5)) == 5


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
        eng.record_exposure(resource_name="a", cloud_provider=CloudProvider.AWS, risk_score=90.0)
        eng.record_exposure(resource_name="b", cloud_provider=CloudProvider.AWS, risk_score=70.0)
        result = eng.analyze_distribution()
        assert CloudProvider.AWS.value in result
        assert result[CloudProvider.AWS.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_exposure(resource_name="a", risk_score=60.0)
        eng.record_exposure(resource_name="b", risk_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_exposure(resource_name="a", risk_score=50.0)
        eng.record_exposure(resource_name="b", risk_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_exposure(resource_name="a", service="auth", risk_score=90.0)
        eng.record_exposure(resource_name="b", service="api", risk_score=50.0)
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
        eng.record_exposure(resource_name="test", risk_score=50.0)
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
        eng.record_exposure(resource_name="test")
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
        eng.record_exposure(resource_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
