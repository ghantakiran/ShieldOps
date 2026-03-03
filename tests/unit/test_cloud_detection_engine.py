"""Tests for shieldops.security.cloud_detection_engine — CloudDetectionEngine."""

from __future__ import annotations

from shieldops.security.cloud_detection_engine import (
    CloudDetectionAnalysis,
    CloudDetectionEngine,
    CloudDetectionRecord,
    CloudDetectionReport,
    CloudProvider,
    CloudSeverity,
    CloudThreat,
)


def _engine(**kw) -> CloudDetectionEngine:
    return CloudDetectionEngine(**kw)


class TestEnums:
    def test_cloud_threat_iam_abuse(self):
        assert CloudThreat.IAM_ABUSE == "iam_abuse"

    def test_cloud_threat_data_exposure(self):
        assert CloudThreat.DATA_EXPOSURE == "data_exposure"

    def test_cloud_threat_crypto_mining(self):
        assert CloudThreat.CRYPTO_MINING == "crypto_mining"

    def test_cloud_threat_resource_hijack(self):
        assert CloudThreat.RESOURCE_HIJACK == "resource_hijack"

    def test_cloud_threat_config_drift(self):
        assert CloudThreat.CONFIG_DRIFT == "config_drift"

    def test_cloud_provider_aws(self):
        assert CloudProvider.AWS == "aws"

    def test_cloud_provider_gcp(self):
        assert CloudProvider.GCP == "gcp"

    def test_cloud_provider_azure(self):
        assert CloudProvider.AZURE == "azure"

    def test_cloud_provider_multi_cloud(self):
        assert CloudProvider.MULTI_CLOUD == "multi_cloud"

    def test_cloud_provider_custom(self):
        assert CloudProvider.CUSTOM == "custom"

    def test_cloud_severity_critical(self):
        assert CloudSeverity.CRITICAL == "critical"

    def test_cloud_severity_high(self):
        assert CloudSeverity.HIGH == "high"

    def test_cloud_severity_medium(self):
        assert CloudSeverity.MEDIUM == "medium"

    def test_cloud_severity_low(self):
        assert CloudSeverity.LOW == "low"

    def test_cloud_severity_info(self):
        assert CloudSeverity.INFO == "info"


class TestModels:
    def test_record_defaults(self):
        r = CloudDetectionRecord()
        assert r.id
        assert r.name == ""
        assert r.cloud_threat == CloudThreat.IAM_ABUSE
        assert r.cloud_provider == CloudProvider.AWS
        assert r.cloud_severity == CloudSeverity.INFO
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = CloudDetectionAnalysis()
        assert a.id
        assert a.name == ""
        assert a.cloud_threat == CloudThreat.IAM_ABUSE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = CloudDetectionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_cloud_threat == {}
        assert r.by_cloud_provider == {}
        assert r.by_cloud_severity == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            cloud_threat=CloudThreat.IAM_ABUSE,
            cloud_provider=CloudProvider.GCP,
            cloud_severity=CloudSeverity.CRITICAL,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.cloud_threat == CloudThreat.IAM_ABUSE
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_cloud_threat(self):
        eng = _engine()
        eng.record_entry(name="a", cloud_threat=CloudThreat.IAM_ABUSE)
        eng.record_entry(name="b", cloud_threat=CloudThreat.DATA_EXPOSURE)
        assert len(eng.list_records(cloud_threat=CloudThreat.IAM_ABUSE)) == 1

    def test_filter_by_cloud_provider(self):
        eng = _engine()
        eng.record_entry(name="a", cloud_provider=CloudProvider.AWS)
        eng.record_entry(name="b", cloud_provider=CloudProvider.GCP)
        assert len(eng.list_records(cloud_provider=CloudProvider.AWS)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
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
        eng.record_entry(name="a", cloud_threat=CloudThreat.DATA_EXPOSURE, score=90.0)
        eng.record_entry(name="b", cloud_threat=CloudThreat.DATA_EXPOSURE, score=70.0)
        result = eng.analyze_distribution()
        assert "data_exposure" in result
        assert result["data_exposure"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
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
        eng.record_entry(name="test", score=50.0)
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
        eng.record_entry(name="test")
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
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
