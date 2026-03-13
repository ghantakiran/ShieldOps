"""Tests for SmartAlertRoutingPlanner."""

from __future__ import annotations

from shieldops.operations.smart_alert_routing_planner import (
    CoverageGap,
    RoutingStrategy,
    SimulationResult,
    SmartAlertRoutingPlanner,
)


def _engine(**kw) -> SmartAlertRoutingPlanner:
    return SmartAlertRoutingPlanner(**kw)


class TestEnums:
    def test_routing_strategy_values(self):
        for v in RoutingStrategy:
            assert isinstance(v.value, str)

    def test_coverage_gap_values(self):
        for v in CoverageGap:
            assert isinstance(v.value, str)

    def test_simulation_result_values(self):
        for v in SimulationResult:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(route_id="rt-1")
        assert r.route_id == "rt-1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(route_id=f"rt-{i}")
        assert len(eng._records) == 5

    def test_with_params(self):
        eng = _engine()
        r = eng.record_item(
            route_id="rt-1",
            skill_match_score=0.9,
            timezone="US/Eastern",
        )
        assert r.skill_match_score == 0.9


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            route_id="rt-1",
            skill_match_score=0.8,
        )
        a = eng.process(r.id)
        assert hasattr(a, "route_id")
        assert a.route_id == "rt-1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(route_id="rt-1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(route_id="rt-1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(route_id="rt-1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestPlanSkillBasedRouting:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            route_id="rt-1",
            responder_id="r1",
            skill_match_score=0.9,
        )
        result = eng.plan_skill_based_routing()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().plan_skill_based_routing()
        assert r == []


class TestOptimizeTimezoneCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            route_id="rt-1",
            responder_id="r1",
            timezone="US/Eastern",
        )
        result = eng.optimize_timezone_coverage()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().optimize_timezone_coverage()
        assert r == []


class TestSimulateRoutingScenario:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            route_id="rt-1",
            simulation_result=(SimulationResult.OPTIMAL),
        )
        result = eng.simulate_routing_scenario()
        assert len(result) >= 1

    def test_empty(self):
        r = _engine().simulate_routing_scenario()
        assert r == []
