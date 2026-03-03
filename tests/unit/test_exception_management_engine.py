"""Tests for shieldops.compliance.exception_management_engine — ExceptionManagementEngine."""

from __future__ import annotations

from shieldops.compliance.exception_management_engine import (
    ApprovalLevel,
    ExceptionAnalysis,
    ExceptionManagementEngine,
    ExceptionManagementReport,
    ExceptionRecord,
    ExceptionStatus,
    ExceptionType,
)


def _engine(**kw) -> ExceptionManagementEngine:
    return ExceptionManagementEngine(**kw)


class TestEnums:
    def test_type_risk_acceptance(self):
        assert ExceptionType.RISK_ACCEPTANCE == "risk_acceptance"

    def test_type_compensating_control(self):
        assert ExceptionType.COMPENSATING_CONTROL == "compensating_control"

    def test_type_temporary_waiver(self):
        assert ExceptionType.TEMPORARY_WAIVER == "temporary_waiver"

    def test_type_permanent_exemption(self):
        assert ExceptionType.PERMANENT_EXEMPTION == "permanent_exemption"

    def test_type_deferred_remediation(self):
        assert ExceptionType.DEFERRED_REMEDIATION == "deferred_remediation"

    def test_status_requested(self):
        assert ExceptionStatus.REQUESTED == "requested"

    def test_status_approved(self):
        assert ExceptionStatus.APPROVED == "approved"

    def test_status_active(self):
        assert ExceptionStatus.ACTIVE == "active"

    def test_status_expired(self):
        assert ExceptionStatus.EXPIRED == "expired"

    def test_status_revoked(self):
        assert ExceptionStatus.REVOKED == "revoked"

    def test_approval_ciso(self):
        assert ApprovalLevel.CISO == "ciso"

    def test_approval_security_lead(self):
        assert ApprovalLevel.SECURITY_LEAD == "security_lead"

    def test_approval_manager(self):
        assert ApprovalLevel.MANAGER == "manager"

    def test_approval_automated(self):
        assert ApprovalLevel.AUTOMATED == "automated"

    def test_approval_committee(self):
        assert ApprovalLevel.COMMITTEE == "committee"


class TestModels:
    def test_record_defaults(self):
        r = ExceptionRecord()
        assert r.id
        assert r.exception_name == ""
        assert r.exception_type == ExceptionType.RISK_ACCEPTANCE
        assert r.exception_status == ExceptionStatus.REQUESTED
        assert r.approval_level == ApprovalLevel.CISO
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ExceptionAnalysis()
        assert a.id
        assert a.exception_name == ""
        assert a.exception_type == ExceptionType.RISK_ACCEPTANCE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ExceptionManagementReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_risk_score == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_approval == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_exception(
            exception_name="legacy-system-exception",
            exception_type=ExceptionType.COMPENSATING_CONTROL,
            exception_status=ExceptionStatus.APPROVED,
            approval_level=ApprovalLevel.SECURITY_LEAD,
            risk_score=85.0,
            service="grc-svc",
            team="compliance",
        )
        assert r.exception_name == "legacy-system-exception"
        assert r.exception_type == ExceptionType.COMPENSATING_CONTROL
        assert r.risk_score == 85.0
        assert r.service == "grc-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_exception(exception_name=f"exc-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_exception(exception_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_exception(exception_name="a")
        eng.record_exception(exception_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_exception_type(self):
        eng = _engine()
        eng.record_exception(exception_name="a", exception_type=ExceptionType.RISK_ACCEPTANCE)
        eng.record_exception(exception_name="b", exception_type=ExceptionType.TEMPORARY_WAIVER)
        assert len(eng.list_records(exception_type=ExceptionType.RISK_ACCEPTANCE)) == 1

    def test_filter_by_exception_status(self):
        eng = _engine()
        eng.record_exception(exception_name="a", exception_status=ExceptionStatus.REQUESTED)
        eng.record_exception(exception_name="b", exception_status=ExceptionStatus.APPROVED)
        assert len(eng.list_records(exception_status=ExceptionStatus.REQUESTED)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_exception(exception_name="a", team="sec")
        eng.record_exception(exception_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_exception(exception_name=f"e-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            exception_name="test",
            analysis_score=88.5,
            breached=True,
            description="exception risk",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(exception_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_exception(
            exception_name="a",
            exception_type=ExceptionType.RISK_ACCEPTANCE,
            risk_score=90.0,
        )
        eng.record_exception(
            exception_name="b",
            exception_type=ExceptionType.RISK_ACCEPTANCE,
            risk_score=70.0,
        )
        result = eng.analyze_distribution()
        assert "risk_acceptance" in result
        assert result["risk_acceptance"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_exception(exception_name="a", risk_score=60.0)
        eng.record_exception(exception_name="b", risk_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_exception(exception_name="a", risk_score=50.0)
        eng.record_exception(exception_name="b", risk_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_exception(exception_name="a", service="auth", risk_score=90.0)
        eng.record_exception(exception_name="b", service="api", risk_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(exception_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(exception_name="a", analysis_score=20.0)
        eng.add_analysis(exception_name="b", analysis_score=20.0)
        eng.add_analysis(exception_name="c", analysis_score=80.0)
        eng.add_analysis(exception_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_exception(exception_name="test", risk_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_exception(exception_name="test")
        eng.add_analysis(exception_name="test")
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
        eng.record_exception(exception_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
