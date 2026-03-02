"""Tests for shieldops.security.cloud_security_posture_scorer — CloudSecurityPostureScorer."""

from __future__ import annotations

from shieldops.security.cloud_security_posture_scorer import (
    CloudProvider,
    CloudSecurityPostureScorer,
    ComplianceState,
    PostureAnalysis,
    PostureCategory,
    PostureRecord,
    PostureReport,
)


def _engine(**kw) -> CloudSecurityPostureScorer:
    return CloudSecurityPostureScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_provider_aws(self):
        assert CloudProvider.AWS == "aws"

    def test_provider_gcp(self):
        assert CloudProvider.GCP == "gcp"

    def test_provider_azure(self):
        assert CloudProvider.AZURE == "azure"

    def test_provider_multi_cloud(self):
        assert CloudProvider.MULTI_CLOUD == "multi_cloud"

    def test_provider_hybrid(self):
        assert CloudProvider.HYBRID == "hybrid"

    def test_category_iam(self):
        assert PostureCategory.IAM == "iam"

    def test_category_network(self):
        assert PostureCategory.NETWORK == "network"

    def test_category_storage(self):
        assert PostureCategory.STORAGE == "storage"

    def test_category_compute(self):
        assert PostureCategory.COMPUTE == "compute"

    def test_category_logging(self):
        assert PostureCategory.LOGGING == "logging"

    def test_state_compliant(self):
        assert ComplianceState.COMPLIANT == "compliant"

    def test_state_non_compliant(self):
        assert ComplianceState.NON_COMPLIANT == "non_compliant"

    def test_state_partially_compliant(self):
        assert ComplianceState.PARTIALLY_COMPLIANT == "partially_compliant"

    def test_state_exempt(self):
        assert ComplianceState.EXEMPT == "exempt"

    def test_state_unknown(self):
        assert ComplianceState.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_posture_record_defaults(self):
        r = PostureRecord()
        assert r.id
        assert r.finding_name == ""
        assert r.cloud_provider == CloudProvider.AWS
        assert r.posture_category == PostureCategory.IAM
        assert r.compliance_state == ComplianceState.COMPLIANT
        assert r.posture_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_posture_analysis_defaults(self):
        c = PostureAnalysis()
        assert c.id
        assert c.finding_name == ""
        assert c.cloud_provider == CloudProvider.AWS
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_posture_report_defaults(self):
        r = PostureReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_posture_count == 0
        assert r.avg_posture_score == 0.0
        assert r.by_provider == {}
        assert r.by_category == {}
        assert r.by_state == {}
        assert r.top_low_posture == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_finding
# ---------------------------------------------------------------------------


