"""Tests for shieldops.security.cloud_posture_manager — CloudSecurityPostureManager."""

from __future__ import annotations

from shieldops.security.cloud_posture_manager import (
    CloudResource,
    CloudSecurityPostureManager,
    ComplianceBenchmark,
    MisconfigurationFinding,
    MisconfigurationType,
    PostureReport,
    RemediationPriority,
)


def _engine(**kw) -> CloudSecurityPostureManager:
    return CloudSecurityPostureManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # MisconfigurationType (6)
    def test_type_public_access(self):
        assert MisconfigurationType.PUBLIC_ACCESS == "public_access"

    def test_type_weak_encryption(self):
        assert MisconfigurationType.WEAK_ENCRYPTION == "weak_encryption"

    def test_type_permissive_iam(self):
        assert MisconfigurationType.PERMISSIVE_IAM == "permissive_iam"

    def test_type_missing_logging(self):
        assert MisconfigurationType.MISSING_LOGGING == "missing_logging"

    def test_type_unpatched_resource(self):
        assert MisconfigurationType.UNPATCHED_RESOURCE == "unpatched_resource"

    def test_type_network_exposure(self):
        assert MisconfigurationType.NETWORK_EXPOSURE == "network_exposure"

    # ComplianceBenchmark (5)
    def test_benchmark_cis_aws(self):
        assert ComplianceBenchmark.CIS_AWS == "cis_aws"

    def test_benchmark_cis_gcp(self):
        assert ComplianceBenchmark.CIS_GCP == "cis_gcp"

    def test_benchmark_cis_azure(self):
        assert ComplianceBenchmark.CIS_AZURE == "cis_azure"

    def test_benchmark_nist_800_53(self):
        assert ComplianceBenchmark.NIST_800_53 == "nist_800_53"

    def test_benchmark_soc2_type2(self):
        assert ComplianceBenchmark.SOC2_TYPE2 == "soc2_type2"

    # RemediationPriority (5)
    def test_priority_immediate(self):
        assert RemediationPriority.IMMEDIATE == "immediate"

    def test_priority_high(self):
        assert RemediationPriority.HIGH == "high"

    def test_priority_medium(self):
        assert RemediationPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert RemediationPriority.LOW == "low"

    def test_priority_informational(self):
        assert RemediationPriority.INFORMATIONAL == "informational"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_cloud_resource_defaults(self):
        r = CloudResource()
        assert r.id
        assert r.resource_id == ""
        assert r.resource_type == ""
        assert r.cloud_provider == ""
        assert r.region == ""
        assert r.account_id == ""
        assert r.compliance_benchmarks == []
        assert r.created_at > 0

    def test_misconfiguration_finding_defaults(self):
        f = MisconfigurationFinding()
        assert f.id
        assert f.resource_id == ""
        assert f.finding_type == MisconfigurationType.PUBLIC_ACCESS
        assert f.benchmark == ComplianceBenchmark.CIS_AWS
        assert f.priority == RemediationPriority.MEDIUM
        assert f.description == ""
        assert f.is_resolved is False
        assert f.resolved_at == 0.0
        assert f.created_at > 0

    def test_posture_report_defaults(self):
        r = PostureReport()
        assert r.total_resources == 0
        assert r.total_findings == 0
        assert r.open_findings == 0
        assert r.resolved_findings == 0
        assert r.compliance_score == 0.0
        assert r.critical_findings == 0
        assert r.provider_distribution == {}
        assert r.finding_type_distribution == {}
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# register_resource
# ---------------------------------------------------------------------------


class TestRegisterResource:
    def test_basic_register(self):
        eng = _engine()
        res = eng.register_resource(
            resource_id="arn:aws:s3:::my-bucket",
            resource_type="s3_bucket",
            cloud_provider="aws",
            region="us-east-1",
            account_id="123456789012",
            compliance_benchmarks=["cis_aws"],
        )
        assert res.resource_id == "arn:aws:s3:::my-bucket"
        assert res.resource_type == "s3_bucket"
        assert res.cloud_provider == "aws"
        assert res.region == "us-east-1"
        assert res.account_id == "123456789012"
        assert res.compliance_benchmarks == ["cis_aws"]

    def test_eviction_at_max(self):
        eng = _engine(max_resources=3)
        for i in range(5):
            eng.register_resource(
                resource_id=f"res-{i}",
                resource_type="vm",
                cloud_provider="gcp",
            )
        assert len(eng._resources) == 3


