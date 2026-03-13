"""Tests for EvolutionIterationOptimizerEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.evolution_iteration_optimizer_engine import (
    EvolutionIterationOptimizerEngine,
    IterationEfficiency,
    OptimizationStrategy,
    ResourceAllocation,
)


@pytest.fixture()
def engine() -> EvolutionIterationOptimizerEngine:
    return EvolutionIterationOptimizerEngine(max_records=100)


def test_add_record(engine: EvolutionIterationOptimizerEngine) -> None:
    rec = engine.add_record(
        run_id="run-1",
        iteration=3,
        strategy=OptimizationStrategy.ADAPTIVE_BUDGET,
        allocation=ResourceAllocation.BALANCED,
        efficiency=IterationEfficiency.OPTIMAL,
        cost_per_iteration=5.0,
        improvement_gain=0.05,
        compute_units=2.0,
    )
    assert rec.run_id == "run-1"
    assert rec.efficiency == IterationEfficiency.OPTIMAL
    assert len(engine._records) == 1


def test_process(engine: EvolutionIterationOptimizerEngine) -> None:
    rec = engine.add_record(run_id="run-2", cost_per_iteration=3.0, improvement_gain=0.08)
    result = engine.process(rec.id)
    assert hasattr(result, "run_id")
    assert result.run_id == "run-2"  # type: ignore[union-attr]


def test_process_not_found(engine: EvolutionIterationOptimizerEngine) -> None:
    result = engine.process("no-id")
    assert result["status"] == "not_found"


def test_generate_report(engine: EvolutionIterationOptimizerEngine) -> None:
    engine.add_record(run_id="r1", efficiency=IterationEfficiency.WASTEFUL, cost_per_iteration=20.0)
    engine.add_record(run_id="r2", efficiency=IterationEfficiency.OPTIMAL, cost_per_iteration=5.0)
    report = engine.generate_report()
    assert report.total_records == 2
    assert len(report.recommendations) > 0


def test_get_stats(engine: EvolutionIterationOptimizerEngine) -> None:
    engine.add_record(run_id="r3", efficiency=IterationEfficiency.ACCEPTABLE)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "efficiency_distribution" in stats


def test_clear_data(engine: EvolutionIterationOptimizerEngine) -> None:
    engine.add_record(run_id="r4")
    engine.clear_data()
    assert engine._records == []


def test_compute_cost_per_improvement(engine: EvolutionIterationOptimizerEngine) -> None:
    for i in range(4):
        engine.add_record(
            run_id="cpi-run", iteration=i, cost_per_iteration=10.0, improvement_gain=0.1
        )
    result = engine.compute_cost_per_improvement()
    assert len(result) >= 1
    assert result[0]["run_id"] == "cpi-run"
    # total_cost=40.0, total_gain=0.4, cpi=40/0.4=100.0
    assert result[0]["cost_per_improvement"] == pytest.approx(100.0, abs=0.01)


def test_recommend_iteration_budget(engine: EvolutionIterationOptimizerEngine) -> None:
    for _ in range(5):
        engine.add_record(run_id="budget-run", cost_per_iteration=10.0, improvement_gain=0.02)
    result = engine.recommend_iteration_budget(target_improvement=0.1, cost_budget=200.0)
    assert "recommended_iterations" in result
    assert result["recommended_iterations"] >= 1


def test_analyze_diminishing_returns(engine: EvolutionIterationOptimizerEngine) -> None:
    gains = [0.1, 0.09, 0.08, 0.01, 0.01, 0.005, 0.005, 0.002]
    for i, g in enumerate(gains):
        engine.add_record(run_id="dim-run", iteration=i, improvement_gain=g, cost_per_iteration=5.0)
    result = engine.analyze_diminishing_returns("dim-run")
    assert result["run_id"] == "dim-run"
    assert "diminishing_returns" in result
    assert result["diminishing_returns"] is True
