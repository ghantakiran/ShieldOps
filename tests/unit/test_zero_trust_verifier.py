"""Tests for shieldops.security.zero_trust_verifier — ZeroTrustVerifier."""

from __future__ import annotations

from shieldops.security.zero_trust_verifier import (
    ComplianceStatus,
    TrustLevel,
    TrustPolicy,
    VerificationRecord,
    VerificationType,
    ZeroTrustReport,
    ZeroTrustVerifier,
)


def _engine(**kw) -> ZeroTrustVerifier:
    return ZeroTrustVerifier(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # VerificationType (5)
    def test_type_identity(self):
        assert VerificationType.IDENTITY == "identity"

    def test_type_device(self):
        assert VerificationType.DEVICE == "device"

    def test_type_network(self):
        assert VerificationType.NETWORK == "network"

    def test_type_application(self):
        assert VerificationType.APPLICATION == "application"

    def test_type_data(self):
        assert VerificationType.DATA == "data"

    # TrustLevel (5)
    def test_level_fully_trusted(self):
        assert TrustLevel.FULLY_TRUSTED == "fully_trusted"

    def test_level_conditionally_trusted(self):
        assert TrustLevel.CONDITIONALLY_TRUSTED == "conditionally_trusted"

    def test_level_limited(self):
        assert TrustLevel.LIMITED == "limited"

    def test_level_untrusted(self):
        assert TrustLevel.UNTRUSTED == "untrusted"

    def test_level_blocked(self):
        assert TrustLevel.BLOCKED == "blocked"

    # ComplianceStatus (5)
    def test_compliance_compliant(self):
        assert ComplianceStatus.COMPLIANT == "compliant"

    def test_compliance_non_compliant(self):
        assert ComplianceStatus.NON_COMPLIANT == "non_compliant"

    def test_compliance_partially_compliant(self):
        assert ComplianceStatus.PARTIALLY_COMPLIANT == "partially_compliant"

    def test_compliance_exempt(self):
        assert ComplianceStatus.EXEMPT == "exempt"

    def test_compliance_pending_review(self):
        assert ComplianceStatus.PENDING_REVIEW == "pending_review"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_verification_record_defaults(self):
        r = VerificationRecord()
        assert r.id
        assert r.service_name == ""
        assert r.verification_type == VerificationType.IDENTITY
        assert r.trust_level == TrustLevel.CONDITIONALLY_TRUSTED
        assert r.compliance_status == ComplianceStatus.PENDING_REVIEW
        assert r.trust_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_trust_policy_defaults(self):
        r = TrustPolicy()
        assert r.id
        assert r.policy_name == ""
        assert r.verification_type == VerificationType.NETWORK
        assert r.trust_level == TrustLevel.LIMITED
        assert r.min_trust_score == 0.0
        assert r.created_at > 0

    def test_zero_trust_report_defaults(self):
        r = ZeroTrustReport()
        assert r.total_verifications == 0
        assert r.total_policies == 0
        assert r.compliance_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_trust_level == {}
        assert r.non_compliant_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_verification
# -------------------------------------------------------------------


class TestRecordVerification:
    def test_basic(self):
        eng = _engine()
        r = eng.record_verification(
            "svc-a",
            verification_type=VerificationType.IDENTITY,
            trust_level=TrustLevel.FULLY_TRUSTED,
        )
        assert r.service_name == "svc-a"
        assert r.verification_type == VerificationType.IDENTITY

    def test_with_compliance(self):
        eng = _engine()
        r = eng.record_verification("svc-b", compliance_status=ComplianceStatus.COMPLIANT)
        assert r.compliance_status == ComplianceStatus.COMPLIANT

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_verification(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_verification
# -------------------------------------------------------------------


class TestGetVerification:
    def test_found(self):
        eng = _engine()
        r = eng.record_verification("svc-a")
        assert eng.get_verification(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_verification("nonexistent") is None


# -------------------------------------------------------------------
# list_verifications
# -------------------------------------------------------------------


class TestListVerifications:
    def test_list_all(self):
        eng = _engine()
        eng.record_verification("svc-a")
        eng.record_verification("svc-b")
        assert len(eng.list_verifications()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_verification("svc-a")
        eng.record_verification("svc-b")
        results = eng.list_verifications(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_verification("svc-a", verification_type=VerificationType.NETWORK)
        eng.record_verification("svc-b", verification_type=VerificationType.DEVICE)
        results = eng.list_verifications(verification_type=VerificationType.NETWORK)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_policy
# -------------------------------------------------------------------


class TestAddPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.add_policy(
            "network-verify",
            verification_type=VerificationType.NETWORK,
            trust_level=TrustLevel.LIMITED,
            min_trust_score=80.0,
        )
        assert p.policy_name == "network-verify"
        assert p.min_trust_score == 80.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_policy(f"policy-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_service_trust
# -------------------------------------------------------------------


class TestAnalyzeServiceTrust:
    def test_with_data(self):
        eng = _engine()
        eng.record_verification(
            "svc-a",
            compliance_status=ComplianceStatus.COMPLIANT,
            trust_score=80.0,
        )
        eng.record_verification(
            "svc-a",
            compliance_status=ComplianceStatus.NON_COMPLIANT,
            trust_score=40.0,
        )
        result = eng.analyze_service_trust("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_verifications"] == 2
        assert result["compliance_rate_pct"] == 50.0
        assert result["avg_trust_score"] == 60.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_service_trust("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_untrusted_services
# -------------------------------------------------------------------


class TestIdentifyUntrustedServices:
    def test_with_untrusted(self):
        eng = _engine()
        eng.record_verification("svc-a", trust_level=TrustLevel.UNTRUSTED)
        eng.record_verification("svc-a", trust_level=TrustLevel.BLOCKED)
        eng.record_verification("svc-b", trust_level=TrustLevel.FULLY_TRUSTED)
        results = eng.identify_untrusted_services()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_untrusted_services() == []


# -------------------------------------------------------------------
# rank_by_trust_score
# -------------------------------------------------------------------


class TestRankByTrustScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_verification("svc-a", trust_score=90.0)
        eng.record_verification("svc-a", trust_score=80.0)
        eng.record_verification("svc-b", trust_score=50.0)
        results = eng.rank_by_trust_score()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_trust_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_trust_score() == []


# -------------------------------------------------------------------
# detect_trust_violations
# -------------------------------------------------------------------


class TestDetectTrustViolations:
    def test_with_violations(self):
        eng = _engine()
        for _ in range(5):
            eng.record_verification("svc-a", compliance_status=ComplianceStatus.NON_COMPLIANT)
        eng.record_verification("svc-b", compliance_status=ComplianceStatus.COMPLIANT)
        results = eng.detect_trust_violations()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["violation_detected"] is True

    def test_no_violations(self):
        eng = _engine()
        eng.record_verification("svc-a", compliance_status=ComplianceStatus.NON_COMPLIANT)
        assert eng.detect_trust_violations() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_verification(
            "svc-a",
            compliance_status=ComplianceStatus.COMPLIANT,
            trust_score=90.0,
        )
        eng.record_verification(
            "svc-b",
            compliance_status=ComplianceStatus.NON_COMPLIANT,
            trust_score=30.0,
        )
        eng.record_verification(
            "svc-b",
            compliance_status=ComplianceStatus.NON_COMPLIANT,
            trust_score=20.0,
        )
        eng.add_policy("policy-1")
        report = eng.generate_report()
        assert report.total_verifications == 3
        assert report.total_policies == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_verifications == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_verification("svc-a")
        eng.add_policy("policy-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._policies) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_verifications"] == 0
        assert stats["total_policies"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_verification("svc-a", verification_type=VerificationType.IDENTITY)
        eng.record_verification("svc-b", verification_type=VerificationType.NETWORK)
        eng.add_policy("p1")
        stats = eng.get_stats()
        assert stats["total_verifications"] == 2
        assert stats["total_policies"] == 1
        assert stats["unique_services"] == 2
