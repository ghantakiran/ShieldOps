"""Tests for shieldops.incidents.root_cause_verifier."""

from __future__ import annotations

from shieldops.incidents.root_cause_verifier import (
    CausalStrength,
    EvidenceChain,
    EvidenceType,
    RootCauseVerificationEngine,
    RootCauseVerifierReport,
    VerificationRecord,
    VerificationResult,
)


def _engine(**kw) -> RootCauseVerificationEngine:
    return RootCauseVerificationEngine(**kw)


# ---------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------


class TestEnums:
    # EvidenceType (5)
    def test_evidence_log_pattern(self):
        assert EvidenceType.LOG_PATTERN == "log_pattern"

    def test_evidence_metric_anomaly(self):
        assert EvidenceType.METRIC_ANOMALY == "metric_anomaly"

    def test_evidence_trace_correlation(self):
        assert EvidenceType.TRACE_CORRELATION == "trace_correlation"

    def test_evidence_config_change(self):
        assert EvidenceType.CONFIG_CHANGE == "config_change"

    def test_evidence_deployment_event(self):
        assert EvidenceType.DEPLOYMENT_EVENT == "deployment_event"

    # VerificationResult (5)
    def test_result_confirmed(self):
        assert VerificationResult.CONFIRMED == "confirmed"

    def test_result_likely(self):
        assert VerificationResult.LIKELY == "likely"

    def test_result_inconclusive(self):
        assert VerificationResult.INCONCLUSIVE == "inconclusive"

    def test_result_unlikely(self):
        assert VerificationResult.UNLIKELY == "unlikely"

    def test_result_disproved(self):
        assert VerificationResult.DISPROVED == "disproved"

    # CausalStrength (5)
    def test_strength_strong(self):
        assert CausalStrength.STRONG == "strong"

    def test_strength_moderate(self):
        assert CausalStrength.MODERATE == "moderate"

    def test_strength_weak(self):
        assert CausalStrength.WEAK == "weak"

    def test_strength_speculative(self):
        assert CausalStrength.SPECULATIVE == "speculative"

    def test_strength_none(self):
        assert CausalStrength.NONE == "none"


# ---------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------


class TestModels:
    def test_verification_record_defaults(self):
        r = VerificationRecord()
        assert r.id
        assert r.hypothesis == ""
        assert r.evidence_type == EvidenceType.LOG_PATTERN
        assert r.result == VerificationResult.CONFIRMED
        assert r.strength == CausalStrength.STRONG
        assert r.confidence_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_evidence_chain_defaults(self):
        r = EvidenceChain()
        assert r.id
        assert r.chain_name == ""
        assert r.evidence_type == EvidenceType.LOG_PATTERN
        assert r.strength == CausalStrength.STRONG
        assert r.link_count == 0
        assert r.weight == 1.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = RootCauseVerifierReport()
        assert r.total_verifications == 0
        assert r.total_chains == 0
        assert r.confirmed_rate_pct == 0.0
        assert r.by_evidence_type == {}
        assert r.by_result == {}
        assert r.disproved_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------
# record_verification
# ---------------------------------------------------------------


