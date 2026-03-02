"""Tests for shieldops.security.security_case_manager — SecurityCaseManager."""

from __future__ import annotations

from shieldops.security.security_case_manager import (
    CaseAnalysis,
    CasePriority,
    CaseRecord,
    CaseReport,
    CaseStatus,
    CaseType,
    SecurityCaseManager,
)


def _engine(**kw) -> SecurityCaseManager:
    return SecurityCaseManager(**kw)


class TestEnums:
    def test_casetype_val1(self):
        assert CaseType.INCIDENT == "incident"

    def test_casetype_val2(self):
        assert CaseType.INVESTIGATION == "investigation"

    def test_casetype_val3(self):
        assert CaseType.THREAT_HUNT == "threat_hunt"

    def test_casetype_val4(self):
        assert CaseType.COMPLIANCE == "compliance"

    def test_casetype_val5(self):
        assert CaseType.VULNERABILITY == "vulnerability"

    def test_casestatus_val1(self):
        assert CaseStatus.OPEN == "open"

    def test_casestatus_val2(self):
        assert CaseStatus.IN_PROGRESS == "in_progress"

    def test_casestatus_val3(self):
        assert CaseStatus.PENDING_REVIEW == "pending_review"

    def test_casestatus_val4(self):
        assert CaseStatus.CLOSED == "closed"

    def test_casestatus_val5(self):
        assert CaseStatus.ARCHIVED == "archived"

    def test_casepriority_val1(self):
        assert CasePriority.CRITICAL == "critical"

    def test_casepriority_val2(self):
        assert CasePriority.HIGH == "high"

    def test_casepriority_val3(self):
        assert CasePriority.MEDIUM == "medium"

    def test_casepriority_val4(self):
        assert CasePriority.LOW == "low"

    def test_casepriority_val5(self):
        assert CasePriority.INFORMATIONAL == "informational"


class TestModels:
    def test_record_defaults(self):
        r = CaseRecord()
        assert r.id
        assert r.case_name == ""

    def test_analysis_defaults(self):
        a = CaseAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = CaseReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_case(
            case_name="test",
            case_type=CaseType.INVESTIGATION,
            resolution_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.case_name == "test"
        assert r.resolution_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_case(case_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_case(case_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_case(case_name="a")
        eng.record_case(case_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_case(case_name="a", case_type=CaseType.INCIDENT)
        eng.record_case(case_name="b", case_type=CaseType.INVESTIGATION)
        assert len(eng.list_records(case_type=CaseType.INCIDENT)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_case(case_name="a", case_status=CaseStatus.OPEN)
        eng.record_case(case_name="b", case_status=CaseStatus.IN_PROGRESS)
        assert len(eng.list_records(case_status=CaseStatus.OPEN)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_case(case_name="a", team="sec")
        eng.record_case(case_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_case(case_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            case_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(case_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_case(case_name="a", case_type=CaseType.INCIDENT, resolution_score=90.0)
        eng.record_case(case_name="b", case_type=CaseType.INCIDENT, resolution_score=70.0)
        result = eng.analyze_distribution()
        assert CaseType.INCIDENT.value in result
        assert result[CaseType.INCIDENT.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_case(case_name="a", resolution_score=60.0)
        eng.record_case(case_name="b", resolution_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_case(case_name="a", resolution_score=50.0)
        eng.record_case(case_name="b", resolution_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["resolution_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_case(case_name="a", service="auth", resolution_score=90.0)
        eng.record_case(case_name="b", service="api", resolution_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(case_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(case_name="a", analysis_score=20.0)
        eng.add_analysis(case_name="b", analysis_score=20.0)
        eng.add_analysis(case_name="c", analysis_score=80.0)
        eng.add_analysis(case_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_case(case_name="test", resolution_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_case(case_name="test")
        eng.add_analysis(case_name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_case(case_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
