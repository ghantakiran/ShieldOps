"""Tests for shieldops.operations.runbook_compliance — RunbookComplianceChecker."""

from __future__ import annotations

from shieldops.operations.runbook_compliance import (
    CheckStatus,
    ComplianceArea,
    ComplianceCheckRecord,
    ComplianceGrade,
    ComplianceStandard,
    RunbookComplianceChecker,
    RunbookComplianceReport,
)


def _engine(**kw) -> RunbookComplianceChecker:
    return RunbookComplianceChecker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_area_documentation(self):
        assert ComplianceArea.DOCUMENTATION == "documentation"

    def test_area_testing(self):
        assert ComplianceArea.TESTING == "testing"

    def test_area_approval(self):
        assert ComplianceArea.APPROVAL == "approval"

    def test_area_versioning(self):
        assert ComplianceArea.VERSIONING == "versioning"

    def test_area_review(self):
        assert ComplianceArea.REVIEW == "review"

    def test_grade_a(self):
        assert ComplianceGrade.A == "a"

    def test_grade_b(self):
        assert ComplianceGrade.B == "b"

    def test_grade_c(self):
        assert ComplianceGrade.C == "c"

    def test_grade_d(self):
        assert ComplianceGrade.D == "d"

    def test_grade_f(self):
        assert ComplianceGrade.F == "f"

    def test_status_passed(self):
        assert CheckStatus.PASSED == "passed"

    def test_status_failed(self):
        assert CheckStatus.FAILED == "failed"

    def test_status_skipped(self):
        assert CheckStatus.SKIPPED == "skipped"

    def test_status_pending(self):
        assert CheckStatus.PENDING == "pending"

    def test_status_waived(self):
        assert CheckStatus.WAIVED == "waived"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_compliance_check_record_defaults(self):
        r = ComplianceCheckRecord()
        assert r.id
        assert r.runbook_id == ""
        assert r.compliance_area == ComplianceArea.DOCUMENTATION
        assert r.compliance_grade == ComplianceGrade.F
        assert r.check_status == CheckStatus.PENDING
        assert r.score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_compliance_standard_defaults(self):
        s = ComplianceStandard()
        assert s.id
        assert s.standard_name == ""
        assert s.compliance_area == ComplianceArea.DOCUMENTATION
        assert s.required_score == 0.0
        assert s.mandatory is True
        assert s.description == ""
        assert s.created_at > 0

    def test_runbook_compliance_report_defaults(self):
        r = RunbookComplianceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_standards == 0
        assert r.passing_count == 0
        assert r.avg_score == 0.0
        assert r.by_area == {}
        assert r.by_grade == {}
        assert r.by_status == {}
        assert r.failing_runbooks == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_check
# ---------------------------------------------------------------------------


