"""Tests for shieldops.compliance.dpa_baa_tracker — DPABAATracker."""

from __future__ import annotations

from shieldops.compliance.dpa_baa_tracker import (
    AgreementAnalysis,
    AgreementComplianceReport,
    AgreementRecord,
    AgreementStatus,
    AgreementType,
    ComplianceFramework,
    DPABAATracker,
)


def _engine(**kw) -> DPABAATracker:
    return DPABAATracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_dpa(self):
        assert AgreementType.DPA == "dpa"

    def test_type_baa(self):
        assert AgreementType.BAA == "baa"

    def test_type_scc(self):
        assert AgreementType.SCC == "scc"

    def test_type_bcr(self):
        assert AgreementType.BCR == "bcr"

    def test_type_custom(self):
        assert AgreementType.CUSTOM == "custom"

    def test_framework_gdpr(self):
        assert ComplianceFramework.GDPR == "gdpr"

    def test_framework_hipaa(self):
        assert ComplianceFramework.HIPAA == "hipaa"

    def test_framework_ccpa(self):
        assert ComplianceFramework.CCPA == "ccpa"

    def test_framework_soc2(self):
        assert ComplianceFramework.SOC2 == "soc2"

    def test_framework_iso27001(self):
        assert ComplianceFramework.ISO27001 == "iso27001"

    def test_status_active(self):
        assert AgreementStatus.ACTIVE == "active"

    def test_status_expiring(self):
        assert AgreementStatus.EXPIRING == "expiring"

    def test_status_expired(self):
        assert AgreementStatus.EXPIRED == "expired"

    def test_status_under_review(self):
        assert AgreementStatus.UNDER_REVIEW == "under_review"

    def test_status_terminated(self):
        assert AgreementStatus.TERMINATED == "terminated"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_agreement_record_defaults(self):
        r = AgreementRecord()
        assert r.id
        assert r.vendor_id == ""
        assert r.agreement_type == AgreementType.DPA
        assert r.compliance_framework == ComplianceFramework.GDPR
        assert r.agreement_status == AgreementStatus.ACTIVE
        assert r.coverage_score == 0.0
        assert r.legal_owner == ""
        assert r.business_unit == ""
        assert r.created_at > 0

    def test_agreement_analysis_defaults(self):
        a = AgreementAnalysis()
        assert a.id
        assert a.vendor_id == ""
        assert a.agreement_type == AgreementType.DPA
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = AgreementComplianceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_coverage_score == 0.0
        assert r.by_agreement_type == {}
        assert r.by_framework == {}
        assert r.by_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_agreement / get_agreement
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_agreement(
            vendor_id="vendor-001",
            agreement_type=AgreementType.BAA,
            compliance_framework=ComplianceFramework.HIPAA,
            agreement_status=AgreementStatus.ACTIVE,
            coverage_score=92.0,
            legal_owner="legal-team",
            business_unit="healthcare",
        )
        assert r.vendor_id == "vendor-001"
        assert r.agreement_type == AgreementType.BAA
        assert r.coverage_score == 92.0
        assert r.business_unit == "healthcare"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_agreement(vendor_id="vendor-001", agreement_type=AgreementType.SCC)
        result = eng.get_agreement(r.id)
        assert result is not None
        assert result.agreement_type == AgreementType.SCC

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_agreement("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_agreement(vendor_id=f"vendor-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_agreements
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_agreement(vendor_id="v-001")
        eng.record_agreement(vendor_id="v-002")
        assert len(eng.list_agreements()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_agreement(vendor_id="v-001", agreement_type=AgreementType.DPA)
        eng.record_agreement(vendor_id="v-002", agreement_type=AgreementType.BAA)
        results = eng.list_agreements(agreement_type=AgreementType.DPA)
        assert len(results) == 1

    def test_filter_by_framework(self):
        eng = _engine()
        eng.record_agreement(vendor_id="v-001", compliance_framework=ComplianceFramework.GDPR)
        eng.record_agreement(vendor_id="v-002", compliance_framework=ComplianceFramework.HIPAA)
        results = eng.list_agreements(compliance_framework=ComplianceFramework.GDPR)
        assert len(results) == 1

    def test_filter_by_unit(self):
        eng = _engine()
        eng.record_agreement(vendor_id="v-001", business_unit="unit-a")
        eng.record_agreement(vendor_id="v-002", business_unit="unit-b")
        results = eng.list_agreements(business_unit="unit-a")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_agreement(vendor_id=f"v-{i}")
        assert len(eng.list_agreements(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            vendor_id="vendor-001",
            agreement_type=AgreementType.DPA,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="agreement expiring",
        )
        assert a.vendor_id == "vendor-001"
        assert a.agreement_type == AgreementType.DPA
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(vendor_id=f"v-{i}")
        assert len(eng._analyses) == 2

    def test_stored_in_analyses(self):
        eng = _engine()
        eng.add_analysis(vendor_id="vendor-999", agreement_type=AgreementType.BCR)
        assert len(eng._analyses) == 1


# ---------------------------------------------------------------------------
# analyze_framework_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_agreement(
            vendor_id="v-001",
            compliance_framework=ComplianceFramework.GDPR,
            coverage_score=90.0,
        )
        eng.record_agreement(
            vendor_id="v-002",
            compliance_framework=ComplianceFramework.GDPR,
            coverage_score=70.0,
        )
        result = eng.analyze_framework_distribution()
        assert "gdpr" in result
        assert result["gdpr"]["count"] == 2
        assert result["gdpr"]["avg_coverage_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_framework_distribution() == {}


# ---------------------------------------------------------------------------
# identify_agreement_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_agreement(vendor_id="v-001", coverage_score=60.0)
        eng.record_agreement(vendor_id="v-002", coverage_score=90.0)
        results = eng.identify_agreement_gaps()
        assert len(results) == 1
        assert results[0]["vendor_id"] == "v-001"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_agreement(vendor_id="v-001", coverage_score=50.0)
        eng.record_agreement(vendor_id="v-002", coverage_score=30.0)
        results = eng.identify_agreement_gaps()
        assert results[0]["coverage_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_coverage
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_agreement(vendor_id="v-001", business_unit="unit-a", coverage_score=90.0)
        eng.record_agreement(vendor_id="v-002", business_unit="unit-b", coverage_score=50.0)
        results = eng.rank_by_coverage()
        assert results[0]["business_unit"] == "unit-b"
        assert results[0]["avg_coverage_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_coverage() == []


# ---------------------------------------------------------------------------
# detect_agreement_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(vendor_id="v-001", analysis_score=50.0)
        result = eng.detect_agreement_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(vendor_id="v-001", analysis_score=20.0)
        eng.add_analysis(vendor_id="v-002", analysis_score=20.0)
        eng.add_analysis(vendor_id="v-003", analysis_score=80.0)
        eng.add_analysis(vendor_id="v-004", analysis_score=80.0)
        result = eng.detect_agreement_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_agreement_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_agreement(
            vendor_id="vendor-001",
            agreement_type=AgreementType.DPA,
            compliance_framework=ComplianceFramework.GDPR,
            agreement_status=AgreementStatus.EXPIRING,
            coverage_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AgreementComplianceReport)
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
        eng.record_agreement(vendor_id="v-001")
        eng.add_analysis(vendor_id="v-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["agreement_type_distribution"] == {}


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=3)
        for i in range(7):
            eng.add_analysis(vendor_id=f"v-{i}")
        assert len(eng._analyses) == 3
