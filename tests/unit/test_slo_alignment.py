"""Tests for shieldops.sla.slo_alignment — SLOAlignmentValidator."""

from __future__ import annotations

from shieldops.sla.slo_alignment import (
    AlignmentDimension,
    AlignmentGap,
    AlignmentRecord,
    AlignmentSeverity,
    AlignmentStatus,
    SLOAlignmentReport,
    SLOAlignmentValidator,
)


def _engine(**kw) -> SLOAlignmentValidator:
    return SLOAlignmentValidator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # AlignmentStatus (5)
    def test_status_aligned(self):
        assert AlignmentStatus.ALIGNED == "aligned"

    def test_status_partially_aligned(self):
        assert AlignmentStatus.PARTIALLY_ALIGNED == "partially_aligned"

    def test_status_misaligned(self):
        assert AlignmentStatus.MISALIGNED == "misaligned"

    def test_status_conflicting(self):
        assert AlignmentStatus.CONFLICTING == "conflicting"

    def test_status_unknown(self):
        assert AlignmentStatus.UNKNOWN == "unknown"

    # AlignmentDimension (5)
    def test_dimension_availability(self):
        assert AlignmentDimension.AVAILABILITY == "availability"

    def test_dimension_latency(self):
        assert AlignmentDimension.LATENCY == "latency"

    def test_dimension_throughput(self):
        assert AlignmentDimension.THROUGHPUT == "throughput"

    def test_dimension_error_rate(self):
        assert AlignmentDimension.ERROR_RATE == "error_rate"

    def test_dimension_durability(self):
        assert AlignmentDimension.DURABILITY == "durability"

    # AlignmentSeverity (5)
    def test_severity_critical(self):
        assert AlignmentSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert AlignmentSeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert AlignmentSeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert AlignmentSeverity.LOW == "low"

    def test_severity_info(self):
        assert AlignmentSeverity.INFO == "info"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_alignment_record_defaults(self):
        r = AlignmentRecord()
        assert r.id
        assert r.service == ""
        assert r.dependency == ""
        assert r.status == AlignmentStatus.UNKNOWN
        assert r.dimension == AlignmentDimension.AVAILABILITY
        assert r.alignment_score == 0.0
        assert r.severity == AlignmentSeverity.INFO
        assert r.details == ""
        assert r.created_at > 0

    def test_alignment_gap_defaults(self):
        g = AlignmentGap()
        assert g.id
        assert g.record_id == ""
        assert g.service == ""
        assert g.gap_description == ""
        assert g.severity == AlignmentSeverity.INFO
        assert g.created_at > 0

    def test_report_defaults(self):
        r = SLOAlignmentReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_gaps == 0
        assert r.aligned_count == 0
        assert r.misaligned_count == 0
        assert r.avg_alignment_score == 0.0
        assert r.by_status == {}
        assert r.by_dimension == {}
        assert r.by_severity == {}
        assert r.critical_misalignments == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_alignment
# -------------------------------------------------------------------


