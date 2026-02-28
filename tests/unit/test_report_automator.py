"""Tests for shieldops.compliance.report_automator — ComplianceReportAutomator."""

from __future__ import annotations

from shieldops.compliance.report_automator import (
    ComplianceReportAutomator,
    ReportAutomatorReport,
    ReportFrequency,
    ReportRecord,
    ReportSection,
    ReportStatus,
    ReportType,
)


def _engine(**kw) -> ComplianceReportAutomator:
    return ComplianceReportAutomator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ReportType (5)
    def test_type_soc2_audit(self):
        assert ReportType.SOC2_AUDIT == "soc2_audit"

    def test_type_hipaa_assessment(self):
        assert ReportType.HIPAA_ASSESSMENT == "hipaa_assessment"

    def test_type_pci_dss_review(self):
        assert ReportType.PCI_DSS_REVIEW == "pci_dss_review"

    def test_type_iso27001_audit(self):
        assert ReportType.ISO27001_AUDIT == "iso27001_audit"

    def test_type_gdpr_compliance(self):
        assert ReportType.GDPR_COMPLIANCE == "gdpr_compliance"

    # ReportStatus (5)
    def test_status_draft(self):
        assert ReportStatus.DRAFT == "draft"

    def test_status_in_review(self):
        assert ReportStatus.IN_REVIEW == "in_review"

    def test_status_approved(self):
        assert ReportStatus.APPROVED == "approved"

    def test_status_published(self):
        assert ReportStatus.PUBLISHED == "published"

    def test_status_archived(self):
        assert ReportStatus.ARCHIVED == "archived"

    # ReportFrequency (5)
    def test_frequency_weekly(self):
        assert ReportFrequency.WEEKLY == "weekly"

    def test_frequency_monthly(self):
        assert ReportFrequency.MONTHLY == "monthly"

    def test_frequency_quarterly(self):
        assert ReportFrequency.QUARTERLY == "quarterly"

    def test_frequency_annually(self):
        assert ReportFrequency.ANNUALLY == "annually"

    def test_frequency_on_demand(self):
        assert ReportFrequency.ON_DEMAND == "on_demand"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_report_record_defaults(self):
        r = ReportRecord()
        assert r.id
        assert r.report_name == ""
        assert r.report_type == ReportType.SOC2_AUDIT
        assert r.status == ReportStatus.DRAFT
        assert r.completion_score == 0.0
        assert r.frequency == ReportFrequency.QUARTERLY
        assert r.details == ""
        assert r.created_at > 0

    def test_report_section_defaults(self):
        r = ReportSection()
        assert r.id
        assert r.section_name == ""
        assert r.report_type == ReportType.SOC2_AUDIT
        assert r.status == ReportStatus.DRAFT
        assert r.completion_score == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_report_automator_report_defaults(self):
        r = ReportAutomatorReport()
        assert r.total_reports == 0
        assert r.total_sections == 0
        assert r.avg_completion_score_pct == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.overdue_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_report
# -------------------------------------------------------------------


class TestRecordReport:
    def test_basic(self):
        eng = _engine()
        r = eng.record_report(
            "soc2-2025",
            report_type=ReportType.SOC2_AUDIT,
            status=ReportStatus.DRAFT,
            completion_score=50.0,
            frequency=ReportFrequency.ANNUALLY,
            details="annual audit",
        )
        assert r.report_name == "soc2-2025"
        assert r.completion_score == 50.0
        assert r.id

    def test_stored(self):
        eng = _engine()
        eng.record_report("soc2-2025")
        assert len(eng._records) == 1

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_report(f"report-{i}")
        assert len(eng._records) == 2

    def test_multiple_types(self):
        eng = _engine()
        eng.record_report("soc2", report_type=ReportType.SOC2_AUDIT)
        eng.record_report("hipaa", report_type=ReportType.HIPAA_ASSESSMENT)
        assert len(eng._records) == 2


# -------------------------------------------------------------------
# get_report
# -------------------------------------------------------------------


class TestGetReport:
    def test_found(self):
        eng = _engine()
        r = eng.record_report("soc2-2025")
        result = eng.get_report(r.id)
        assert result is not None
        assert result.id == r.id

    def test_not_found(self):
        eng = _engine()
        assert eng.get_report("nonexistent") is None


# -------------------------------------------------------------------
# list_reports
# -------------------------------------------------------------------


