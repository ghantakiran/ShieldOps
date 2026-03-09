"""Tests for CloudSecurityOrchestrator."""

from __future__ import annotations

from shieldops.security.cloud_security_orchestrator import (
    CloudPosture,
    CloudProvider,
    CloudSecurityOrchestrator,
    CloudSecurityReport,
    GuardrailType,
    MisconfigSeverity,
    Misconfiguration,
    RemediationStatus,
)


def _engine(**kw) -> CloudSecurityOrchestrator:
    return CloudSecurityOrchestrator(**kw)


# --- Enum tests ---


class TestEnums:
    def test_provider_aws(self):
        assert CloudProvider.AWS == "aws"

    def test_provider_gcp(self):
        assert CloudProvider.GCP == "gcp"

    def test_provider_azure(self):
        assert CloudProvider.AZURE == "azure"

    def test_provider_multi(self):
        assert CloudProvider.MULTI_CLOUD == "multi_cloud"

    def test_guardrail_iam(self):
        assert GuardrailType.IAM == "iam"

    def test_guardrail_network(self):
        assert GuardrailType.NETWORK == "network"

    def test_guardrail_encryption(self):
        assert GuardrailType.ENCRYPTION == "encryption"

    def test_guardrail_logging(self):
        assert GuardrailType.LOGGING == "logging"

    def test_guardrail_storage(self):
        assert GuardrailType.STORAGE == "storage"

    def test_misconfig_low(self):
        assert MisconfigSeverity.LOW == "low"

    def test_misconfig_critical(self):
        assert MisconfigSeverity.CRITICAL == "critical"

    def test_remediation_pending(self):
        assert RemediationStatus.PENDING == "pending"

    def test_remediation_completed(self):
        assert RemediationStatus.COMPLETED == "completed"


# --- Model tests ---


class TestModels:
    def test_posture_defaults(self):
        p = CloudPosture()
        assert p.id
        assert p.provider == CloudProvider.AWS
        assert p.score == 0.0

    def test_misconfig_defaults(self):
        m = Misconfiguration()
        assert m.id
        assert m.severity == MisconfigSeverity.LOW

    def test_report_defaults(self):
        r = CloudSecurityReport()
        assert r.total_postures == 0
        assert r.risk_score == 0.0


# --- assess_cloud_posture ---


class TestAssessPosture:
    def test_basic(self):
        eng = _engine()
        p = eng.assess_cloud_posture(
            provider=CloudProvider.GCP,
            guardrail_type=GuardrailType.ENCRYPTION,
            score=85.0,
            service="gke",
            team="infra",
        )
        assert p.provider == CloudProvider.GCP
        assert p.score == 85.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.assess_cloud_posture(score=float(i))
        assert len(eng._postures) == 3


# --- enforce_guardrails ---


class TestEnforceGuardrails:
    def test_violations_detected(self):
        eng = _engine(score_threshold=80.0)
        eng.assess_cloud_posture(
            provider=CloudProvider.AWS,
            guardrail_type=GuardrailType.IAM,
            score=40.0,
        )
        eng.assess_cloud_posture(
            provider=CloudProvider.AWS,
            guardrail_type=GuardrailType.IAM,
            score=90.0,
        )
        result = eng.enforce_guardrails(CloudProvider.AWS, GuardrailType.IAM)
        assert result["violations_count"] == 1

    def test_no_violations(self):
        eng = _engine(score_threshold=50.0)
        eng.assess_cloud_posture(
            provider=CloudProvider.AWS,
            guardrail_type=GuardrailType.IAM,
            score=80.0,
        )
        result = eng.enforce_guardrails(CloudProvider.AWS, GuardrailType.IAM)
        assert result["violations_count"] == 0


# --- remediate_misconfigurations ---


class TestRemediate:
    def test_basic(self):
        eng = _engine()
        m = eng.remediate_misconfigurations(
            provider=CloudProvider.AZURE,
            severity=MisconfigSeverity.HIGH,
            resource="storage-acct",
            description="public access enabled",
        )
        assert m.remediation_status == RemediationStatus.IN_PROGRESS
        assert m.resource == "storage-acct"

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.remediate_misconfigurations(resource=f"r-{i}")
        assert len(eng._misconfigs) == 2


# --- validate_compliance ---


class TestValidateCompliance:
    def test_compliant(self):
        eng = _engine(score_threshold=50.0)
        eng.assess_cloud_posture(provider=CloudProvider.AWS, score=80.0)
        result = eng.validate_compliance(CloudProvider.AWS)
        assert result["compliant"] is True

    def test_non_compliant(self):
        eng = _engine(score_threshold=80.0)
        eng.assess_cloud_posture(provider=CloudProvider.AWS, score=40.0)
        result = eng.validate_compliance(CloudProvider.AWS)
        assert result["compliant"] is False

    def test_no_data(self):
        eng = _engine()
        result = eng.validate_compliance(CloudProvider.GCP)
        assert result["compliant"] is False
        assert result["reason"] == "no_data"


# --- get_cloud_risk_score ---


class TestRiskScore:
    def test_with_data(self):
        eng = _engine()
        eng.assess_cloud_posture(provider=CloudProvider.AWS, score=80.0)
        result = eng.get_cloud_risk_score()
        assert result["overall_risk"] == 20.0
        assert result["by_provider"]["aws"] == 20.0

    def test_empty(self):
        eng = _engine()
        result = eng.get_cloud_risk_score()
        assert result["overall_risk"] == 0.0


# --- list_postures ---


class TestListPostures:
    def test_all(self):
        eng = _engine()
        eng.assess_cloud_posture()
        eng.assess_cloud_posture()
        assert len(eng.list_postures()) == 2

    def test_filter_provider(self):
        eng = _engine()
        eng.assess_cloud_posture(provider=CloudProvider.AWS)
        eng.assess_cloud_posture(provider=CloudProvider.GCP)
        assert len(eng.list_postures(provider=CloudProvider.AWS)) == 1

    def test_filter_team(self):
        eng = _engine()
        eng.assess_cloud_posture(team="sec")
        eng.assess_cloud_posture(team="ops")
        assert len(eng.list_postures(team="sec")) == 1


# --- generate_report ---


class TestReport:
    def test_populated(self):
        eng = _engine(score_threshold=80.0)
        eng.assess_cloud_posture(score=40.0, description="weak")
        eng.remediate_misconfigurations(resource="r1")
        report = eng.generate_report()
        assert isinstance(report, CloudSecurityReport)
        assert report.total_postures == 1
        assert report.total_misconfigs == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "healthy range" in report.recommendations[0]


# --- stats / clear ---


class TestStatsAndClear:
    def test_stats(self):
        eng = _engine()
        eng.assess_cloud_posture(service="s", team="t")
        stats = eng.get_stats()
        assert stats["total_postures"] == 1

    def test_clear(self):
        eng = _engine()
        eng.assess_cloud_posture()
        eng.remediate_misconfigurations()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._postures) == 0
        assert len(eng._misconfigs) == 0