class TestRecordVerification:
    def test_basic(self):
        eng = _engine()
        r = eng.record_verification(
            "hyp-a",
            evidence_type=EvidenceType.LOG_PATTERN,
            result=VerificationResult.CONFIRMED,
        )
        assert r.hypothesis == "hyp-a"
        assert r.evidence_type == EvidenceType.LOG_PATTERN

    def test_with_strength(self):
        eng = _engine()
        r = eng.record_verification(
            "hyp-b",
            strength=CausalStrength.WEAK,
        )
        assert r.strength == CausalStrength.WEAK

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_verification(f"hyp-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------
# get_verification
# ---------------------------------------------------------------


class TestGetVerification:
    def test_found(self):
        eng = _engine()
        r = eng.record_verification("hyp-a")
        assert eng.get_verification(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_verification("nonexistent") is None


# ---------------------------------------------------------------
# list_verifications
# ---------------------------------------------------------------


class TestListVerifications:
    def test_list_all(self):
        eng = _engine()
        eng.record_verification("hyp-a")
        eng.record_verification("hyp-b")
        assert len(eng.list_verifications()) == 2

    def test_filter_by_hypothesis(self):
        eng = _engine()
        eng.record_verification("hyp-a")
        eng.record_verification("hyp-b")
        results = eng.list_verifications(hypothesis="hyp-a")
        assert len(results) == 1

    def test_filter_by_evidence_type(self):
        eng = _engine()
        eng.record_verification(
            "hyp-a",
            evidence_type=EvidenceType.CONFIG_CHANGE,
        )
        eng.record_verification(
            "hyp-b",
            evidence_type=EvidenceType.METRIC_ANOMALY,
        )
        results = eng.list_verifications(evidence_type=EvidenceType.CONFIG_CHANGE)
        assert len(results) == 1


# ---------------------------------------------------------------
# add_evidence_chain
# ---------------------------------------------------------------


class TestAddEvidenceChain:
    def test_basic(self):
        eng = _engine()
        c = eng.add_evidence_chain(
            "chain-1",
            evidence_type=EvidenceType.LOG_PATTERN,
            strength=CausalStrength.STRONG,
            link_count=5,
            weight=2.0,
        )
        assert c.chain_name == "chain-1"
        assert c.link_count == 5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_evidence_chain(f"chain-{i}")
        assert len(eng._chains) == 2


# ---------------------------------------------------------------
# analyze_verification_accuracy
# ---------------------------------------------------------------


class TestAnalyzeVerificationAccuracy:
    def test_with_data(self):
        eng = _engine()
        eng.record_verification(
            "hyp-a",
            result=VerificationResult.CONFIRMED,
        )
        eng.record_verification(
            "hyp-a",
            result=VerificationResult.DISPROVED,
        )
        result = eng.analyze_verification_accuracy("hyp-a")
        assert result["hypothesis"] == "hyp-a"
        assert result["verification_count"] == 2
        assert result["confirmed_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_verification_accuracy("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_confidence_pct=50.0)
        eng.record_verification(
            "hyp-a",
            result=VerificationResult.CONFIRMED,
        )
        result = eng.analyze_verification_accuracy("hyp-a")
        assert result["meets_threshold"] is True


# ---------------------------------------------------------------
# identify_disproved_hypotheses
# ---------------------------------------------------------------


class TestIdentifyDisprovedHypotheses:
    def test_with_disproved(self):
        eng = _engine()
        eng.record_verification(
            "hyp-a",
            result=VerificationResult.DISPROVED,
        )
        eng.record_verification(
            "hyp-a",
            result=VerificationResult.UNLIKELY,
        )
        eng.record_verification(
            "hyp-b",
            result=VerificationResult.CONFIRMED,
        )
        results = eng.identify_disproved_hypotheses()
        assert len(results) == 1
        assert results[0]["hypothesis"] == "hyp-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_disproved_hypotheses() == []


# ---------------------------------------------------------------
# rank_by_confidence
# ---------------------------------------------------------------


class TestRankByConfidence:
    def test_with_data(self):
        eng = _engine()
        eng.record_verification("hyp-a", confidence_score=90.0)
        eng.record_verification("hyp-a", confidence_score=80.0)
        eng.record_verification("hyp-b", confidence_score=50.0)
        results = eng.rank_by_confidence()
        assert results[0]["hypothesis"] == "hyp-a"
        assert results[0]["avg_confidence"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_confidence() == []


# ---------------------------------------------------------------
# detect_weak_evidence
# ---------------------------------------------------------------


class TestDetectWeakEvidence:
    def test_with_weak(self):
        eng = _engine()
        for _ in range(5):
            eng.record_verification(
                "hyp-a",
                result=VerificationResult.LIKELY,
            )
        eng.record_verification(
            "hyp-b",
            result=VerificationResult.CONFIRMED,
        )
        results = eng.detect_weak_evidence()
        assert len(results) == 1
        assert results[0]["hypothesis"] == "hyp-a"
        assert results[0]["weak_evidence"] is True

    def test_no_weak(self):
        eng = _engine()
        eng.record_verification(
            "hyp-a",
            result=VerificationResult.LIKELY,
        )
        assert eng.detect_weak_evidence() == []


# ---------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_verification(
            "hyp-a",
            result=VerificationResult.CONFIRMED,
        )
        eng.record_verification(
            "hyp-b",
            result=VerificationResult.DISPROVED,
        )
        eng.record_verification(
            "hyp-b",
            result=VerificationResult.DISPROVED,
        )
        eng.add_evidence_chain("chain-1")
        report = eng.generate_report()
        assert report.total_verifications == 3
        assert report.total_chains == 1
        assert report.by_evidence_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_verifications == 0
        assert "below" in report.recommendations[0]


# ---------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_verification("hyp-a")
        eng.add_evidence_chain("chain-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._chains) == 0


# ---------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_verifications"] == 0
        assert stats["total_chains"] == 0
        assert stats["evidence_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_verification(
            "hyp-a",
            evidence_type=EvidenceType.LOG_PATTERN,
        )
        eng.record_verification(
            "hyp-b",
            evidence_type=EvidenceType.CONFIG_CHANGE,
        )
        eng.add_evidence_chain("c1")
        stats = eng.get_stats()
        assert stats["total_verifications"] == 2
        assert stats["total_chains"] == 1
        assert stats["unique_hypotheses"] == 2
