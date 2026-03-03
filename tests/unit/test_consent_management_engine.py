"""Tests for shieldops.compliance.consent_management_engine — ConsentManagementEngine."""

from __future__ import annotations

from shieldops.compliance.consent_management_engine import (
    ConsentAnalysis,
    ConsentComplianceReport,
    ConsentManagementEngine,
    ConsentPurpose,
    ConsentRecord,
    ConsentStatus,
    ConsentType,
)


def _engine(**kw) -> ConsentManagementEngine:
    return ConsentManagementEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_opt_in(self):
        assert ConsentType.OPT_IN == "opt_in"

    def test_type_opt_out(self):
        assert ConsentType.OPT_OUT == "opt_out"

    def test_type_explicit(self):
        assert ConsentType.EXPLICIT == "explicit"

    def test_type_implied(self):
        assert ConsentType.IMPLIED == "implied"

    def test_type_withdrawn(self):
        assert ConsentType.WITHDRAWN == "withdrawn"

    def test_purpose_marketing(self):
        assert ConsentPurpose.MARKETING == "marketing"

    def test_purpose_analytics(self):
        assert ConsentPurpose.ANALYTICS == "analytics"

    def test_purpose_personalization(self):
        assert ConsentPurpose.PERSONALIZATION == "personalization"

    def test_purpose_third_party(self):
        assert ConsentPurpose.THIRD_PARTY == "third_party"

    def test_purpose_essential(self):
        assert ConsentPurpose.ESSENTIAL == "essential"

    def test_status_active(self):
        assert ConsentStatus.ACTIVE == "active"

    def test_status_expired(self):
        assert ConsentStatus.EXPIRED == "expired"

    def test_status_revoked(self):
        assert ConsentStatus.REVOKED == "revoked"

    def test_status_pending(self):
        assert ConsentStatus.PENDING == "pending"

    def test_status_invalid(self):
        assert ConsentStatus.INVALID == "invalid"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_consent_record_defaults(self):
        r = ConsentRecord()
        assert r.id
        assert r.subject_id == ""
        assert r.consent_type == ConsentType.OPT_IN
        assert r.consent_purpose == ConsentPurpose.ESSENTIAL
        assert r.consent_status == ConsentStatus.ACTIVE
        assert r.validity_score == 0.0
        assert r.channel == ""
        assert r.data_controller == ""
        assert r.created_at > 0

    def test_consent_analysis_defaults(self):
        a = ConsentAnalysis()
        assert a.id
        assert a.subject_id == ""
        assert a.consent_purpose == ConsentPurpose.ESSENTIAL
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ConsentComplianceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_validity_score == 0.0
        assert r.by_consent_type == {}
        assert r.by_purpose == {}
        assert r.by_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_consent / get_consent
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_consent(
            subject_id="user-123",
            consent_type=ConsentType.EXPLICIT,
            consent_purpose=ConsentPurpose.MARKETING,
            consent_status=ConsentStatus.ACTIVE,
            validity_score=95.0,
            channel="web",
            data_controller="acme-corp",
        )
        assert r.subject_id == "user-123"
        assert r.consent_type == ConsentType.EXPLICIT
        assert r.validity_score == 95.0
        assert r.channel == "web"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_consent(subject_id="user-456", consent_purpose=ConsentPurpose.ANALYTICS)
        result = eng.get_consent(r.id)
        assert result is not None
        assert result.consent_purpose == ConsentPurpose.ANALYTICS

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_consent("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_consent(subject_id=f"user-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_consents
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_consent(subject_id="u-001")
        eng.record_consent(subject_id="u-002")
        assert len(eng.list_consents()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_consent(subject_id="u-001", consent_type=ConsentType.OPT_IN)
        eng.record_consent(subject_id="u-002", consent_type=ConsentType.OPT_OUT)
        results = eng.list_consents(consent_type=ConsentType.OPT_IN)
        assert len(results) == 1

    def test_filter_by_purpose(self):
        eng = _engine()
        eng.record_consent(subject_id="u-001", consent_purpose=ConsentPurpose.MARKETING)
        eng.record_consent(subject_id="u-002", consent_purpose=ConsentPurpose.ANALYTICS)
        results = eng.list_consents(consent_purpose=ConsentPurpose.MARKETING)
        assert len(results) == 1

    def test_filter_by_controller(self):
        eng = _engine()
        eng.record_consent(subject_id="u-001", data_controller="corp-a")
        eng.record_consent(subject_id="u-002", data_controller="corp-b")
        results = eng.list_consents(data_controller="corp-a")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_consent(subject_id=f"u-{i}")
        assert len(eng.list_consents(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            subject_id="user-123",
            consent_purpose=ConsentPurpose.MARKETING,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="consent expired",
        )
        assert a.subject_id == "user-123"
        assert a.consent_purpose == ConsentPurpose.MARKETING
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(subject_id=f"u-{i}")
        assert len(eng._analyses) == 2

    def test_stored_in_analyses(self):
        eng = _engine()
        eng.add_analysis(subject_id="user-999", consent_purpose=ConsentPurpose.ESSENTIAL)
        assert len(eng._analyses) == 1


# ---------------------------------------------------------------------------
# analyze_purpose_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_consent(
            subject_id="u-001", consent_purpose=ConsentPurpose.MARKETING, validity_score=90.0
        )
        eng.record_consent(
            subject_id="u-002", consent_purpose=ConsentPurpose.MARKETING, validity_score=70.0
        )
        result = eng.analyze_purpose_distribution()
        assert "marketing" in result
        assert result["marketing"]["count"] == 2
        assert result["marketing"]["avg_validity_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_purpose_distribution() == {}


# ---------------------------------------------------------------------------
# identify_consent_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_consent(subject_id="u-001", validity_score=60.0)
        eng.record_consent(subject_id="u-002", validity_score=90.0)
        results = eng.identify_consent_gaps()
        assert len(results) == 1
        assert results[0]["subject_id"] == "u-001"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_consent(subject_id="u-001", validity_score=50.0)
        eng.record_consent(subject_id="u-002", validity_score=30.0)
        results = eng.identify_consent_gaps()
        assert results[0]["validity_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_validity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_consent(subject_id="u-001", data_controller="corp-a", validity_score=90.0)
        eng.record_consent(subject_id="u-002", data_controller="corp-b", validity_score=50.0)
        results = eng.rank_by_validity()
        assert results[0]["data_controller"] == "corp-b"
        assert results[0]["avg_validity_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_validity() == []


# ---------------------------------------------------------------------------
# detect_consent_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(subject_id="u-001", analysis_score=50.0)
        result = eng.detect_consent_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(subject_id="u-001", analysis_score=20.0)
        eng.add_analysis(subject_id="u-002", analysis_score=20.0)
        eng.add_analysis(subject_id="u-003", analysis_score=80.0)
        eng.add_analysis(subject_id="u-004", analysis_score=80.0)
        result = eng.detect_consent_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_consent_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_consent(
            subject_id="user-123",
            consent_type=ConsentType.WITHDRAWN,
            consent_purpose=ConsentPurpose.MARKETING,
            consent_status=ConsentStatus.REVOKED,
            validity_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ConsentComplianceReport)
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
        eng.record_consent(subject_id="u-001")
        eng.add_analysis(subject_id="u-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["purpose_distribution"] == {}


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=3)
        for i in range(7):
            eng.add_analysis(subject_id=f"u-{i}")
        assert len(eng._analyses) == 3
