"""Tests for shieldops.audit.audit_readiness — AuditReadinessScorer."""

from __future__ import annotations

from shieldops.audit.audit_readiness import (
    AuditReadinessReport,
    AuditReadinessScorer,
    ReadinessArea,
    ReadinessAssessment,
    ReadinessGap,
    ReadinessGrade,
    ReadinessRecord,
)


def _engine(**kw) -> AuditReadinessScorer:
    return AuditReadinessScorer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ReadinessArea (5)
    def test_area_documentation(self):
        assert ReadinessArea.DOCUMENTATION == "documentation"

    def test_area_evidence_collection(self):
        assert ReadinessArea.EVIDENCE_COLLECTION == "evidence_collection"

    def test_area_control_testing(self):
        assert ReadinessArea.CONTROL_TESTING == "control_testing"

    def test_area_access_review(self):
        assert ReadinessArea.ACCESS_REVIEW == "access_review"

    def test_area_risk_assessment(self):
        assert ReadinessArea.RISK_ASSESSMENT == "risk_assessment"

    # ReadinessGrade (5)
    def test_grade_audit_ready(self):
        assert ReadinessGrade.AUDIT_READY == "audit_ready"

    def test_grade_mostly_ready(self):
        assert ReadinessGrade.MOSTLY_READY == "mostly_ready"

    def test_grade_partially_ready(self):
        assert ReadinessGrade.PARTIALLY_READY == "partially_ready"

    def test_grade_not_ready(self):
        assert ReadinessGrade.NOT_READY == "not_ready"

    def test_grade_critical_gaps(self):
        assert ReadinessGrade.CRITICAL_GAPS == "critical_gaps"

    # ReadinessGap (5)
    def test_gap_missing_evidence(self):
        assert ReadinessGap.MISSING_EVIDENCE == "missing_evidence"

    def test_gap_stale_controls(self):
        assert ReadinessGap.STALE_CONTROLS == "stale_controls"

    def test_gap_incomplete_documentation(self):
        assert ReadinessGap.INCOMPLETE_DOCUMENTATION == "incomplete_documentation"

    def test_gap_untested_controls(self):
        assert ReadinessGap.UNTESTED_CONTROLS == "untested_controls"

    def test_gap_access_issues(self):
        assert ReadinessGap.ACCESS_ISSUES == "access_issues"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_readiness_record_defaults(self):
        r = ReadinessRecord()
        assert r.id
        assert r.area_name == ""
        assert r.area == ReadinessArea.DOCUMENTATION
        assert r.grade == ReadinessGrade.PARTIALLY_READY
        assert r.gap == ReadinessGap.MISSING_EVIDENCE
        assert r.readiness_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_readiness_assessment_defaults(self):
        r = ReadinessAssessment()
        assert r.id
        assert r.area_name == ""
        assert r.area == ReadinessArea.DOCUMENTATION
        assert r.grade == ReadinessGrade.PARTIALLY_READY
        assert r.min_readiness_pct == 80.0
        assert r.review_frequency_days == 30.0
        assert r.created_at > 0

    def test_audit_readiness_report_defaults(self):
        r = AuditReadinessReport()
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.ready_rate_pct == 0.0
        assert r.by_area == {}
        assert r.by_grade == {}
        assert r.critical_gap_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_readiness
# -------------------------------------------------------------------


