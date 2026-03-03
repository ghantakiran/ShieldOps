"""Tests for shieldops.compliance.pii_classifier_masker — PIIClassifierMasker."""

from __future__ import annotations

from shieldops.compliance.pii_classifier_masker import (
    ClassificationConfidence,
    MaskingAnalysis,
    MaskingMethod,
    PIIClassificationReport,
    PIIClassifierMasker,
    PIIRecord,
    PIIType,
)


def _engine(**kw) -> PIIClassifierMasker:
    return PIIClassifierMasker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_pii_type_email(self):
        assert PIIType.EMAIL == "email"

    def test_pii_type_phone(self):
        assert PIIType.PHONE == "phone"

    def test_pii_type_ssn(self):
        assert PIIType.SSN == "ssn"

    def test_pii_type_credit_card(self):
        assert PIIType.CREDIT_CARD == "credit_card"

    def test_pii_type_address(self):
        assert PIIType.ADDRESS == "address"

    def test_masking_redact(self):
        assert MaskingMethod.REDACT == "redact"

    def test_masking_hash(self):
        assert MaskingMethod.HASH == "hash"

    def test_masking_tokenize(self):
        assert MaskingMethod.TOKENIZE == "tokenize"  # noqa: S105

    def test_masking_encrypt(self):
        assert MaskingMethod.ENCRYPT == "encrypt"

    def test_masking_pseudonymize(self):
        assert MaskingMethod.PSEUDONYMIZE == "pseudonymize"

    def test_confidence_high(self):
        assert ClassificationConfidence.HIGH == "high"

    def test_confidence_medium(self):
        assert ClassificationConfidence.MEDIUM == "medium"

    def test_confidence_low(self):
        assert ClassificationConfidence.LOW == "low"

    def test_confidence_uncertain(self):
        assert ClassificationConfidence.UNCERTAIN == "uncertain"

    def test_confidence_manual(self):
        assert ClassificationConfidence.MANUAL == "manual"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_pii_record_defaults(self):
        r = PIIRecord()
        assert r.id
        assert r.data_field == ""
        assert r.pii_type == PIIType.EMAIL
        assert r.masking_method == MaskingMethod.REDACT
        assert r.confidence == ClassificationConfidence.HIGH
        assert r.confidence_score == 0.0
        assert r.source_system == ""
        assert r.data_owner == ""
        assert r.created_at > 0

    def test_masking_analysis_defaults(self):
        a = MaskingAnalysis()
        assert a.id
        assert a.data_field == ""
        assert a.pii_type == PIIType.EMAIL
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PIIClassificationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_confidence_score == 0.0
        assert r.by_pii_type == {}
        assert r.by_masking_method == {}
        assert r.by_confidence == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_pii / get_pii
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_pii(
            data_field="email_address",
            pii_type=PIIType.EMAIL,
            masking_method=MaskingMethod.HASH,
            confidence=ClassificationConfidence.HIGH,
            confidence_score=95.0,
            source_system="crm",
            data_owner="privacy-team",
        )
        assert r.data_field == "email_address"
        assert r.pii_type == PIIType.EMAIL
        assert r.masking_method == MaskingMethod.HASH
        assert r.confidence_score == 95.0
        assert r.source_system == "crm"
        assert r.data_owner == "privacy-team"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_pii(data_field="phone_number", pii_type=PIIType.PHONE)
        result = eng.get_pii(r.id)
        assert result is not None
        assert result.pii_type == PIIType.PHONE

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_pii("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_pii(data_field=f"field-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_piis
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_pii(data_field="f-001")
        eng.record_pii(data_field="f-002")
        assert len(eng.list_piis()) == 2

    def test_filter_by_pii_type(self):
        eng = _engine()
        eng.record_pii(data_field="f-001", pii_type=PIIType.EMAIL)
        eng.record_pii(data_field="f-002", pii_type=PIIType.SSN)
        results = eng.list_piis(pii_type=PIIType.EMAIL)
        assert len(results) == 1

    def test_filter_by_masking_method(self):
        eng = _engine()
        eng.record_pii(data_field="f-001", masking_method=MaskingMethod.REDACT)
        eng.record_pii(data_field="f-002", masking_method=MaskingMethod.HASH)
        results = eng.list_piis(masking_method=MaskingMethod.REDACT)
        assert len(results) == 1

    def test_filter_by_data_owner(self):
        eng = _engine()
        eng.record_pii(data_field="f-001", data_owner="team-a")
        eng.record_pii(data_field="f-002", data_owner="team-b")
        results = eng.list_piis(data_owner="team-a")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_pii(data_field=f"f-{i}")
        assert len(eng.list_piis(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            data_field="email_address",
            pii_type=PIIType.EMAIL,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="classification gap",
        )
        assert a.data_field == "email_address"
        assert a.pii_type == PIIType.EMAIL
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(data_field=f"f-{i}")
        assert len(eng._analyses) == 2

    def test_stored_in_analyses(self):
        eng = _engine()
        eng.add_analysis(data_field="ssn_field", pii_type=PIIType.SSN)
        assert len(eng._analyses) == 1


# ---------------------------------------------------------------------------
# analyze_pii_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_pii(data_field="f-001", pii_type=PIIType.EMAIL, confidence_score=90.0)
        eng.record_pii(data_field="f-002", pii_type=PIIType.EMAIL, confidence_score=70.0)
        result = eng.analyze_pii_distribution()
        assert "email" in result
        assert result["email"]["count"] == 2
        assert result["email"]["avg_confidence_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_pii_distribution() == {}


# ---------------------------------------------------------------------------
# identify_masking_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_pii(data_field="f-001", confidence_score=60.0)
        eng.record_pii(data_field="f-002", confidence_score=90.0)
        results = eng.identify_masking_gaps()
        assert len(results) == 1
        assert results[0]["data_field"] == "f-001"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_pii(data_field="f-001", confidence_score=50.0)
        eng.record_pii(data_field="f-002", confidence_score=30.0)
        results = eng.identify_masking_gaps()
        assert results[0]["confidence_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_confidence
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_pii(data_field="f-001", source_system="crm", confidence_score=90.0)
        eng.record_pii(data_field="f-002", source_system="erp", confidence_score=50.0)
        results = eng.rank_by_confidence()
        assert results[0]["source_system"] == "erp"
        assert results[0]["avg_confidence_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_confidence() == []


# ---------------------------------------------------------------------------
# detect_classification_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(data_field="f-001", analysis_score=50.0)
        result = eng.detect_classification_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(data_field="f-001", analysis_score=20.0)
        eng.add_analysis(data_field="f-002", analysis_score=20.0)
        eng.add_analysis(data_field="f-003", analysis_score=80.0)
        eng.add_analysis(data_field="f-004", analysis_score=80.0)
        result = eng.detect_classification_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_classification_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_pii(
            data_field="email_address",
            pii_type=PIIType.EMAIL,
            masking_method=MaskingMethod.HASH,
            confidence=ClassificationConfidence.HIGH,
            confidence_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, PIIClassificationReport)
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
        eng.record_pii(data_field="f-001")
        eng.add_analysis(data_field="f-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["pii_type_distribution"] == {}


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=3)
        for i in range(7):
            eng.add_analysis(data_field=f"f-{i}")
        assert len(eng._analyses) == 3
