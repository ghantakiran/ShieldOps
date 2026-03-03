"""Tests for shieldops.security.alert_routing_intelligence — AlertRoutingIntelligence."""

from __future__ import annotations

from shieldops.security.alert_routing_intelligence import (
    AlertPriority,
    AlertRoutingIntelligence,
    RoutingAnalysis,
    RoutingOutcome,
    RoutingRecord,
    RoutingReport,
    RoutingStrategy,
)


def _engine(**kw) -> AlertRoutingIntelligence:
    return AlertRoutingIntelligence(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert RoutingStrategy.SKILL_BASED == "skill_based"

    def test_e1_v2(self):
        assert RoutingStrategy.ROUND_ROBIN == "round_robin"

    def test_e1_v3(self):
        assert RoutingStrategy.PRIORITY_BASED == "priority_based"

    def test_e1_v4(self):
        assert RoutingStrategy.WORKLOAD_AWARE == "workload_aware"

    def test_e1_v5(self):
        assert RoutingStrategy.ML_OPTIMIZED == "ml_optimized"

    def test_e2_v1(self):
        assert AlertPriority.P1_CRITICAL == "p1_critical"

    def test_e2_v2(self):
        assert AlertPriority.P2_HIGH == "p2_high"

    def test_e2_v3(self):
        assert AlertPriority.P3_MEDIUM == "p3_medium"

    def test_e2_v4(self):
        assert AlertPriority.P4_LOW == "p4_low"

    def test_e2_v5(self):
        assert AlertPriority.P5_INFORMATIONAL == "p5_informational"

    def test_e3_v1(self):
        assert RoutingOutcome.CORRECT == "correct"

    def test_e3_v2(self):
        assert RoutingOutcome.ESCALATED == "escalated"

    def test_e3_v3(self):
        assert RoutingOutcome.REROUTED == "rerouted"

    def test_e3_v4(self):
        assert RoutingOutcome.DELAYED == "delayed"

    def test_e3_v5(self):
        assert RoutingOutcome.MISSED == "missed"


class TestModels:
    def test_rec(self):
        r = RoutingRecord()
        assert r.id and r.routing_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = RoutingAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = RoutingReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_routing(
            routing_id="t",
            routing_strategy=RoutingStrategy.ROUND_ROBIN,
            alert_priority=AlertPriority.P2_HIGH,
            routing_outcome=RoutingOutcome.ESCALATED,
            routing_score=92.0,
            service="s",
            team="t",
        )
        assert r.routing_id == "t" and r.routing_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_routing(routing_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_routing(routing_id="t")
        assert eng.get_routing(r.id) is not None

    def test_not_found(self):
        assert _engine().get_routing("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_routing(routing_id="a")
        eng.record_routing(routing_id="b")
        assert len(eng.list_routings()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_routing(routing_id="a", routing_strategy=RoutingStrategy.SKILL_BASED)
        eng.record_routing(routing_id="b", routing_strategy=RoutingStrategy.ROUND_ROBIN)
        assert len(eng.list_routings(routing_strategy=RoutingStrategy.SKILL_BASED)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_routing(routing_id="a", alert_priority=AlertPriority.P1_CRITICAL)
        eng.record_routing(routing_id="b", alert_priority=AlertPriority.P2_HIGH)
        assert len(eng.list_routings(alert_priority=AlertPriority.P1_CRITICAL)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_routing(routing_id="a", team="x")
        eng.record_routing(routing_id="b", team="y")
        assert len(eng.list_routings(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_routing(routing_id=f"t-{i}")
        assert len(eng.list_routings(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            routing_id="t",
            routing_strategy=RoutingStrategy.ROUND_ROBIN,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(routing_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_routing(
            routing_id="a", routing_strategy=RoutingStrategy.SKILL_BASED, routing_score=90.0
        )
        eng.record_routing(
            routing_id="b", routing_strategy=RoutingStrategy.SKILL_BASED, routing_score=70.0
        )
        assert "skill_based" in eng.analyze_strategy_distribution()

    def test_empty(self):
        assert _engine().analyze_strategy_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(routing_threshold=80.0)
        eng.record_routing(routing_id="a", routing_score=60.0)
        eng.record_routing(routing_id="b", routing_score=90.0)
        assert len(eng.identify_routing_gaps()) == 1

    def test_sorted(self):
        eng = _engine(routing_threshold=80.0)
        eng.record_routing(routing_id="a", routing_score=50.0)
        eng.record_routing(routing_id="b", routing_score=30.0)
        assert len(eng.identify_routing_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_routing(routing_id="a", service="s1", routing_score=80.0)
        eng.record_routing(routing_id="b", service="s2", routing_score=60.0)
        assert eng.rank_by_routing()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_routing() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(routing_id="t", analysis_score=float(v))
        assert eng.detect_routing_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(routing_id="t", analysis_score=float(v))
        assert eng.detect_routing_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_routing_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_routing(routing_id="t", routing_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_routing(routing_id="t")
        eng.add_analysis(routing_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_routing(routing_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_routing(routing_id="a")
        eng.record_routing(routing_id="b")
        eng.add_analysis(routing_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
