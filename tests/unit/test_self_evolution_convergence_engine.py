"""Tests for SelfEvolutionConvergenceEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.self_evolution_convergence_engine import (
    ConvergenceSpeed,
    ConvergenceStatus,
    SelfEvolutionConvergenceEngine,
    StoppingCriterion,
)


@pytest.fixture()
def engine() -> SelfEvolutionConvergenceEngine:
    return SelfEvolutionConvergenceEngine(max_records=100)


def test_add_record(engine: SelfEvolutionConvergenceEngine) -> None:
    rec = engine.add_record(
        evolution_id="evo-1",
        iteration=5,
        status=ConvergenceStatus.APPROACHING,
        criterion=StoppingCriterion.REWARD_PLATEAU,
        speed=ConvergenceSpeed.MODERATE,
        reward_value=0.78,
        reward_delta=0.01,
        cost_incurred=10.0,
    )
    assert rec.evolution_id == "evo-1"
    assert rec.status == ConvergenceStatus.APPROACHING
    assert len(engine._records) == 1


def test_process(engine: SelfEvolutionConvergenceEngine) -> None:
    rec = engine.add_record(evolution_id="evo-2", reward_value=0.85)
    result = engine.process(rec.id)
    assert hasattr(result, "evolution_id")
    assert result.evolution_id == "evo-2"  # type: ignore[union-attr]


def test_process_not_found(engine: SelfEvolutionConvergenceEngine) -> None:
    result = engine.process("bad-id")
    assert result["status"] == "not_found"


def test_generate_report(engine: SelfEvolutionConvergenceEngine) -> None:
    engine.add_record(evolution_id="e1", status=ConvergenceStatus.CONVERGED, reward_value=0.95)
    engine.add_record(evolution_id="e2", status=ConvergenceStatus.DIVERGING, reward_value=0.3)
    report = engine.generate_report()
    assert report.total_records == 2
    assert "converged" in report.by_status or "diverging" in report.by_status


def test_get_stats(engine: SelfEvolutionConvergenceEngine) -> None:
    engine.add_record(evolution_id="e3", status=ConvergenceStatus.PRE_CONVERGENCE)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "status_distribution" in stats


def test_clear_data(engine: SelfEvolutionConvergenceEngine) -> None:
    engine.add_record(evolution_id="e4")
    engine.clear_data()
    assert engine._records == []


def test_detect_convergence_point(engine: SelfEvolutionConvergenceEngine) -> None:
    for i in range(8):
        engine.add_record(
            evolution_id="conv-test",
            iteration=i,
            reward_value=0.8 + i * 0.001,
            reward_delta=0.0005,
        )
    result = engine.detect_convergence_point("conv-test", delta_threshold=0.001, window=5)
    assert "converged" in result
    assert result["evolution_id"] == "conv-test"


def test_compute_convergence_rate(engine: SelfEvolutionConvergenceEngine) -> None:
    for i in range(5):
        engine.add_record(
            evolution_id="rate-test",
            iteration=i,
            reward_value=0.5 + i * 0.1,
            reward_delta=0.1,
        )
    result = engine.compute_convergence_rate("rate-test")
    assert "convergence_rate" in result
    assert result["convergence_rate"] > 0


def test_recommend_stopping_iteration(engine: SelfEvolutionConvergenceEngine) -> None:
    for i in range(6):
        engine.add_record(
            evolution_id="stop-test",
            iteration=i,
            reward_value=0.7,
            reward_delta=0.0001,
            cost_incurred=100.0,
        )
    result = engine.recommend_stopping_iteration("stop-test", cost_budget=300.0)
    assert "recommended_stop" in result
    assert result["total_cost"] <= 700.0
