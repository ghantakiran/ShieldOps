"""Tests for shieldops.billing.cost_simulator — CostSimulationEngine."""

from __future__ import annotations

from shieldops.billing.cost_simulator import (
    CostImpact,
    CostSimulationEngine,
    SimulationReport,
    SimulationResult,
    SimulationScenario,
    SimulationStatus,
    SimulationType,
)


def _engine(**kw) -> CostSimulationEngine:
    return CostSimulationEngine(**kw)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestSimulationType:
    """Test every SimulationType member."""

    def test_add_resource(self):
        assert SimulationType.ADD_RESOURCE == "add_resource"

    def test_remove_resource(self):
        assert SimulationType.REMOVE_RESOURCE == "remove_resource"

    def test_resize(self):
        assert SimulationType.RESIZE == "resize"

    def test_migrate_region(self):
        assert SimulationType.MIGRATE_REGION == "migrate_region"

    def test_change_provider(self):
        assert SimulationType.CHANGE_PROVIDER == "change_provider"


class TestCostImpact:
    """Test every CostImpact member."""

    def test_decrease_major(self):
        assert CostImpact.DECREASE_MAJOR == "decrease_major"

    def test_decrease_minor(self):
        assert CostImpact.DECREASE_MINOR == "decrease_minor"

    def test_neutral(self):
        assert CostImpact.NEUTRAL == "neutral"

    def test_increase_minor(self):
        assert CostImpact.INCREASE_MINOR == "increase_minor"

    def test_increase_major(self):
        assert CostImpact.INCREASE_MAJOR == "increase_major"


class TestSimulationStatus:
    """Test every SimulationStatus member."""

    def test_draft(self):
        assert SimulationStatus.DRAFT == "draft"

    def test_running(self):
        assert SimulationStatus.RUNNING == "running"

    def test_completed(self):
        assert SimulationStatus.COMPLETED == "completed"

    def test_failed(self):
        assert SimulationStatus.FAILED == "failed"

    def test_archived(self):
        assert SimulationStatus.ARCHIVED == "archived"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestModels:
    """Test model defaults."""

    def test_simulation_scenario_defaults(self):
        m = SimulationScenario()
        assert m.id
        assert m.name == ""
        assert m.simulation_type == SimulationType.ADD_RESOURCE
        assert m.status == SimulationStatus.DRAFT
        assert m.baseline_monthly_cost == 0.0
        assert m.resource_name == ""
        assert m.resource_cost == 0.0
        assert m.region == ""
        assert m.provider == ""

    def test_simulation_result_defaults(self):
        m = SimulationResult()
        assert m.id
        assert m.scenario_id == ""
        assert m.projected_monthly_cost == 0.0
        assert m.cost_difference == 0.0
        assert m.cost_impact == CostImpact.NEUTRAL
        assert m.impact_pct == 0.0
        assert m.details == ""

    def test_simulation_report_defaults(self):
        m = SimulationReport()
        assert m.total_scenarios == 0
        assert m.completed_count == 0
        assert m.avg_impact_pct == 0.0
        assert m.by_type == {}
        assert m.by_impact == {}
        assert m.total_projected_savings == 0.0
        assert m.budget_breaches == 0
        assert m.recommendations == []


# ---------------------------------------------------------------------------
# create_scenario
# ---------------------------------------------------------------------------


class TestCreateScenario:
    """Test CostSimulationEngine.create_scenario."""

    def test_basic(self):
        eng = _engine()
        sc = eng.create_scenario(
            name="add-cache",
            simulation_type=SimulationType.ADD_RESOURCE,
            baseline_monthly_cost=5000.0,
            resource_name="redis-cluster",
            resource_cost=500.0,
            region="us-east-1",
            provider="aws",
        )
        assert sc.name == "add-cache"
        assert sc.simulation_type == SimulationType.ADD_RESOURCE
        assert sc.baseline_monthly_cost == 5000.0
        assert sc.resource_cost == 500.0
        assert eng.get_scenario(sc.id) is sc

    def test_eviction_on_overflow(self):
        eng = _engine(max_scenarios=2)
        s1 = eng.create_scenario(name="s1")
        eng.create_scenario(name="s2")
        eng.create_scenario(name="s3")
        assert eng.get_scenario(s1.id) is None
        assert len(eng.list_scenarios()) == 2


# ---------------------------------------------------------------------------
# get_scenario
# ---------------------------------------------------------------------------


class TestGetScenario:
    """Test CostSimulationEngine.get_scenario."""

    def test_found(self):
        eng = _engine()
        sc = eng.create_scenario(name="test")
        assert eng.get_scenario(sc.id) is sc

    def test_not_found(self):
        eng = _engine()
        assert eng.get_scenario("nonexistent") is None


