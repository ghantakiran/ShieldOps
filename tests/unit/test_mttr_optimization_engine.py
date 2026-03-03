"""Tests for shieldops.analytics.mttr_optimization_engine — MTTROptimizationEngine."""

from __future__ import annotations

from shieldops.analytics.mttr_optimization_engine import (
    ImprovementStatus,
    MTTRAnalysis,
    MTTROptimizationEngine,
    MTTRRecord,
    MTTRReport,
    OptimizationType,
    ResponsePhase,
)


def _engine(**kw) -> MTTROptimizationEngine:
    return MTTROptimizationEngine(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert ResponsePhase.TRIAGE == "triage"

    def test_e1_v2(self):
        assert ResponsePhase.INVESTIGATION == "investigation"

    def test_e1_v3(self):
        assert ResponsePhase.CONTAINMENT == "containment"

    def test_e1_v4(self):
        assert ResponsePhase.REMEDIATION == "remediation"

    def test_e1_v5(self):
        assert ResponsePhase.RECOVERY == "recovery"

    def test_e2_v1(self):
        assert OptimizationType.AUTOMATION == "automation"

    def test_e2_v2(self):
        assert OptimizationType.RUNBOOK == "runbook"

    def test_e2_v3(self):
        assert OptimizationType.STAFFING == "staffing"

    def test_e2_v4(self):
        assert OptimizationType.TOOLING == "tooling"

    def test_e2_v5(self):
        assert OptimizationType.PROCESS == "process"

    def test_e3_v1(self):
        assert ImprovementStatus.IMPLEMENTED == "implemented"

    def test_e3_v2(self):
        assert ImprovementStatus.IN_PROGRESS == "in_progress"

    def test_e3_v3(self):
        assert ImprovementStatus.PLANNED == "planned"

    def test_e3_v4(self):
        assert ImprovementStatus.EVALUATED == "evaluated"

    def test_e3_v5(self):
        assert ImprovementStatus.DEFERRED == "deferred"


class TestModels:
    def test_rec(self):
        r = MTTRRecord()
        assert r.id and r.response_time_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = MTTRAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = MTTRReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_mttr(
            mttr_id="t",
            response_phase=ResponsePhase.INVESTIGATION,
            optimization_type=OptimizationType.RUNBOOK,
            improvement_status=ImprovementStatus.IN_PROGRESS,
            response_time_score=92.0,
            service="s",
            team="t",
        )
        assert r.mttr_id == "t" and r.response_time_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mttr(mttr_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_mttr(mttr_id="t")
        assert eng.get_mttr(r.id) is not None

    def test_not_found(self):
        assert _engine().get_mttr("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_mttr(mttr_id="a")
        eng.record_mttr(mttr_id="b")
        assert len(eng.list_mttrs()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_mttr(mttr_id="a", response_phase=ResponsePhase.TRIAGE)
        eng.record_mttr(mttr_id="b", response_phase=ResponsePhase.INVESTIGATION)
        assert len(eng.list_mttrs(response_phase=ResponsePhase.TRIAGE)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_mttr(mttr_id="a", optimization_type=OptimizationType.AUTOMATION)
        eng.record_mttr(mttr_id="b", optimization_type=OptimizationType.RUNBOOK)
        assert len(eng.list_mttrs(optimization_type=OptimizationType.AUTOMATION)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_mttr(mttr_id="a", team="x")
        eng.record_mttr(mttr_id="b", team="y")
        assert len(eng.list_mttrs(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_mttr(mttr_id=f"t-{i}")
        assert len(eng.list_mttrs(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            mttr_id="t",
            response_phase=ResponsePhase.INVESTIGATION,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(mttr_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_mttr(mttr_id="a", response_phase=ResponsePhase.TRIAGE, response_time_score=90.0)
        eng.record_mttr(mttr_id="b", response_phase=ResponsePhase.TRIAGE, response_time_score=70.0)
        assert "triage" in eng.analyze_phase_distribution()

    def test_empty(self):
        assert _engine().analyze_phase_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(response_time_threshold=80.0)
        eng.record_mttr(mttr_id="a", response_time_score=60.0)
        eng.record_mttr(mttr_id="b", response_time_score=90.0)
        assert len(eng.identify_response_gaps()) == 1

    def test_sorted(self):
        eng = _engine(response_time_threshold=80.0)
        eng.record_mttr(mttr_id="a", response_time_score=50.0)
        eng.record_mttr(mttr_id="b", response_time_score=30.0)
        assert len(eng.identify_response_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_mttr(mttr_id="a", service="s1", response_time_score=80.0)
        eng.record_mttr(mttr_id="b", service="s2", response_time_score=60.0)
        assert eng.rank_by_response_time()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_response_time() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(mttr_id="t", analysis_score=float(v))
        assert eng.detect_response_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(mttr_id="t", analysis_score=float(v))
        assert eng.detect_response_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_response_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_mttr(mttr_id="t", response_time_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_mttr(mttr_id="t")
        eng.add_analysis(mttr_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_mttr(mttr_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_mttr(mttr_id="a")
        eng.record_mttr(mttr_id="b")
        eng.add_analysis(mttr_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