# ---------------------------------------------------------------------------
# get_resource
# ---------------------------------------------------------------------------


class TestGetResource:
    def test_found(self):
        eng = _engine()
        res = eng.register_resource(
            resource_id="bucket-1",
            resource_type="s3_bucket",
            cloud_provider="aws",
        )
        assert eng.get_resource(res.id) is not None
        assert eng.get_resource(res.id).resource_id == "bucket-1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_resource("nonexistent") is None


# ---------------------------------------------------------------------------
# list_resources
# ---------------------------------------------------------------------------


class TestListResources:
    def test_list_all(self):
        eng = _engine()
        eng.register_resource("res-1", "vm", "aws")
        eng.register_resource("res-2", "bucket", "gcp")
        assert len(eng.list_resources()) == 2

    def test_filter_by_provider(self):
        eng = _engine()
        eng.register_resource("res-1", "vm", "aws")
        eng.register_resource("res-2", "vm", "gcp")
        eng.register_resource("res-3", "bucket", "aws")
        results = eng.list_resources(cloud_provider="aws")
        assert len(results) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.register_resource("res-1", "vm", "aws")
        eng.register_resource("res-2", "bucket", "aws")
        eng.register_resource("res-3", "vm", "gcp")
        results = eng.list_resources(resource_type="vm")
        assert len(results) == 2


# ---------------------------------------------------------------------------
# record_finding
# ---------------------------------------------------------------------------


class TestRecordFinding:
    def test_basic_record(self):
        eng = _engine()
        res = eng.register_resource("bucket-1", "s3_bucket", "aws")
        finding = eng.record_finding(
            resource_id=res.id,
            finding_type=MisconfigurationType.PUBLIC_ACCESS,
            benchmark=ComplianceBenchmark.CIS_AWS,
            priority=RemediationPriority.IMMEDIATE,
            description="S3 bucket is publicly accessible",
        )
        assert finding.resource_id == res.id
        assert finding.finding_type == MisconfigurationType.PUBLIC_ACCESS
        assert finding.priority == RemediationPriority.IMMEDIATE
        assert finding.description == "S3 bucket is publicly accessible"
        assert finding.is_resolved is False


# ---------------------------------------------------------------------------
# evaluate_resource
# ---------------------------------------------------------------------------


class TestEvaluateResource:
    def test_with_findings(self):
        eng = _engine()
        res = eng.register_resource("bucket-1", "s3_bucket", "aws")
        eng.record_finding(res.id, MisconfigurationType.PUBLIC_ACCESS)
        eng.record_finding(res.id, MisconfigurationType.WEAK_ENCRYPTION)
        findings = eng.evaluate_resource(res.id)
        assert len(findings) == 2
        types = {f.finding_type for f in findings}
        assert MisconfigurationType.PUBLIC_ACCESS in types
        assert MisconfigurationType.WEAK_ENCRYPTION in types


# ---------------------------------------------------------------------------
# calculate_compliance_score
# ---------------------------------------------------------------------------


class TestCalculateComplianceScore:
    def test_with_open_and_resolved_findings(self):
        eng = _engine()
        res = eng.register_resource("bucket-1", "s3_bucket", "aws")
        f1 = eng.record_finding(
            res.id,
            MisconfigurationType.PUBLIC_ACCESS,
            benchmark=ComplianceBenchmark.CIS_AWS,
        )
        eng.record_finding(
            res.id,
            MisconfigurationType.WEAK_ENCRYPTION,
            benchmark=ComplianceBenchmark.CIS_AWS,
        )
        eng.resolve_finding(f1.id)
        result = eng.calculate_compliance_score()
        assert result["overall_score"] == 50.0
        assert result["total_findings"] == 2
        assert result["open_findings"] == 1
        cis_aws = result["benchmark_scores"]["cis_aws"]
        assert cis_aws["score"] == 50.0
        assert cis_aws["resolved_findings"] == 1