class TestRecordReadiness:
    def test_basic(self):
        eng = _engine()
        r = eng.record_readiness(
            "doc-area",
            area=ReadinessArea.DOCUMENTATION,
            grade=ReadinessGrade.AUDIT_READY,
        )
        assert r.area_name == "doc-area"
        assert r.area == ReadinessArea.DOCUMENTATION

    def test_with_gap(self):
        eng = _engine()
        r = eng.record_readiness(
            "ctrl-area",
            gap=ReadinessGap.STALE_CONTROLS,
        )
        assert r.gap == ReadinessGap.STALE_CONTROLS

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_readiness(f"area-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_readiness
# -------------------------------------------------------------------


class TestGetReadiness:
    def test_found(self):
        eng = _engine()
        r = eng.record_readiness("area-a")
        assert eng.get_readiness(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_readiness("nonexistent") is None


# -------------------------------------------------------------------
# list_readiness_records
# -------------------------------------------------------------------


class TestListReadinessRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_readiness("area-a")
        eng.record_readiness("area-b")
        assert len(eng.list_readiness_records()) == 2

    def test_filter_by_area_name(self):
        eng = _engine()
        eng.record_readiness("area-a")
        eng.record_readiness("area-b")
        results = eng.list_readiness_records(area_name="area-a")
        assert len(results) == 1

    def test_filter_by_area(self):
        eng = _engine()
        eng.record_readiness("area-a", area=ReadinessArea.DOCUMENTATION)
        eng.record_readiness("area-b", area=ReadinessArea.CONTROL_TESTING)
        results = eng.list_readiness_records(area=ReadinessArea.DOCUMENTATION)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_assessment
# -------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            "doc-assessment",
            area=ReadinessArea.DOCUMENTATION,
            grade=ReadinessGrade.AUDIT_READY,
            min_readiness_pct=85.0,
            review_frequency_days=14.0,
        )
        assert a.area_name == "doc-assessment"
        assert a.min_readiness_pct == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_assessment(f"assessment-{i}")
        assert len(eng._assessments) == 2


# -------------------------------------------------------------------
# analyze_readiness_by_area
# -------------------------------------------------------------------


class TestAnalyzeReadinessByArea:
    def test_with_data(self):
        eng = _engine()
        eng.record_readiness("area-a", grade=ReadinessGrade.AUDIT_READY)
        eng.record_readiness("area-a", grade=ReadinessGrade.NOT_READY)
        result = eng.analyze_readiness_by_area("area-a")
        assert result["area_name"] == "area-a"
        assert result["record_count"] == 2
        assert result["ready_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_readiness_by_area("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_critical_gaps
# -------------------------------------------------------------------


class TestIdentifyCriticalGaps:
    def test_with_gaps(self):
        eng = _engine()
        eng.record_readiness("area-a", grade=ReadinessGrade.NOT_READY)
        eng.record_readiness("area-a", grade=ReadinessGrade.CRITICAL_GAPS)
        eng.record_readiness("area-b", grade=ReadinessGrade.AUDIT_READY)
        results = eng.identify_critical_gaps()
        assert len(results) == 1
        assert results[0]["area_name"] == "area-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_gaps() == []


# -------------------------------------------------------------------
# rank_by_readiness_score
# -------------------------------------------------------------------


class TestRankByReadinessScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_readiness("area-a", readiness_pct=90.0)
        eng.record_readiness("area-a", readiness_pct=80.0)
        eng.record_readiness("area-b", readiness_pct=50.0)
        results = eng.rank_by_readiness_score()
        assert results[0]["area_name"] == "area-a"
        assert results[0]["avg_readiness_pct"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_readiness_score() == []


# -------------------------------------------------------------------
# detect_readiness_trends
# -------------------------------------------------------------------


class TestDetectReadinessTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_readiness("area-a", grade=ReadinessGrade.NOT_READY)
        eng.record_readiness("area-b", grade=ReadinessGrade.AUDIT_READY)
        results = eng.detect_readiness_trends()
        assert len(results) == 1
        assert results[0]["area_name"] == "area-a"
        assert results[0]["trend_detected"] is True

    def test_no_trends(self):
        eng = _engine()
        eng.record_readiness("area-a", grade=ReadinessGrade.NOT_READY)
        assert eng.detect_readiness_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_readiness("area-a", grade=ReadinessGrade.AUDIT_READY)
        eng.record_readiness("area-b", grade=ReadinessGrade.NOT_READY)
        eng.record_readiness("area-b", grade=ReadinessGrade.NOT_READY)
        eng.add_assessment("assessment-1")
        report = eng.generate_report()
        assert report.total_records == 3
        assert report.total_assessments == 1
        assert report.by_area != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_readiness("area-a")
        eng.add_assessment("assessment-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["area_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_readiness("area-a", area=ReadinessArea.DOCUMENTATION)
        eng.record_readiness("area-b", area=ReadinessArea.CONTROL_TESTING)
        eng.add_assessment("assessment-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_assessments"] == 1
        assert stats["unique_areas"] == 2