# ---------------------------------------------------------------------------
# list_scenarios
# ---------------------------------------------------------------------------


class TestListScenarios:
    """Test CostSimulationEngine.list_scenarios."""

    def test_all(self):
        eng = _engine()
        eng.create_scenario(name="a")
        eng.create_scenario(name="b")
        assert len(eng.list_scenarios()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.create_scenario(simulation_type=SimulationType.RESIZE)
        eng.create_scenario(simulation_type=SimulationType.ADD_RESOURCE)
        eng.create_scenario(simulation_type=SimulationType.RESIZE)
        result = eng.list_scenarios(simulation_type=SimulationType.RESIZE)
        assert len(result) == 2

    def test_filter_by_status(self):
        eng = _engine()
        sc = eng.create_scenario(
            simulation_type=SimulationType.RESIZE,
            baseline_monthly_cost=1000.0,
        )
        eng.run_simulation(sc.id)
        eng.create_scenario(name="draft-only")
        completed = eng.list_scenarios(status=SimulationStatus.COMPLETED)
        assert len(completed) == 1


# ---------------------------------------------------------------------------
# run_simulation
# ---------------------------------------------------------------------------


class TestRunSimulation:
    """Test CostSimulationEngine.run_simulation."""

    def test_add_resource(self):
        eng = _engine()
        sc = eng.create_scenario(
            simulation_type=SimulationType.ADD_RESOURCE,
            baseline_monthly_cost=5000.0,
            resource_cost=500.0,
        )
        result = eng.run_simulation(sc.id)
        assert result is not None
        assert result.projected_monthly_cost == 5500.0
        assert result.cost_difference == 500.0
        assert result.impact_pct == 10.0
        assert result.cost_impact == CostImpact.INCREASE_MINOR

    def test_remove_resource(self):
        eng = _engine()
        sc = eng.create_scenario(
            simulation_type=SimulationType.REMOVE_RESOURCE,
            baseline_monthly_cost=5000.0,
            resource_cost=500.0,
        )
        result = eng.run_simulation(sc.id)
        assert result is not None
        assert result.projected_monthly_cost == 4500.0
        assert result.cost_difference == -500.0
        assert result.cost_impact == CostImpact.DECREASE_MINOR

    def test_resize(self):
        eng = _engine()
        sc = eng.create_scenario(
            simulation_type=SimulationType.RESIZE,
            baseline_monthly_cost=1000.0,
        )
        result = eng.run_simulation(sc.id)
        assert result is not None
        assert result.projected_monthly_cost == 800.0
        assert result.cost_difference == -200.0
        assert result.impact_pct == -20.0
        assert result.cost_impact == CostImpact.DECREASE_MAJOR

    def test_migrate_region(self):
        eng = _engine()
        sc = eng.create_scenario(
            simulation_type=SimulationType.MIGRATE_REGION,
            baseline_monthly_cost=1000.0,
        )
        result = eng.run_simulation(sc.id)
        assert result is not None
        assert result.projected_monthly_cost == 900.0
        assert result.cost_difference == -100.0
        assert result.cost_impact == CostImpact.DECREASE_MINOR

    def test_change_provider(self):
        eng = _engine()
        sc = eng.create_scenario(
            simulation_type=SimulationType.CHANGE_PROVIDER,
            baseline_monthly_cost=1000.0,
        )
        result = eng.run_simulation(sc.id)
        assert result is not None
        assert result.projected_monthly_cost == 850.0
        assert result.cost_difference == -150.0
        assert result.cost_impact == CostImpact.DECREASE_MINOR

    def test_not_found_returns_none(self):
        eng = _engine()
        assert eng.run_simulation("missing") is None


# ---------------------------------------------------------------------------
# compare_scenarios
# ---------------------------------------------------------------------------


class TestCompareScenarios:
    """Test CostSimulationEngine.compare_scenarios."""

    def test_basic_with_two_scenarios(self):
        eng = _engine()
        s1 = eng.create_scenario(
            name="add",
            simulation_type=SimulationType.ADD_RESOURCE,
            baseline_monthly_cost=1000.0,
            resource_cost=200.0,
        )
        s2 = eng.create_scenario(
            name="resize",
            simulation_type=SimulationType.RESIZE,
            baseline_monthly_cost=1000.0,
        )
        eng.run_simulation(s1.id)
        eng.run_simulation(s2.id)
        comparisons = eng.compare_scenarios([s1.id, s2.id])
        assert len(comparisons) == 2
        assert comparisons[0]["name"] == "add"
        assert comparisons[0]["projected_cost"] == 1200.0
        assert comparisons[1]["name"] == "resize"
        assert comparisons[1]["projected_cost"] == 800.0


# ---------------------------------------------------------------------------
# estimate_monthly_impact
# ---------------------------------------------------------------------------


class TestEstimateMonthlyImpact:
    """Test CostSimulationEngine.estimate_monthly_impact."""

    def test_basic_with_result(self):
        eng = _engine()
        sc = eng.create_scenario(
            simulation_type=SimulationType.ADD_RESOURCE,
            baseline_monthly_cost=1000.0,
            resource_cost=200.0,
        )
        eng.run_simulation(sc.id)
        impact = eng.estimate_monthly_impact(sc.id)
        assert impact["baseline"] == 1000.0
        assert impact["projected"] == 1200.0
        assert impact["monthly_difference"] == 200.0
        assert impact["annual_difference"] == 2400.0

    def test_not_found_returns_zeros(self):
        eng = _engine()
        impact = eng.estimate_monthly_impact("missing")
        assert impact["baseline"] == 0.0
        assert impact["projected"] == 0.0
        assert impact["monthly_difference"] == 0.0
        assert impact["annual_difference"] == 0.0


# ---------------------------------------------------------------------------
# identify_cost_drivers
# ---------------------------------------------------------------------------


class TestIdentifyCostDrivers:
    """Test CostSimulationEngine.identify_cost_drivers."""

    def test_sorted_by_abs_difference(self):
        eng = _engine()
        s1 = eng.create_scenario(
            name="small-add",
            simulation_type=SimulationType.ADD_RESOURCE,
            baseline_monthly_cost=1000.0,
            resource_cost=100.0,
        )
        s2 = eng.create_scenario(
            name="large-remove",
            simulation_type=SimulationType.REMOVE_RESOURCE,
            baseline_monthly_cost=1000.0,
            resource_cost=500.0,
        )
        eng.run_simulation(s1.id)
        eng.run_simulation(s2.id)
        drivers = eng.identify_cost_drivers()
        assert len(drivers) == 2
        assert drivers[0]["scenario_name"] == "large-remove"
        assert abs(drivers[0]["cost_difference"]) >= abs(drivers[1]["cost_difference"])


# ---------------------------------------------------------------------------
# detect_budget_breaches
# ---------------------------------------------------------------------------


class TestDetectBudgetBreaches:
    """Test CostSimulationEngine.detect_budget_breaches."""

    def test_breach_above_threshold(self):
        eng = _engine(budget_breach_threshold_pct=10.0)
        sc = eng.create_scenario(
            name="big-add",
            simulation_type=SimulationType.ADD_RESOURCE,
            baseline_monthly_cost=1000.0,
            resource_cost=500.0,
        )
        eng.run_simulation(sc.id)
        breaches = eng.detect_budget_breaches()
        assert len(breaches) == 1
        assert breaches[0]["scenario_name"] == "big-add"
        assert breaches[0]["impact_pct"] == 50.0
        assert breaches[0]["breach_amount"] == 40.0

    def test_no_breaches(self):
        eng = _engine(budget_breach_threshold_pct=50.0)
        sc = eng.create_scenario(
            name="tiny-add",
            simulation_type=SimulationType.ADD_RESOURCE,
            baseline_monthly_cost=1000.0,
            resource_cost=10.0,
        )
        eng.run_simulation(sc.id)
        breaches = eng.detect_budget_breaches()
        assert breaches == []


# ---------------------------------------------------------------------------
# generate_simulation_report
# ---------------------------------------------------------------------------


class TestGenerateSimulationReport:
    """Test CostSimulationEngine.generate_simulation_report."""

    def test_basic(self):
        eng = _engine()
        sc = eng.create_scenario(
            name="resize-test",
            simulation_type=SimulationType.RESIZE,
            baseline_monthly_cost=1000.0,
        )
        eng.run_simulation(sc.id)
        report = eng.generate_simulation_report()
        assert isinstance(report, SimulationReport)
        assert report.total_scenarios == 1
        assert report.completed_count == 1
        assert report.total_projected_savings == 200.0
        assert report.by_type["resize"] == 1


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    """Test CostSimulationEngine.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        sc = eng.create_scenario(name="x")
        eng.run_simulation(sc.id)
        eng.clear_data()
        assert eng.list_scenarios() == []
        stats = eng.get_stats()
        assert stats["total_scenarios"] == 0
        assert stats["total_results"] == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    """Test CostSimulationEngine.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_scenarios"] == 0
        assert stats["total_results"] == 0
        assert stats["type_distribution"] == {}
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        sc = eng.create_scenario(
            name="test",
            simulation_type=SimulationType.ADD_RESOURCE,
            baseline_monthly_cost=1000.0,
            resource_cost=100.0,
        )
        eng.run_simulation(sc.id)
        stats = eng.get_stats()
        assert stats["total_scenarios"] == 1
        assert stats["total_results"] == 1
        assert stats["type_distribution"]["add_resource"] == 1
        assert stats["status_distribution"]["completed"] == 1
