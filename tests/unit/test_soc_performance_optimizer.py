"""Tests for shieldops.analytics.soc_performance_optimizer — SOCPerformanceOptimizer."""

from __future__ import annotations

from shieldops.analytics.soc_performance_optimizer import (
    OptimizationArea,
    PerformanceMetric,
    PerformanceTier,
    SOCPerformanceAnalysis,
    SOCPerformanceOptimizer,
    SOCPerformanceRecord,
    SOCPerformanceReport,
)


def _engine(**kw) -> SOCPerformanceOptimizer:
    return SOCPerformanceOptimizer(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert PerformanceMetric.MTTD == "mttd"

    def test_e1_v2(self):
        assert PerformanceMetric.MTTR == "mttr"

    def test_e1_v3(self):
        assert PerformanceMetric.FALSE_POSITIVE_RATE == "false_positive_rate"

    def test_e1_v4(self):
        assert PerformanceMetric.ANALYST_UTILIZATION == "analyst_utilization"

    def test_e1_v5(self):
        assert PerformanceMetric.COVERAGE == "coverage"

    def test_e2_v1(self):
        assert OptimizationArea.WORKFLOW == "workflow"

    def test_e2_v2(self):
        assert OptimizationArea.TOOLING == "tooling"

    def test_e2_v3(self):
        assert OptimizationArea.TRAINING == "training"

    def test_e2_v4(self):
        assert OptimizationArea.AUTOMATION == "automation"

    def test_e2_v5(self):
        assert OptimizationArea.STAFFING == "staffing"

    def test_e3_v1(self):
        assert PerformanceTier.ELITE == "elite"

    def test_e3_v2(self):
        assert PerformanceTier.HIGH == "high"

    def test_e3_v3(self):
        assert PerformanceTier.AVERAGE == "average"

    def test_e3_v4(self):
        assert PerformanceTier.BELOW_AVERAGE == "below_average"

    def test_e3_v5(self):
        assert PerformanceTier.CRITICAL == "critical"


class TestModels:
    def test_rec(self):
        r = SOCPerformanceRecord()
        assert r.id and r.performance_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = SOCPerformanceAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = SOCPerformanceReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_performance(
            performance_id="t",
            performance_metric=PerformanceMetric.MTTR,
            optimization_area=OptimizationArea.TOOLING,
            performance_tier=PerformanceTier.HIGH,
            performance_score=92.0,
            service="s",
            team="t",
        )
        assert r.performance_id == "t" and r.performance_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_performance(performance_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_performance(performance_id="t")
        assert eng.get_performance(r.id) is not None

    def test_not_found(self):
        assert _engine().get_performance("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_performance(performance_id="a")
        eng.record_performance(performance_id="b")
        assert len(eng.list_performances()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_performance(performance_id="a", performance_metric=PerformanceMetric.MTTD)
        eng.record_performance(performance_id="b", performance_metric=PerformanceMetric.MTTR)
        assert len(eng.list_performances(performance_metric=PerformanceMetric.MTTD)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_performance(performance_id="a", optimization_area=OptimizationArea.WORKFLOW)
        eng.record_performance(performance_id="b", optimization_area=OptimizationArea.TOOLING)
        assert len(eng.list_performances(optimization_area=OptimizationArea.WORKFLOW)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_performance(performance_id="a", team="x")
        eng.record_performance(performance_id="b", team="y")
        assert len(eng.list_performances(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_performance(performance_id=f"t-{i}")
        assert len(eng.list_performances(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            performance_id="t",
            performance_metric=PerformanceMetric.MTTR,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(performance_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_performance(
            performance_id="a", performance_metric=PerformanceMetric.MTTD, performance_score=90.0
        )
        eng.record_performance(
            performance_id="b", performance_metric=PerformanceMetric.MTTD, performance_score=70.0
        )
        assert "mttd" in eng.analyze_metric_distribution()

    def test_empty(self):
        assert _engine().analyze_metric_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(performance_threshold=80.0)
        eng.record_performance(performance_id="a", performance_score=60.0)
        eng.record_performance(performance_id="b", performance_score=90.0)
        assert len(eng.identify_performance_gaps()) == 1

    def test_sorted(self):
        eng = _engine(performance_threshold=80.0)
        eng.record_performance(performance_id="a", performance_score=50.0)
        eng.record_performance(performance_id="b", performance_score=30.0)
        assert len(eng.identify_performance_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_performance(performance_id="a", service="s1", performance_score=80.0)
        eng.record_performance(performance_id="b", service="s2", performance_score=60.0)
        assert eng.rank_by_performance()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_performance() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(performance_id="t", analysis_score=float(v))
        assert eng.detect_performance_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(performance_id="t", analysis_score=float(v))
        assert eng.detect_performance_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_performance_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_performance(performance_id="t", performance_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_performance(performance_id="t")
        eng.add_analysis(performance_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_performance(performance_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_performance(performance_id="a")
        eng.record_performance(performance_id="b")
        eng.add_analysis(performance_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
