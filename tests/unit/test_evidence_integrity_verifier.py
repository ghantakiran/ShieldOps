"""Tests for shieldops.security.evidence_integrity_verifier — EvidenceIntegrityVerifier."""

from __future__ import annotations

from shieldops.security.evidence_integrity_verifier import (
    EvidenceIntegrityVerifier,
    EvidenceType,
    HashAlgorithm,
    IntegrityAnalysis,
    IntegrityRecord,
    IntegrityReport,
    VerificationStatus,
)


def _engine(**kw) -> EvidenceIntegrityVerifier:
    return EvidenceIntegrityVerifier(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_algorithm_sha256(self):
        assert HashAlgorithm.SHA256 == "sha256"

    def test_algorithm_sha512(self):
        assert HashAlgorithm.SHA512 == "sha512"

    def test_algorithm_md5(self):
        assert HashAlgorithm.MD5 == "md5"

    def test_algorithm_sha1(self):
        assert HashAlgorithm.SHA1 == "sha1"

    def test_algorithm_blake2(self):
        assert HashAlgorithm.BLAKE2 == "blake2"

    def test_status_verified(self):
        assert VerificationStatus.VERIFIED == "verified"

    def test_status_tampered(self):
        assert VerificationStatus.TAMPERED == "tampered"

    def test_status_pending(self):
        assert VerificationStatus.PENDING == "pending"

    def test_status_failed(self):
        assert VerificationStatus.FAILED == "failed"

    def test_status_expired(self):
        assert VerificationStatus.EXPIRED == "expired"

    def test_type_disk_image(self):
        assert EvidenceType.DISK_IMAGE == "disk_image"

    def test_type_memory_dump(self):
        assert EvidenceType.MEMORY_DUMP == "memory_dump"

    def test_type_log_file(self):
        assert EvidenceType.LOG_FILE == "log_file"

    def test_type_network_capture(self):
        assert EvidenceType.NETWORK_CAPTURE == "network_capture"

    def test_type_configuration(self):
        assert EvidenceType.CONFIGURATION == "configuration"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_integrity_record_defaults(self):
        r = IntegrityRecord()
        assert r.id
        assert r.evidence_name == ""
        assert r.hash_algorithm == HashAlgorithm.SHA256
        assert r.verification_status == VerificationStatus.VERIFIED
        assert r.evidence_type == EvidenceType.DISK_IMAGE
        assert r.integrity_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_integrity_analysis_defaults(self):
        a = IntegrityAnalysis()
        assert a.id
        assert a.evidence_name == ""
        assert a.hash_algorithm == HashAlgorithm.SHA256
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_integrity_report_defaults(self):
        r = IntegrityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.tampered_count == 0
        assert r.avg_integrity_score == 0.0
        assert r.by_algorithm == {}
        assert r.by_status == {}
        assert r.by_type == {}
        assert r.top_tampered == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_verification
# ---------------------------------------------------------------------------


class TestRecordVerification:
    def test_basic(self):
        eng = _engine()
        r = eng.record_verification(
            evidence_name="disk-image-001",
            hash_algorithm=HashAlgorithm.SHA512,
            verification_status=VerificationStatus.TAMPERED,
            evidence_type=EvidenceType.MEMORY_DUMP,
            integrity_score=72.0,
            service="forensics-svc",
            team="security",
        )
        assert r.evidence_name == "disk-image-001"
        assert r.hash_algorithm == HashAlgorithm.SHA512
        assert r.verification_status == VerificationStatus.TAMPERED
        assert r.evidence_type == EvidenceType.MEMORY_DUMP
        assert r.integrity_score == 72.0
        assert r.service == "forensics-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_verification(evidence_name=f"EV-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_verification
# ---------------------------------------------------------------------------


class TestGetVerification:
    def test_found(self):
        eng = _engine()
        r = eng.record_verification(
            evidence_name="disk-image-001",
            verification_status=VerificationStatus.VERIFIED,
        )
        result = eng.get_verification(r.id)
        assert result is not None
        assert result.verification_status == VerificationStatus.VERIFIED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_verification("nonexistent") is None


# ---------------------------------------------------------------------------
# list_verifications
# ---------------------------------------------------------------------------


class TestListVerifications:
    def test_list_all(self):
        eng = _engine()
        eng.record_verification(evidence_name="EV-001")
        eng.record_verification(evidence_name="EV-002")
        assert len(eng.list_verifications()) == 2

    def test_filter_by_algorithm(self):
        eng = _engine()
        eng.record_verification(
            evidence_name="EV-001",
            hash_algorithm=HashAlgorithm.SHA256,
        )
        eng.record_verification(
            evidence_name="EV-002",
            hash_algorithm=HashAlgorithm.SHA512,
        )
        results = eng.list_verifications(hash_algorithm=HashAlgorithm.SHA256)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_verification(
            evidence_name="EV-001",
            verification_status=VerificationStatus.VERIFIED,
        )
        eng.record_verification(
            evidence_name="EV-002",
            verification_status=VerificationStatus.TAMPERED,
        )
        results = eng.list_verifications(
            verification_status=VerificationStatus.VERIFIED,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_verification(evidence_name="EV-001", team="security")
        eng.record_verification(evidence_name="EV-002", team="platform")
        results = eng.list_verifications(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_verification(evidence_name=f"EV-{i}")
        assert len(eng.list_verifications(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            evidence_name="disk-image-001",
            hash_algorithm=HashAlgorithm.BLAKE2,
            analysis_score=88.5,
            threshold=95.0,
            breached=True,
            description="integrity check on disk image",
        )
        assert a.evidence_name == "disk-image-001"
        assert a.hash_algorithm == HashAlgorithm.BLAKE2
        assert a.analysis_score == 88.5
        assert a.threshold == 95.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(evidence_name=f"EV-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_verification_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeVerificationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_verification(
            evidence_name="EV-001",
            hash_algorithm=HashAlgorithm.SHA256,
            integrity_score=90.0,
        )
        eng.record_verification(
            evidence_name="EV-002",
            hash_algorithm=HashAlgorithm.SHA256,
            integrity_score=70.0,
        )
        result = eng.analyze_verification_distribution()
        assert "sha256" in result
        assert result["sha256"]["count"] == 2
        assert result["sha256"]["avg_integrity_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_verification_distribution() == {}


# ---------------------------------------------------------------------------
# identify_tampered_evidence
# ---------------------------------------------------------------------------


class TestIdentifyTamperedEvidence:
    def test_detects_below_threshold(self):
        eng = _engine(integrity_confidence_threshold=95.0)
        eng.record_verification(evidence_name="EV-001", integrity_score=60.0)
        eng.record_verification(evidence_name="EV-002", integrity_score=98.0)
        results = eng.identify_tampered_evidence()
        assert len(results) == 1
        assert results[0]["evidence_name"] == "EV-001"

    def test_sorted_ascending(self):
        eng = _engine(integrity_confidence_threshold=95.0)
        eng.record_verification(evidence_name="EV-001", integrity_score=50.0)
        eng.record_verification(evidence_name="EV-002", integrity_score=30.0)
        results = eng.identify_tampered_evidence()
        assert len(results) == 2
        assert results[0]["integrity_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_tampered_evidence() == []


# ---------------------------------------------------------------------------
# rank_by_integrity
# ---------------------------------------------------------------------------


class TestRankByIntegrity:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_verification(
            evidence_name="EV-001", service="forensics-svc", integrity_score=90.0
        )
        eng.record_verification(evidence_name="EV-002", service="audit-svc", integrity_score=50.0)
        results = eng.rank_by_integrity()
        assert len(results) == 2
        assert results[0]["service"] == "audit-svc"
        assert results[0]["avg_integrity_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_integrity() == []


# ---------------------------------------------------------------------------
# detect_integrity_trends
# ---------------------------------------------------------------------------


class TestDetectIntegrityTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(evidence_name="EV-001", analysis_score=50.0)
        result = eng.detect_integrity_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(evidence_name="EV-001", analysis_score=20.0)
        eng.add_analysis(evidence_name="EV-002", analysis_score=20.0)
        eng.add_analysis(evidence_name="EV-003", analysis_score=80.0)
        eng.add_analysis(evidence_name="EV-004", analysis_score=80.0)
        result = eng.detect_integrity_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_integrity_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(integrity_confidence_threshold=95.0)
        eng.record_verification(
            evidence_name="disk-image-001",
            hash_algorithm=HashAlgorithm.SHA512,
            verification_status=VerificationStatus.TAMPERED,
            evidence_type=EvidenceType.MEMORY_DUMP,
            integrity_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, IntegrityReport)
        assert report.total_records == 1
        assert report.tampered_count == 1
        assert len(report.top_tampered) == 1
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
        eng.record_verification(evidence_name="EV-001")
        eng.add_analysis(evidence_name="EV-001")
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
        assert stats["algorithm_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_verification(
            evidence_name="EV-001",
            hash_algorithm=HashAlgorithm.SHA256,
            service="forensics-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "sha256" in stats["algorithm_distribution"]