class TestRecordFinding:
    def test_basic(self):
        eng = _engine()
        r = eng.record_finding(
            finding_name="open-s3-bucket",
            cloud_provider=CloudProvider.GCP,
            posture_category=PostureCategory.STORAGE,
            compliance_state=ComplianceState.NON_COMPLIANT,
            posture_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.finding_name == "open-s3-bucket"
        assert r.cloud_provider == CloudProvider.GCP
        assert r.posture_category == PostureCategory.STORAGE
        assert r.compliance_state == ComplianceState.NON_COMPLIANT
        assert r.posture_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_finding(finding_name=f"F-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_finding
# ---------------------------------------------------------------------------


class TestGetFinding:
    def test_found(self):
        eng = _engine()
        r = eng.record_finding(
            finding_name="open-s3-bucket",
            compliance_state=ComplianceState.COMPLIANT,
        )
        result = eng.get_finding(r.id)
        assert result is not None
        assert result.compliance_state == ComplianceState.COMPLIANT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_finding("nonexistent") is None


# ---------------------------------------------------------------------------
# list_findings
# ---------------------------------------------------------------------------


class TestListFindings:
    def test_list_all(self):
        eng = _engine()
        eng.record_finding(finding_name="F-001")
        eng.record_finding(finding_name="F-002")
        assert len(eng.list_findings()) == 2

    def test_filter_by_cloud_provider(self):
        eng = _engine()
        eng.record_finding(
            finding_name="F-001",
            cloud_provider=CloudProvider.AWS,
        )
        eng.record_finding(
            finding_name="F-002",
            cloud_provider=CloudProvider.GCP,
        )
        results = eng.list_findings(cloud_provider=CloudProvider.AWS)
        assert len(results) == 1

    def test_filter_by_posture_category(self):
        eng = _engine()
        eng.record_finding(
            finding_name="F-001",
            posture_category=PostureCategory.IAM,
        )
        eng.record_finding(
            finding_name="F-002",
            posture_category=PostureCategory.NETWORK,
        )
        results = eng.list_findings(
            posture_category=PostureCategory.IAM,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_finding(finding_name="F-001", team="security")
        eng.record_finding(finding_name="F-002", team="platform")
        results = eng.list_findings(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_finding(finding_name=f"F-{i}")
        assert len(eng.list_findings(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            finding_name="open-s3-bucket",
            cloud_provider=CloudProvider.GCP,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="posture gap detected",
        )
        assert a.finding_name == "open-s3-bucket"
        assert a.cloud_provider == CloudProvider.GCP
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(finding_name=f"F-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_provider_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_finding(
            finding_name="F-001",
            cloud_provider=CloudProvider.AWS,
            posture_score=90.0,
        )
        eng.record_finding(
            finding_name="F-002",
            cloud_provider=CloudProvider.AWS,
            posture_score=70.0,
        )
        result = eng.analyze_provider_distribution()
        assert "aws" in result
        assert result["aws"]["count"] == 2
        assert result["aws"]["avg_posture_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_provider_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_posture_findings
# ---------------------------------------------------------------------------


class TestIdentifyLowPostureFindings:
    def test_detects_below_threshold(self):
        eng = _engine(posture_threshold=80.0)
        eng.record_finding(finding_name="F-001", posture_score=60.0)
        eng.record_finding(finding_name="F-002", posture_score=90.0)
        results = eng.identify_low_posture_findings()
        assert len(results) == 1
        assert results[0]["finding_name"] == "F-001"

    def test_sorted_ascending(self):
        eng = _engine(posture_threshold=80.0)
        eng.record_finding(finding_name="F-001", posture_score=50.0)
        eng.record_finding(finding_name="F-002", posture_score=30.0)
        results = eng.identify_low_posture_findings()
        assert len(results) == 2
        assert results[0]["posture_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_posture_findings() == []


# ---------------------------------------------------------------------------
# rank_by_posture_score
# ---------------------------------------------------------------------------


class TestRankByPostureScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_finding(finding_name="F-001", service="auth-svc", posture_score=90.0)
        eng.record_finding(finding_name="F-002", service="api-gw", posture_score=50.0)
        results = eng.rank_by_posture_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_posture_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_posture_score() == []


# ---------------------------------------------------------------------------
# detect_posture_trends
# ---------------------------------------------------------------------------


class TestDetectPostureTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(finding_name="F-001", analysis_score=50.0)
        result = eng.detect_posture_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(finding_name="F-001", analysis_score=20.0)
        eng.add_analysis(finding_name="F-002", analysis_score=20.0)
        eng.add_analysis(finding_name="F-003", analysis_score=80.0)
        eng.add_analysis(finding_name="F-004", analysis_score=80.0)
        result = eng.detect_posture_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_posture_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(posture_threshold=80.0)
        eng.record_finding(
            finding_name="open-s3-bucket",
            cloud_provider=CloudProvider.GCP,
            posture_category=PostureCategory.STORAGE,
            compliance_state=ComplianceState.NON_COMPLIANT,
            posture_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, PostureReport)
        assert report.total_records == 1
        assert report.low_posture_count == 1
        assert len(report.top_low_posture) == 1
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
        eng.record_finding(finding_name="F-001")
        eng.add_analysis(finding_name="F-001")
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
        assert stats["provider_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_finding(
            finding_name="F-001",
            cloud_provider=CloudProvider.AWS,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "aws" in stats["provider_distribution"]