class TestRecordAlignment:
    def test_basic(self):
        eng = _engine()
        r = eng.record_alignment(
            "svc-payments",
            status=AlignmentStatus.ALIGNED,
            dimension=AlignmentDimension.LATENCY,
            alignment_score=95.0,
        )
        assert r.service == "svc-payments"
        assert r.status == AlignmentStatus.ALIGNED
        assert r.alignment_score == 95.0

    def test_dependency_stored(self):
        eng = _engine()
        r = eng.record_alignment("svc-a", dependency="svc-b")
        assert r.dependency == "svc-b"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_alignment(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_alignment
# -------------------------------------------------------------------


class TestGetAlignment:
    def test_found(self):
        eng = _engine()
        r = eng.record_alignment("svc-a")
        assert eng.get_alignment(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_alignment("nonexistent") is None


# -------------------------------------------------------------------
# list_alignments
# -------------------------------------------------------------------


class TestListAlignments:
    def test_list_all(self):
        eng = _engine()
        eng.record_alignment("svc-a")
        eng.record_alignment("svc-b")
        assert len(eng.list_alignments()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_alignment("svc-a", status=AlignmentStatus.MISALIGNED)
        eng.record_alignment("svc-b", status=AlignmentStatus.ALIGNED)
        results = eng.list_alignments(status=AlignmentStatus.MISALIGNED)
        assert len(results) == 1

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_alignment("svc-a", dimension=AlignmentDimension.LATENCY)
        eng.record_alignment("svc-b", dimension=AlignmentDimension.ERROR_RATE)
        results = eng.list_alignments(dimension=AlignmentDimension.LATENCY)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_alignment("svc-a")
        eng.record_alignment("svc-b")
        results = eng.list_alignments(service="svc-a")
        assert len(results) == 1


# -------------------------------------------------------------------
# add_gap
# -------------------------------------------------------------------


class TestAddGap:
    def test_basic(self):
        eng = _engine()
        g = eng.add_gap(
            "record-id-1",
            service="svc-a",
            gap_description="latency SLO gap",
            severity=AlignmentSeverity.HIGH,
        )
        assert g.record_id == "record-id-1"
        assert g.service == "svc-a"
        assert g.severity == AlignmentSeverity.HIGH

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_gap(f"rec-{i}")
        assert len(eng._gaps) == 2


# -------------------------------------------------------------------
# analyze_alignment_by_service
# -------------------------------------------------------------------


class TestAnalyzeAlignmentByService:
    def test_groups_by_service(self):
        eng = _engine()
        eng.record_alignment("svc-a", alignment_score=90.0)
        eng.record_alignment("svc-a", alignment_score=80.0)
        eng.record_alignment("svc-b", alignment_score=50.0)
        results = eng.analyze_alignment_by_service()
        svcs = {r["service"] for r in results}
        assert "svc-a" in svcs and "svc-b" in svcs

    def test_sorted_desc(self):
        eng = _engine()
        eng.record_alignment("svc-a", alignment_score=90.0)
        eng.record_alignment("svc-b", alignment_score=30.0)
        results = eng.analyze_alignment_by_service()
        assert results[0]["avg_alignment_score"] >= results[-1]["avg_alignment_score"]

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_alignment_by_service() == []


# -------------------------------------------------------------------
# identify_misaligned_services
# -------------------------------------------------------------------


class TestIdentifyMisalignedServices:
    def test_finds_misaligned(self):
        eng = _engine()
        eng.record_alignment("svc-a", status=AlignmentStatus.MISALIGNED)
        eng.record_alignment("svc-a", status=AlignmentStatus.CONFLICTING)
        eng.record_alignment("svc-b", status=AlignmentStatus.ALIGNED)
        results = eng.identify_misaligned_services()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_empty_when_all_aligned(self):
        eng = _engine()
        eng.record_alignment("svc-a", status=AlignmentStatus.ALIGNED)
        assert eng.identify_misaligned_services() == []

    def test_empty_no_records(self):
        eng = _engine()
        assert eng.identify_misaligned_services() == []


# -------------------------------------------------------------------
# rank_by_alignment_score
# -------------------------------------------------------------------


class TestRankByAlignmentScore:
    def test_worst_first(self):
        eng = _engine()
        eng.record_alignment("svc-good", alignment_score=95.0)
        eng.record_alignment("svc-bad", alignment_score=20.0)
        results = eng.rank_by_alignment_score()
        assert results[0]["service"] == "svc-bad"

    def test_averages_correctly(self):
        eng = _engine()
        eng.record_alignment("svc-a", alignment_score=60.0)
        eng.record_alignment("svc-a", alignment_score=80.0)
        results = eng.rank_by_alignment_score()
        assert results[0]["avg_alignment_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_alignment_score() == []


# -------------------------------------------------------------------
# detect_alignment_trends
# -------------------------------------------------------------------


class TestDetectAlignmentTrends:
    def test_detects_improving(self):
        eng = _engine()
        for _ in range(3):
            eng.record_alignment("svc-a", alignment_score=30.0)
        for _ in range(3):
            eng.record_alignment("svc-a", alignment_score=90.0)
        results = eng.detect_alignment_trends()
        assert len(results) == 1
        assert results[0]["trend"] == "improving"

    def test_no_trend_below_delta(self):
        eng = _engine()
        for _ in range(4):
            eng.record_alignment("svc-a", alignment_score=80.0)
        results = eng.detect_alignment_trends()
        assert results == []

    def test_too_few_records(self):
        eng = _engine()
        eng.record_alignment("svc-a")
        assert eng.detect_alignment_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_alignment_score=80.0)
        eng.record_alignment(
            "svc-a",
            status=AlignmentStatus.MISALIGNED,
            alignment_score=40.0,
            severity=AlignmentSeverity.CRITICAL,
        )
        eng.record_alignment("svc-b", status=AlignmentStatus.ALIGNED, alignment_score=95.0)
        eng.add_gap("rec-1", service="svc-a")
        report = eng.generate_report()
        assert isinstance(report, SLOAlignmentReport)
        assert report.total_records == 2
        assert report.total_gaps == 1
        assert report.misaligned_count == 1
        assert report.aligned_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "acceptable" in report.recommendations[0]

    def test_critical_misalignments_listed(self):
        eng = _engine()
        eng.record_alignment("svc-critical", severity=AlignmentSeverity.CRITICAL)
        report = eng.generate_report()
        assert "svc-critical" in report.critical_misalignments


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_alignment("svc-a")
        eng.add_gap("rec-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._gaps) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_gaps"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_alignment("svc-a", status=AlignmentStatus.ALIGNED)
        eng.record_alignment("svc-b", status=AlignmentStatus.MISALIGNED)
        eng.add_gap("rec-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_gaps"] == 1
        assert stats["unique_services"] == 2
