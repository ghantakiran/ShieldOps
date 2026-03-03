"""Tests for shieldops.security.supply_chain_integrity_verifier."""

from __future__ import annotations

from shieldops.security.supply_chain_integrity_verifier import (
    IntegrityAnalysis,
    IntegrityLevel,
    IntegrityRecord,
    SupplyChainIntegrityReport,
    SupplyChainIntegrityVerifier,
    TrustModel,
    VerificationStage,
)


def _engine(**kw) -> SupplyChainIntegrityVerifier:
    return SupplyChainIntegrityVerifier(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_integrity_verified(self):
        assert IntegrityLevel.VERIFIED == "verified"

    def test_integrity_partial(self):
        assert IntegrityLevel.PARTIAL == "partial"

    def test_integrity_unverified(self):
        assert IntegrityLevel.UNVERIFIED == "unverified"

    def test_integrity_compromised(self):
        assert IntegrityLevel.COMPROMISED == "compromised"

    def test_integrity_unknown(self):
        assert IntegrityLevel.UNKNOWN == "unknown"

    def test_stage_source(self):
        assert VerificationStage.SOURCE == "source"

    def test_stage_build(self):
        assert VerificationStage.BUILD == "build"

    def test_stage_package(self):
        assert VerificationStage.PACKAGE == "package"

    def test_stage_deploy(self):
        assert VerificationStage.DEPLOY == "deploy"

    def test_stage_runtime(self):
        assert VerificationStage.RUNTIME == "runtime"

    def test_trust_slsa(self):
        assert TrustModel.SLSA == "slsa"

    def test_trust_sigstore(self):
        assert TrustModel.SIGSTORE == "sigstore"

    def test_trust_notary(self):
        assert TrustModel.NOTARY == "notary"

    def test_trust_custom(self):
        assert TrustModel.CUSTOM == "custom"

    def test_trust_none(self):
        assert TrustModel.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_integrity_record_defaults(self):
        r = IntegrityRecord()
        assert r.id
        assert r.component_name == ""
        assert r.integrity_level == IntegrityLevel.VERIFIED
        assert r.verification_stage == VerificationStage.BUILD
        assert r.trust_model == TrustModel.SLSA
        assert r.integrity_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_integrity_analysis_defaults(self):
        c = IntegrityAnalysis()
        assert c.id
        assert c.component_name == ""
        assert c.integrity_level == IntegrityLevel.VERIFIED
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_supply_chain_integrity_report_defaults(self):
        r = SupplyChainIntegrityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_integrity_score == 0.0
        assert r.by_integrity == {}
        assert r.by_stage == {}
        assert r.by_trust_model == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_integrity / get / list
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_integrity(
            component_name="my-lib",
            integrity_level=IntegrityLevel.PARTIAL,
            verification_stage=VerificationStage.SOURCE,
            trust_model=TrustModel.SIGSTORE,
            integrity_score=65.0,
            service="build",
            team="security",
        )
        assert r.component_name == "my-lib"
        assert r.integrity_level == IntegrityLevel.PARTIAL
        assert r.verification_stage == VerificationStage.SOURCE
        assert r.trust_model == TrustModel.SIGSTORE
        assert r.integrity_score == 65.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_integrity(component_name="mylib", integrity_score=90.0)
        result = eng.get_integrity(r.id)
        assert result is not None
        assert result.integrity_score == 90.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_integrity("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_integrity(component_name=f"comp-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_integrity_records
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_integrity(component_name="a")
        eng.record_integrity(component_name="b")
        assert len(eng.list_integrity_records()) == 2

    def test_filter_by_integrity_level(self):
        eng = _engine()
        eng.record_integrity(component_name="a", integrity_level=IntegrityLevel.VERIFIED)
        eng.record_integrity(component_name="b", integrity_level=IntegrityLevel.COMPROMISED)
        results = eng.list_integrity_records(integrity_level=IntegrityLevel.VERIFIED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_integrity(component_name="a", team="security")
        eng.record_integrity(component_name="b", team="platform")
        results = eng.list_integrity_records(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_integrity(component_name=f"comp-{i}")
        assert len(eng.list_integrity_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            component_name="my-lib",
            integrity_level=IntegrityLevel.COMPROMISED,
            analysis_score=10.0,
            threshold=50.0,
            breached=True,
            description="supply chain compromise detected",
        )
        assert a.component_name == "my-lib"
        assert a.integrity_level == IntegrityLevel.COMPROMISED
        assert a.analysis_score == 10.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(component_name=f"comp-{i}")
        assert len(eng._analyses) == 2

    def test_filter_by_verification_stage(self):
        eng = _engine()
        eng.record_integrity(component_name="a", verification_stage=VerificationStage.BUILD)
        eng.record_integrity(component_name="b", verification_stage=VerificationStage.RUNTIME)
        results = eng.list_integrity_records(verification_stage=VerificationStage.BUILD)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# analyze_integrity_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_integrity(
            component_name="a", integrity_level=IntegrityLevel.VERIFIED, integrity_score=90.0
        )
        eng.record_integrity(
            component_name="b", integrity_level=IntegrityLevel.VERIFIED, integrity_score=70.0
        )
        result = eng.analyze_integrity_distribution()
        assert "verified" in result
        assert result["verified"]["count"] == 2
        assert result["verified"]["avg_integrity_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_integrity_distribution() == {}


# ---------------------------------------------------------------------------
# identify_integrity_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(integrity_gap_threshold=70.0)
        eng.record_integrity(component_name="a", integrity_score=50.0)
        eng.record_integrity(component_name="b", integrity_score=80.0)
        results = eng.identify_integrity_gaps()
        assert len(results) == 1
        assert results[0]["component_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(integrity_gap_threshold=80.0)
        eng.record_integrity(component_name="a", integrity_score=50.0)
        eng.record_integrity(component_name="b", integrity_score=20.0)
        results = eng.identify_integrity_gaps()
        assert len(results) == 2
        assert results[0]["integrity_score"] == 20.0


# ---------------------------------------------------------------------------
# rank_by_integrity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_integrity(component_name="a", service="build", integrity_score=90.0)
        eng.record_integrity(component_name="b", service="deploy", integrity_score=40.0)
        results = eng.rank_by_integrity()
        assert len(results) == 2
        assert results[0]["service"] == "deploy"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_integrity() == []


# ---------------------------------------------------------------------------
# detect_integrity_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(component_name="comp", analysis_score=50.0)
        result = eng.detect_integrity_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(component_name="comp", analysis_score=20.0)
        eng.add_analysis(component_name="comp", analysis_score=20.0)
        eng.add_analysis(component_name="comp", analysis_score=80.0)
        eng.add_analysis(component_name="comp", analysis_score=80.0)
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


class TestReport:
    def test_populated(self):
        eng = _engine(integrity_gap_threshold=60.0)
        eng.record_integrity(
            component_name="my-lib",
            integrity_level=IntegrityLevel.UNVERIFIED,
            verification_stage=VerificationStage.SOURCE,
            integrity_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SupplyChainIntegrityReport)
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
        eng.record_integrity(component_name="comp")
        eng.add_analysis(component_name="comp")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats(self):
        eng = _engine()
        eng.record_integrity(
            component_name="my-lib",
            integrity_level=IntegrityLevel.VERIFIED,
            service="build",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "verified" in stats["integrity_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.record_integrity(component_name=f"comp-{i}")
        assert len(eng._records) == 2
        assert eng._records[-1].component_name == "comp-4"
