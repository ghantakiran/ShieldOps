"""Tests for shieldops.compliance.security_exception_workflow — SecurityExceptionWorkflow."""

from __future__ import annotations

from shieldops.compliance.security_exception_workflow import (
    ApprovalStatus,
    ExceptionAnalysis,
    ExceptionRecord,
    ExceptionRisk,
    ExceptionType,
    SecurityExceptionReport,
    SecurityExceptionWorkflow,
)


def _engine(**kw) -> SecurityExceptionWorkflow:
    return SecurityExceptionWorkflow(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert ExceptionType.POLICY_WAIVER == "policy_waiver"

    def test_e1_v2(self):
        assert ExceptionType.RISK_ACCEPTANCE == "risk_acceptance"

    def test_e1_v3(self):
        assert ExceptionType.TEMPORARY_EXEMPTION == "temporary_exemption"

    def test_e1_v4(self):
        assert ExceptionType.COMPENSATING_CONTROL == "compensating_control"

    def test_e1_v5(self):
        assert ExceptionType.LEGACY_SYSTEM == "legacy_system"

    def test_e2_v1(self):
        assert ApprovalStatus.APPROVED == "approved"

    def test_e2_v2(self):
        assert ApprovalStatus.DENIED == "denied"

    def test_e2_v3(self):
        assert ApprovalStatus.PENDING == "pending"

    def test_e2_v4(self):
        assert ApprovalStatus.EXPIRED == "expired"

    def test_e2_v5(self):
        assert ApprovalStatus.REVOKED == "revoked"

    def test_e3_v1(self):
        assert ExceptionRisk.CRITICAL == "critical"

    def test_e3_v2(self):
        assert ExceptionRisk.HIGH == "high"

    def test_e3_v3(self):
        assert ExceptionRisk.MEDIUM == "medium"

    def test_e3_v4(self):
        assert ExceptionRisk.LOW == "low"

    def test_e3_v5(self):
        assert ExceptionRisk.NEGLIGIBLE == "negligible"


class TestModels:
    def test_rec(self):
        r = ExceptionRecord()
        assert r.id and r.exception_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = ExceptionAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = SecurityExceptionReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_exception(
            exception_id="t",
            exception_type=ExceptionType.RISK_ACCEPTANCE,
            approval_status=ApprovalStatus.DENIED,
            exception_risk=ExceptionRisk.HIGH,
            exception_score=92.0,
            service="s",
            team="t",
        )
        assert r.exception_id == "t" and r.exception_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_exception(exception_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_exception(exception_id="t")
        assert eng.get_exception(r.id) is not None

    def test_not_found(self):
        assert _engine().get_exception("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_exception(exception_id="a")
        eng.record_exception(exception_id="b")
        assert len(eng.list_exceptions()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_exception(exception_id="a", exception_type=ExceptionType.POLICY_WAIVER)
        eng.record_exception(exception_id="b", exception_type=ExceptionType.RISK_ACCEPTANCE)
        assert len(eng.list_exceptions(exception_type=ExceptionType.POLICY_WAIVER)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_exception(exception_id="a", approval_status=ApprovalStatus.APPROVED)
        eng.record_exception(exception_id="b", approval_status=ApprovalStatus.DENIED)
        assert len(eng.list_exceptions(approval_status=ApprovalStatus.APPROVED)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_exception(exception_id="a", team="x")
        eng.record_exception(exception_id="b", team="y")
        assert len(eng.list_exceptions(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_exception(exception_id=f"t-{i}")
        assert len(eng.list_exceptions(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            exception_id="t",
            exception_type=ExceptionType.RISK_ACCEPTANCE,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(exception_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_exception(
            exception_id="a", exception_type=ExceptionType.POLICY_WAIVER, exception_score=90.0
        )
        eng.record_exception(
            exception_id="b", exception_type=ExceptionType.POLICY_WAIVER, exception_score=70.0
        )
        assert "policy_waiver" in eng.analyze_exception_distribution()

    def test_empty(self):
        assert _engine().analyze_exception_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(exception_gap_threshold=80.0)
        eng.record_exception(exception_id="a", exception_score=60.0)
        eng.record_exception(exception_id="b", exception_score=90.0)
        assert len(eng.identify_exception_gaps()) == 1

    def test_sorted(self):
        eng = _engine(exception_gap_threshold=80.0)
        eng.record_exception(exception_id="a", exception_score=50.0)
        eng.record_exception(exception_id="b", exception_score=30.0)
        assert len(eng.identify_exception_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_exception(exception_id="a", service="s1", exception_score=80.0)
        eng.record_exception(exception_id="b", service="s2", exception_score=60.0)
        assert eng.rank_by_exception()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_exception() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(exception_id="t", analysis_score=float(v))
        assert eng.detect_exception_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(exception_id="t", analysis_score=float(v))
        assert eng.detect_exception_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_exception_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_exception(exception_id="t", exception_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_exception(exception_id="t")
        eng.add_analysis(exception_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_exception(exception_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_exception(exception_id="a")
        eng.record_exception(exception_id="b")
        eng.add_analysis(exception_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