class TestListReports:
    def test_list_all(self):
        eng = _engine()
        eng.record_report("soc2-2025")
        eng.record_report("hipaa-2025")
        assert len(eng.list_reports()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_report("soc2-2025", report_type=ReportType.SOC2_AUDIT)
        eng.record_report("hipaa-2025", report_type=ReportType.HIPAA_ASSESSMENT)
        results = eng.list_reports(report_type=ReportType.SOC2_AUDIT)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_report("soc2-2025", status=ReportStatus.DRAFT)
        eng.record_report("hipaa-2025", status=ReportStatus.APPROVED)
        results = eng.list_reports(status=ReportStatus.DRAFT)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_section
# -------------------------------------------------------------------


class TestAddSection:
    def test_basic(self):
        eng = _engine()
        s = eng.add_section(
            "access-controls",
            report_type=ReportType.SOC2_AUDIT,
            status=ReportStatus.IN_REVIEW,
            completion_score=75.0,
            description="CC6 access controls section",
        )
        assert s.section_name == "access-controls"
        assert s.completion_score == 75.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_section(f"section-{i}")
        assert len(eng._sections) == 2


# -------------------------------------------------------------------
# analyze_report_by_type
# -------------------------------------------------------------------


class TestAnalyzeReportByType:
    def test_with_data(self):
        eng = _engine()
        eng.record_report("soc2-q1", report_type=ReportType.SOC2_AUDIT, completion_score=80.0)
        eng.record_report("soc2-q2", report_type=ReportType.SOC2_AUDIT, completion_score=60.0)
        result = eng.analyze_report_by_type(ReportType.SOC2_AUDIT)
        assert result["report_type"] == "soc2_audit"
        assert result["total_records"] == 2
        assert result["avg_completion_score"] == 70.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_report_by_type(ReportType.HIPAA_ASSESSMENT)
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_overdue_reports
# -------------------------------------------------------------------


class TestIdentifyOverdueReports:
    def test_with_overdue(self):
        eng = _engine()
        eng.record_report("soc2-q1", status=ReportStatus.DRAFT)
        eng.record_report("soc2-q1", status=ReportStatus.IN_REVIEW)
        eng.record_report("hipaa-q1", status=ReportStatus.APPROVED)
        results = eng.identify_overdue_reports()
        assert len(results) == 1
        assert results[0]["report_name"] == "soc2-q1"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_overdue_reports() == []


# -------------------------------------------------------------------
# rank_by_completion_score
# -------------------------------------------------------------------


class TestRankByCompletionScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_report("soc2-q1", report_type=ReportType.SOC2_AUDIT, completion_score=90.0)
        eng.record_report("soc2-q2", report_type=ReportType.SOC2_AUDIT, completion_score=80.0)
        eng.record_report(
            "hipaa-q1", report_type=ReportType.HIPAA_ASSESSMENT, completion_score=30.0
        )
        results = eng.rank_by_completion_score()
        assert results[0]["report_type"] == "soc2_audit"
        assert results[0]["avg_completion_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_completion_score() == []


# -------------------------------------------------------------------
# detect_reporting_gaps
# -------------------------------------------------------------------


class TestDetectReportingGaps:
    def test_with_gaps(self):
        eng = _engine()
        for _ in range(5):
            eng.record_report("soc2", report_type=ReportType.SOC2_AUDIT)
        eng.record_report("hipaa", report_type=ReportType.HIPAA_ASSESSMENT)
        results = eng.detect_reporting_gaps()
        assert len(results) == 1
        assert results[0]["report_type"] == "soc2_audit"
        assert results[0]["gap_detected"] is True

    def test_no_gaps(self):
        eng = _engine()
        eng.record_report("soc2")
        assert eng.detect_reporting_gaps() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_report("soc2-q1", status=ReportStatus.DRAFT, completion_score=50.0)
        eng.record_report("hipaa-q1", status=ReportStatus.APPROVED, completion_score=90.0)
        eng.add_section("section-1")
        report = eng.generate_report()
        assert report.total_reports == 2
        assert report.total_sections == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_reports == 0
        assert "within acceptable" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_report("soc2-q1")
        eng.add_section("section-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._sections) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_reports"] == 0
        assert stats["total_sections"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_report("soc2-q1", report_type=ReportType.SOC2_AUDIT)
        eng.record_report("hipaa-q1", report_type=ReportType.HIPAA_ASSESSMENT)
        eng.add_section("section-1")
        stats = eng.get_stats()
        assert stats["total_reports"] == 2
        assert stats["total_sections"] == 1
        assert stats["unique_report_names"] == 2
