"""Tests for shieldops.security.security_control_sla_monitor — SecurityControlSLAMonitor."""

from __future__ import annotations

from shieldops.security.security_control_sla_monitor import (
    ControlCategory,
    ControlSLAAnalysis,
    ControlSLARecord,
    ControlSLAReport,
    SecurityControlSLAMonitor,
    SLAMetric,
    SLAStatus,
)


def _engine(**kw) -> SecurityControlSLAMonitor:
    return SecurityControlSLAMonitor(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert ControlCategory.PREVENTIVE == "preventive"

    def test_e1_v2(self):
        assert ControlCategory.DETECTIVE == "detective"

    def test_e1_v3(self):
        assert ControlCategory.CORRECTIVE == "corrective"

    def test_e1_v4(self):
        assert ControlCategory.DETERRENT == "deterrent"

    def test_e1_v5(self):
        assert ControlCategory.COMPENSATING == "compensating"

    def test_e2_v1(self):
        assert SLAMetric.UPTIME == "uptime"

    def test_e2_v2(self):
        assert SLAMetric.RESPONSE_TIME == "response_time"

    def test_e2_v3(self):
        assert SLAMetric.COVERAGE == "coverage"

    def test_e2_v4(self):
        assert SLAMetric.EFFECTIVENESS == "effectiveness"

    def test_e2_v5(self):
        assert SLAMetric.COMPLIANCE == "compliance"

    def test_e3_v1(self):
        assert SLAStatus.MET == "met"

    def test_e3_v2(self):
        assert SLAStatus.AT_RISK == "at_risk"

    def test_e3_v3(self):
        assert SLAStatus.BREACHED == "breached"

    def test_e3_v4(self):
        assert SLAStatus.EXEMPT == "exempt"

    def test_e3_v5(self):
        assert SLAStatus.NOT_MEASURED == "not_measured"


class TestModels:
    def test_rec(self):
        r = ControlSLARecord()
        assert r.id and r.sla_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = ControlSLAAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = ControlSLAReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_sla(
            sla_id="t",
            control_category=ControlCategory.DETECTIVE,
            sla_metric=SLAMetric.RESPONSE_TIME,
            sla_status=SLAStatus.AT_RISK,
            sla_score=92.0,
            service="s",
            team="t",
        )
        assert r.sla_id == "t" and r.sla_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_sla(sla_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_sla(sla_id="t")
        assert eng.get_sla(r.id) is not None

    def test_not_found(self):
        assert _engine().get_sla("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_sla(sla_id="a")
        eng.record_sla(sla_id="b")
        assert len(eng.list_slas()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_sla(sla_id="a", control_category=ControlCategory.PREVENTIVE)
        eng.record_sla(sla_id="b", control_category=ControlCategory.DETECTIVE)
        assert len(eng.list_slas(control_category=ControlCategory.PREVENTIVE)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_sla(sla_id="a", sla_metric=SLAMetric.UPTIME)
        eng.record_sla(sla_id="b", sla_metric=SLAMetric.RESPONSE_TIME)
        assert len(eng.list_slas(sla_metric=SLAMetric.UPTIME)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_sla(sla_id="a", team="x")
        eng.record_sla(sla_id="b", team="y")
        assert len(eng.list_slas(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_sla(sla_id=f"t-{i}")
        assert len(eng.list_slas(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            sla_id="t",
            control_category=ControlCategory.DETECTIVE,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(sla_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_sla(sla_id="a", control_category=ControlCategory.PREVENTIVE, sla_score=90.0)
        eng.record_sla(sla_id="b", control_category=ControlCategory.PREVENTIVE, sla_score=70.0)
        assert "preventive" in eng.analyze_category_distribution()

    def test_empty(self):
        assert _engine().analyze_category_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(sla_threshold=80.0)
        eng.record_sla(sla_id="a", sla_score=60.0)
        eng.record_sla(sla_id="b", sla_score=90.0)
        assert len(eng.identify_sla_gaps()) == 1

    def test_sorted(self):
        eng = _engine(sla_threshold=80.0)
        eng.record_sla(sla_id="a", sla_score=50.0)
        eng.record_sla(sla_id="b", sla_score=30.0)
        assert len(eng.identify_sla_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_sla(sla_id="a", service="s1", sla_score=80.0)
        eng.record_sla(sla_id="b", service="s2", sla_score=60.0)
        assert eng.rank_by_sla()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_sla() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(sla_id="t", analysis_score=float(v))
        assert eng.detect_sla_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(sla_id="t", analysis_score=float(v))
        assert eng.detect_sla_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_sla_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_sla(sla_id="t", sla_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_sla(sla_id="t")
        eng.add_analysis(sla_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_sla(sla_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_sla(sla_id="a")
        eng.record_sla(sla_id="b")
        eng.add_analysis(sla_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