class TestRecordCheck:
    def test_basic(self):
        eng = _engine()
        r = eng.record_check(
            runbook_id="RB-001",
            compliance_area=ComplianceArea.TESTING,
            compliance_grade=ComplianceGrade.A,
            check_status=CheckStatus.PASSED,
            score=95.0,
            team="sre",
        )
        assert r.runbook_id == "RB-001"
        assert r.compliance_area == ComplianceArea.TESTING
        assert r.compliance_grade == ComplianceGrade.A
        assert r.check_status == CheckStatus.PASSED
        assert r.score == 95.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_check(runbook_id=f"RB-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_check
# ---------------------------------------------------------------------------


class TestGetCheck:
    def test_found(self):
        eng = _engine()
        r = eng.record_check(
            runbook_id="RB-001",
            compliance_grade=ComplianceGrade.B,
        )
        result = eng.get_check(r.id)
        assert result is not None
        assert result.compliance_grade == ComplianceGrade.B

    def test_not_found(self):
        eng = _engine()
        assert eng.get_check("nonexistent") is None


# ---------------------------------------------------------------------------
# list_checks
# ---------------------------------------------------------------------------


class TestListChecks:
    def test_list_all(self):
        eng = _engine()
        eng.record_check(runbook_id="RB-001")
        eng.record_check(runbook_id="RB-002")
        assert len(eng.list_checks()) == 2

    def test_filter_by_area(self):
        eng = _engine()
        eng.record_check(
            runbook_id="RB-001",
            compliance_area=ComplianceArea.TESTING,
        )
        eng.record_check(
            runbook_id="RB-002",
            compliance_area=ComplianceArea.APPROVAL,
        )
        results = eng.list_checks(area=ComplianceArea.TESTING)
        assert len(results) == 1

    def test_filter_by_grade(self):
        eng = _engine()
        eng.record_check(
            runbook_id="RB-001",
            compliance_grade=ComplianceGrade.A,
        )
        eng.record_check(
            runbook_id="RB-002",
            compliance_grade=ComplianceGrade.D,
        )
        results = eng.list_checks(grade=ComplianceGrade.A)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_check(runbook_id="RB-001", team="sre")
        eng.record_check(runbook_id="RB-002", team="platform")
        results = eng.list_checks(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_check(runbook_id=f"RB-{i}")
        assert len(eng.list_checks(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_standard
# ---------------------------------------------------------------------------


class TestAddStandard:
    def test_basic(self):
        eng = _engine()
        s = eng.add_standard(
            standard_name="doc-completeness",
            compliance_area=ComplianceArea.DOCUMENTATION,
            required_score=80.0,
            mandatory=True,
            description="All runbooks must have complete documentation",
        )
        assert s.standard_name == "doc-completeness"
        assert s.compliance_area == ComplianceArea.DOCUMENTATION
        assert s.required_score == 80.0
        assert s.mandatory is True
        assert s.description == "All runbooks must have complete documentation"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_standard(standard_name=f"std-{i}")
        assert len(eng._standards) == 2


# ---------------------------------------------------------------------------
# analyze_compliance_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeComplianceDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_check(
            runbook_id="RB-001",
            compliance_area=ComplianceArea.TESTING,
            score=90.0,
        )
        eng.record_check(
            runbook_id="RB-002",
            compliance_area=ComplianceArea.TESTING,
            score=80.0,
        )
        result = eng.analyze_compliance_distribution()
        assert "testing" in result
        assert result["testing"]["count"] == 2
        assert result["testing"]["avg_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_compliance_distribution() == {}


# ---------------------------------------------------------------------------
# identify_failing_runbooks
# ---------------------------------------------------------------------------


class TestIdentifyFailingRunbooks:
    def test_detects_failed(self):
        eng = _engine()
        eng.record_check(
            runbook_id="RB-001",
            check_status=CheckStatus.FAILED,
        )
        eng.record_check(
            runbook_id="RB-002",
            check_status=CheckStatus.PASSED,
        )
        results = eng.identify_failing_runbooks()
        assert len(results) == 1
        assert results[0]["runbook_id"] == "RB-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failing_runbooks() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_check(runbook_id="RB-001", team="sre", score=90.0)
        eng.record_check(runbook_id="RB-002", team="sre", score=80.0)
        eng.record_check(runbook_id="RB-003", team="platform", score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["team"] == "platform"
        assert results[0]["avg_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_compliance_trends
# ---------------------------------------------------------------------------


class TestDetectComplianceTrends:
    def test_stable(self):
        eng = _engine()
        for score in [80.0, 80.0, 80.0, 80.0]:
            eng.add_standard(standard_name="s", required_score=score)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for score in [60.0, 60.0, 90.0, 90.0]:
            eng.add_standard(standard_name="s", required_score=score)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_compliance_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_check(
            runbook_id="RB-001",
            compliance_area=ComplianceArea.TESTING,
            check_status=CheckStatus.FAILED,
            score=40.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, RunbookComplianceReport)
        assert report.total_records == 1
        assert report.passing_count == 0
        assert report.avg_score == 40.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_check(runbook_id="RB-001")
        eng.add_standard(standard_name="s1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._standards) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_standards"] == 0
        assert stats["area_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_check(
            runbook_id="RB-001",
            compliance_area=ComplianceArea.VERSIONING,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_runbooks"] == 1
        assert "versioning" in stats["area_distribution"]