# ---------------------------------------------------------------------------
# detect_high_risk_resources
# ---------------------------------------------------------------------------


class TestDetectHighRiskResources:
    def test_with_immediate_findings(self):
        eng = _engine()
        res = eng.register_resource("bucket-1", "s3_bucket", "aws")
        eng.record_finding(
            res.id,
            MisconfigurationType.PUBLIC_ACCESS,
            priority=RemediationPriority.IMMEDIATE,
        )
        eng.record_finding(
            res.id,
            MisconfigurationType.PERMISSIVE_IAM,
            priority=RemediationPriority.IMMEDIATE,
        )
        # Medium-priority finding should not appear in high risk
        eng.record_finding(
            res.id,
            MisconfigurationType.MISSING_LOGGING,
            priority=RemediationPriority.MEDIUM,
        )
        high_risk = eng.detect_high_risk_resources()
        assert len(high_risk) == 1
        assert high_risk[0]["immediate_finding_count"] == 2
        assert high_risk[0]["resource_id"] == "bucket-1"
        assert high_risk[0]["cloud_provider"] == "aws"


# ---------------------------------------------------------------------------
# resolve_finding
# ---------------------------------------------------------------------------


class TestResolveFinding:
    def test_success(self):
        eng = _engine()
        res = eng.register_resource("vm-1", "vm", "gcp")
        finding = eng.record_finding(res.id, MisconfigurationType.MISSING_LOGGING)
        ok = eng.resolve_finding(finding.id)
        assert ok is True
        assert finding.is_resolved is True
        assert finding.resolved_at > 0

    def test_not_found(self):
        eng = _engine()
        assert eng.resolve_finding("bad-id") is False


# ---------------------------------------------------------------------------
# generate_posture_report
# ---------------------------------------------------------------------------


class TestGeneratePostureReport:
    def test_basic_report(self):
        eng = _engine()
        res_a = eng.register_resource("bucket-1", "s3_bucket", "aws")
        res_b = eng.register_resource("vm-1", "compute_instance", "gcp")
        f1 = eng.record_finding(
            res_a.id,
            MisconfigurationType.PUBLIC_ACCESS,
            priority=RemediationPriority.IMMEDIATE,
        )
        eng.record_finding(
            res_b.id,
            MisconfigurationType.MISSING_LOGGING,
            priority=RemediationPriority.MEDIUM,
        )
        eng.resolve_finding(f1.id)
        report = eng.generate_posture_report()
        assert report.total_resources == 2
        assert report.total_findings == 2
        assert report.open_findings == 1
        assert report.resolved_findings == 1
        assert report.compliance_score > 0
        assert len(report.provider_distribution) == 2
        assert len(report.finding_type_distribution) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_both_lists(self):
        eng = _engine()
        res = eng.register_resource("bucket-1", "s3_bucket", "aws")
        eng.record_finding(res.id, MisconfigurationType.PUBLIC_ACCESS)
        assert len(eng._resources) == 1
        assert len(eng._findings) == 1
        eng.clear_data()
        assert len(eng._resources) == 0
        assert len(eng._findings) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_resources"] == 0
        assert stats["total_findings"] == 0
        assert stats["open_findings"] == 0
        assert stats["resolved_findings"] == 0
        assert stats["provider_distribution"] == {}
        assert stats["resource_type_distribution"] == {}
        assert stats["finding_type_distribution"] == {}
        assert stats["priority_distribution"] == {}
        assert stats["benchmark_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        res = eng.register_resource("vm-1", "vm", "aws")
        eng.record_finding(res.id, MisconfigurationType.PERMISSIVE_IAM)
        stats = eng.get_stats()
        assert stats["total_resources"] == 1
        assert stats["total_findings"] == 1
        assert stats["open_findings"] == 1
        assert stats["resolved_findings"] == 0
        assert stats["max_resources"] == 200000
        assert stats["auto_resolve_days"] == 30
