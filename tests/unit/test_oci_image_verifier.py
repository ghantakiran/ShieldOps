"""Tests for shieldops.security.oci_image_verifier — OCIImageVerifier."""

from __future__ import annotations

from shieldops.security.oci_image_verifier import (
    ImageSource,
    ImageVerificationAnalysis,
    ImageVerificationRecord,
    OCIImageVerificationReport,
    OCIImageVerifier,
    VerificationMethod,
    VerificationResult,
)


def _engine(**kw) -> OCIImageVerifier:
    return OCIImageVerifier(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert VerificationMethod.COSIGN == "cosign"

    def test_e1_v2(self):
        assert VerificationMethod.NOTARY == "notary"

    def test_e1_v3(self):
        assert VerificationMethod.SIGSTORE == "sigstore"

    def test_e1_v4(self):
        assert VerificationMethod.DCT == "dct"

    def test_e1_v5(self):
        assert VerificationMethod.CUSTOM == "custom"

    def test_e2_v1(self):
        assert ImageSource.PUBLIC_REGISTRY == "public_registry"

    def test_e2_v2(self):
        assert ImageSource.PRIVATE_REGISTRY == "private_registry"

    def test_e2_v3(self):
        assert ImageSource.BUILD_PIPELINE == "build_pipeline"

    def test_e2_v4(self):
        assert ImageSource.MIRROR == "mirror"

    def test_e2_v5(self):
        assert ImageSource.UNKNOWN == "unknown"

    def test_e3_v1(self):
        assert VerificationResult.VERIFIED == "verified"

    def test_e3_v2(self):
        assert VerificationResult.UNSIGNED == "unsigned"

    def test_e3_v3(self):
        assert VerificationResult.TAMPERED == "tampered"

    def test_e3_v4(self):
        assert VerificationResult.EXPIRED == "expired"

    def test_e3_v5(self):
        assert VerificationResult.PENDING == "pending"


class TestModels:
    def test_rec(self):
        r = ImageVerificationRecord()
        assert r.id and r.verification_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = ImageVerificationAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = OCIImageVerificationReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_verification(
            verification_id="t",
            verification_method=VerificationMethod.NOTARY,
            image_source=ImageSource.PRIVATE_REGISTRY,
            verification_result=VerificationResult.UNSIGNED,
            verification_score=92.0,
            service="s",
            team="t",
        )
        assert r.verification_id == "t" and r.verification_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_verification(verification_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_verification(verification_id="t")
        assert eng.get_verification(r.id) is not None

    def test_not_found(self):
        assert _engine().get_verification("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_verification(verification_id="a")
        eng.record_verification(verification_id="b")
        assert len(eng.list_verifications()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_verification(verification_id="a", verification_method=VerificationMethod.COSIGN)
        eng.record_verification(verification_id="b", verification_method=VerificationMethod.NOTARY)
        assert len(eng.list_verifications(verification_method=VerificationMethod.COSIGN)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_verification(verification_id="a", image_source=ImageSource.PUBLIC_REGISTRY)
        eng.record_verification(verification_id="b", image_source=ImageSource.PRIVATE_REGISTRY)
        assert len(eng.list_verifications(image_source=ImageSource.PUBLIC_REGISTRY)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_verification(verification_id="a", team="x")
        eng.record_verification(verification_id="b", team="y")
        assert len(eng.list_verifications(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_verification(verification_id=f"t-{i}")
        assert len(eng.list_verifications(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            verification_id="t",
            verification_method=VerificationMethod.NOTARY,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(verification_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_verification(
            verification_id="a",
            verification_method=VerificationMethod.COSIGN,
            verification_score=90.0,
        )
        eng.record_verification(
            verification_id="b",
            verification_method=VerificationMethod.COSIGN,
            verification_score=70.0,
        )
        assert "cosign" in eng.analyze_method_distribution()

    def test_empty(self):
        assert _engine().analyze_method_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(verification_gap_threshold=80.0)
        eng.record_verification(verification_id="a", verification_score=60.0)
        eng.record_verification(verification_id="b", verification_score=90.0)
        assert len(eng.identify_verification_gaps()) == 1

    def test_sorted(self):
        eng = _engine(verification_gap_threshold=80.0)
        eng.record_verification(verification_id="a", verification_score=50.0)
        eng.record_verification(verification_id="b", verification_score=30.0)
        assert len(eng.identify_verification_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_verification(verification_id="a", service="s1", verification_score=80.0)
        eng.record_verification(verification_id="b", service="s2", verification_score=60.0)
        assert eng.rank_by_verification()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_verification() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(verification_id="t", analysis_score=float(v))
        assert eng.detect_verification_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(verification_id="t", analysis_score=float(v))
        assert eng.detect_verification_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_verification_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_verification(verification_id="t", verification_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_verification(verification_id="t")
        eng.add_analysis(verification_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_verification(verification_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_verification(verification_id="a")
        eng.record_verification(verification_id="b")
        eng.add_analysis(verification_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
