"""Tests for shieldops.security.build_artifact_verifier — BuildArtifactVerifier."""

from __future__ import annotations

from shieldops.security.build_artifact_verifier import (
    ArtifactType,
    ArtifactVerification,
    ArtifactVerificationReport,
    BuildArtifactVerifier,
    VerificationAnalysis,
    VerificationMethod,
    VerificationStatus,
)


def _engine(**kw) -> BuildArtifactVerifier:
    return BuildArtifactVerifier(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_container(self):
        assert ArtifactType.CONTAINER == "container"

    def test_type_binary(self):
        assert ArtifactType.BINARY == "binary"

    def test_type_package(self):
        assert ArtifactType.PACKAGE == "package"

    def test_type_library(self):
        assert ArtifactType.LIBRARY == "library"

    def test_type_config(self):
        assert ArtifactType.CONFIG == "config"

    def test_method_signature(self):
        assert VerificationMethod.SIGNATURE == "signature"

    def test_method_checksum(self):
        assert VerificationMethod.CHECKSUM == "checksum"

    def test_method_provenance(self):
        assert VerificationMethod.PROVENANCE == "provenance"

    def test_method_attestation(self):
        assert VerificationMethod.ATTESTATION == "attestation"

    def test_method_policy(self):
        assert VerificationMethod.POLICY == "policy"

    def test_status_verified(self):
        assert VerificationStatus.VERIFIED == "verified"

    def test_status_failed(self):
        assert VerificationStatus.FAILED == "failed"

    def test_status_pending(self):
        assert VerificationStatus.PENDING == "pending"

    def test_status_skipped(self):
        assert VerificationStatus.SKIPPED == "skipped"

    def test_status_unknown(self):
        assert VerificationStatus.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_artifact_verification_defaults(self):
        r = ArtifactVerification()
        assert r.id
        assert r.artifact_name == ""
        assert r.artifact_type == ArtifactType.CONTAINER
        assert r.verification_method == VerificationMethod.SIGNATURE
        assert r.verification_status == VerificationStatus.VERIFIED
        assert r.verification_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_verification_analysis_defaults(self):
        c = VerificationAnalysis()
        assert c.id
        assert c.artifact_name == ""
        assert c.artifact_type == ArtifactType.CONTAINER
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_artifact_verification_report_defaults(self):
        r = ArtifactVerificationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_verification_score == 0.0
        assert r.by_type == {}
        assert r.by_method == {}
        assert r.by_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_verification / get / list
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_verification(
            artifact_name="my-service:v1.0",
            artifact_type=ArtifactType.CONTAINER,
            verification_method=VerificationMethod.SIGNATURE,
            verification_status=VerificationStatus.VERIFIED,
            verification_score=95.0,
            service="build-svc",
            team="platform",
        )
        assert r.artifact_name == "my-service:v1.0"
        assert r.artifact_type == ArtifactType.CONTAINER
        assert r.verification_method == VerificationMethod.SIGNATURE
        assert r.verification_status == VerificationStatus.VERIFIED
        assert r.verification_score == 95.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_verification(artifact_name="binary-v2", verification_score=88.0)
        result = eng.get_verification(r.id)
        assert result is not None
        assert result.verification_score == 88.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_verification("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_verification(artifact_name=f"artifact-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_verifications
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_verification(artifact_name="a")
        eng.record_verification(artifact_name="b")
        assert len(eng.list_verifications()) == 2

    def test_filter_by_artifact_type(self):
        eng = _engine()
        eng.record_verification(artifact_name="a", artifact_type=ArtifactType.CONTAINER)
        eng.record_verification(artifact_name="b", artifact_type=ArtifactType.BINARY)
        results = eng.list_verifications(artifact_type=ArtifactType.CONTAINER)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_verification(artifact_name="a", team="security")
        eng.record_verification(artifact_name="b", team="platform")
        results = eng.list_verifications(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_verification(artifact_name=f"art-{i}")
        assert len(eng.list_verifications(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            artifact_name="my-app:v2",
            artifact_type=ArtifactType.CONTAINER,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="signature mismatch",
        )
        assert a.artifact_name == "my-app:v2"
        assert a.artifact_type == ArtifactType.CONTAINER
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(artifact_name=f"art-{i}")
        assert len(eng._analyses) == 2

    def test_filter_by_verification_status(self):
        eng = _engine()
        eng.record_verification(artifact_name="a", verification_status=VerificationStatus.VERIFIED)
        eng.record_verification(artifact_name="b", verification_status=VerificationStatus.FAILED)
        results = eng.list_verifications(verification_status=VerificationStatus.FAILED)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# analyze_type_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_verification(
            artifact_name="a", artifact_type=ArtifactType.CONTAINER, verification_score=90.0
        )
        eng.record_verification(
            artifact_name="b", artifact_type=ArtifactType.CONTAINER, verification_score=70.0
        )
        result = eng.analyze_type_distribution()
        assert "container" in result
        assert result["container"]["count"] == 2
        assert result["container"]["avg_verification_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


# ---------------------------------------------------------------------------
# identify_verification_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(verification_gap_threshold=80.0)
        eng.record_verification(artifact_name="a", verification_score=60.0)
        eng.record_verification(artifact_name="b", verification_score=90.0)
        results = eng.identify_verification_gaps()
        assert len(results) == 1
        assert results[0]["artifact_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(verification_gap_threshold=80.0)
        eng.record_verification(artifact_name="a", verification_score=50.0)
        eng.record_verification(artifact_name="b", verification_score=30.0)
        results = eng.identify_verification_gaps()
        assert len(results) == 2
        assert results[0]["verification_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_verification
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_verification(artifact_name="a", service="build-svc", verification_score=90.0)
        eng.record_verification(artifact_name="b", service="deploy-svc", verification_score=50.0)
        results = eng.rank_by_verification()
        assert len(results) == 2
        assert results[0]["service"] == "deploy-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_verification() == []


# ---------------------------------------------------------------------------
# detect_verification_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(artifact_name="art", analysis_score=50.0)
        result = eng.detect_verification_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(artifact_name="art", analysis_score=20.0)
        eng.add_analysis(artifact_name="art", analysis_score=20.0)
        eng.add_analysis(artifact_name="art", analysis_score=80.0)
        eng.add_analysis(artifact_name="art", analysis_score=80.0)
        result = eng.detect_verification_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_verification_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(verification_gap_threshold=80.0)
        eng.record_verification(
            artifact_name="my-svc:v1",
            artifact_type=ArtifactType.CONTAINER,
            verification_status=VerificationStatus.FAILED,
            verification_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ArtifactVerificationReport)
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


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_verification(artifact_name="art")
        eng.add_analysis(artifact_name="art")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats(self):
        eng = _engine()
        eng.record_verification(
            artifact_name="art",
            artifact_type=ArtifactType.CONTAINER,
            service="build-svc",
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "container" in stats["type_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.record_verification(artifact_name=f"art-{i}")
        assert len(eng._records) == 2
        assert eng._records[-1].artifact_name == "art-4"
