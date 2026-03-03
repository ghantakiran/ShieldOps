"""Tests for shieldops.security.saas_security_posture_monitor — SaaSSecurityPostureMonitor."""

from __future__ import annotations

from shieldops.security.saas_security_posture_monitor import (
    PostureArea,
    PostureGrade,
    SaaSCategory,
    SaaSPostureAnalysis,
    SaaSPostureRecord,
    SaaSSecurityPostureMonitor,
    SaaSSecurityPostureReport,
)


def _engine(**kw) -> SaaSSecurityPostureMonitor:
    return SaaSSecurityPostureMonitor(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert SaaSCategory.COLLABORATION == "collaboration"

    def test_e1_v2(self):
        assert SaaSCategory.CRM == "crm"

    def test_e1_v3(self):
        assert SaaSCategory.DEVELOPMENT == "development"

    def test_e1_v4(self):
        assert SaaSCategory.SECURITY == "security"

    def test_e1_v5(self):
        assert SaaSCategory.INFRASTRUCTURE == "infrastructure"

    def test_e2_v1(self):
        assert PostureArea.AUTHENTICATION == "authentication"

    def test_e2_v2(self):
        assert PostureArea.AUTHORIZATION == "authorization"

    def test_e2_v3(self):
        assert PostureArea.DATA_PROTECTION == "data_protection"

    def test_e2_v4(self):
        assert PostureArea.LOGGING == "logging"

    def test_e2_v5(self):
        assert PostureArea.INTEGRATION == "integration"

    def test_e3_v1(self):
        assert PostureGrade.A_EXCELLENT == "a_excellent"

    def test_e3_v2(self):
        assert PostureGrade.B_GOOD == "b_good"

    def test_e3_v3(self):
        assert PostureGrade.C_FAIR == "c_fair"

    def test_e3_v4(self):
        assert PostureGrade.D_POOR == "d_poor"

    def test_e3_v5(self):
        assert PostureGrade.F_CRITICAL == "f_critical"


class TestModels:
    def test_rec(self):
        r = SaaSPostureRecord()
        assert r.id and r.posture_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = SaaSPostureAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = SaaSSecurityPostureReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_posture(
            posture_id="t",
            saas_category=SaaSCategory.CRM,
            posture_area=PostureArea.AUTHORIZATION,
            posture_grade=PostureGrade.B_GOOD,
            posture_score=92.0,
            service="s",
            team="t",
        )
        assert r.posture_id == "t" and r.posture_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_posture(posture_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_posture(posture_id="t")
        assert eng.get_posture(r.id) is not None

    def test_not_found(self):
        assert _engine().get_posture("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_posture(posture_id="a")
        eng.record_posture(posture_id="b")
        assert len(eng.list_postures()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_posture(posture_id="a", saas_category=SaaSCategory.COLLABORATION)
        eng.record_posture(posture_id="b", saas_category=SaaSCategory.CRM)
        assert len(eng.list_postures(saas_category=SaaSCategory.COLLABORATION)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_posture(posture_id="a", posture_area=PostureArea.AUTHENTICATION)
        eng.record_posture(posture_id="b", posture_area=PostureArea.AUTHORIZATION)
        assert len(eng.list_postures(posture_area=PostureArea.AUTHENTICATION)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_posture(posture_id="a", team="x")
        eng.record_posture(posture_id="b", team="y")
        assert len(eng.list_postures(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_posture(posture_id=f"t-{i}")
        assert len(eng.list_postures(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            posture_id="t", saas_category=SaaSCategory.CRM, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(posture_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_posture(
            posture_id="a", saas_category=SaaSCategory.COLLABORATION, posture_score=90.0
        )
        eng.record_posture(
            posture_id="b", saas_category=SaaSCategory.COLLABORATION, posture_score=70.0
        )
        assert "collaboration" in eng.analyze_posture_distribution()

    def test_empty(self):
        assert _engine().analyze_posture_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(posture_gap_threshold=80.0)
        eng.record_posture(posture_id="a", posture_score=60.0)
        eng.record_posture(posture_id="b", posture_score=90.0)
        assert len(eng.identify_posture_gaps()) == 1

    def test_sorted(self):
        eng = _engine(posture_gap_threshold=80.0)
        eng.record_posture(posture_id="a", posture_score=50.0)
        eng.record_posture(posture_id="b", posture_score=30.0)
        assert len(eng.identify_posture_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_posture(posture_id="a", service="s1", posture_score=80.0)
        eng.record_posture(posture_id="b", service="s2", posture_score=60.0)
        assert eng.rank_by_posture()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_posture() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(posture_id="t", analysis_score=float(v))
        assert eng.detect_posture_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(posture_id="t", analysis_score=float(v))
        assert eng.detect_posture_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_posture_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_posture(posture_id="t", posture_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_posture(posture_id="t")
        eng.add_analysis(posture_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_posture(posture_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_posture(posture_id="a")
        eng.record_posture(posture_id="b")
        eng.add_analysis(posture_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
