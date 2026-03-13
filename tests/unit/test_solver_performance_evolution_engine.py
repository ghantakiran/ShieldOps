"""Tests for SolverPerformanceEvolutionEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.solver_performance_evolution_engine import (
    EvolutionPhase,
    PerformanceTrend,
    SolverPerformanceEvolutionEngine,
    SolverSkillLevel,
)


@pytest.fixture()
def engine() -> SolverPerformanceEvolutionEngine:
    return SolverPerformanceEvolutionEngine(max_records=100)


def test_add_record(engine: SolverPerformanceEvolutionEngine) -> None:
    rec = engine.add_record(
        solver_id="agent-1",
        iteration=1,
        phase=EvolutionPhase.RAPID_GAIN,
        skill_level=SolverSkillLevel.COMPETENT,
        trend=PerformanceTrend.IMPROVING,
        success_rate=0.72,
        reward_score=0.68,
    )
    assert rec.solver_id == "agent-1"
    assert rec.phase == EvolutionPhase.RAPID_GAIN
    assert len(engine._records) == 1


def test_process(engine: SolverPerformanceEvolutionEngine) -> None:
    rec = engine.add_record(solver_id="agent-2", success_rate=0.8, reward_score=0.75)
    result = engine.process(rec.id)
    assert hasattr(result, "solver_id")
    assert result.solver_id == "agent-2"  # type: ignore[union-attr]


def test_process_not_found(engine: SolverPerformanceEvolutionEngine) -> None:
    result = engine.process("bad-key")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: SolverPerformanceEvolutionEngine) -> None:
    engine.add_record(solver_id="a1", phase=EvolutionPhase.WARMUP, success_rate=0.4)
    engine.add_record(solver_id="a2", phase=EvolutionPhase.CONVERGENCE, success_rate=0.9)
    report = engine.generate_report()
    assert report.total_records == 2
    assert "warmup" in report.by_phase or "convergence" in report.by_phase


def test_get_stats(engine: SolverPerformanceEvolutionEngine) -> None:
    engine.add_record(solver_id="a3", phase=EvolutionPhase.PLATEAU)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "phase_distribution" in stats


def test_clear_data(engine: SolverPerformanceEvolutionEngine) -> None:
    engine.add_record(solver_id="a4")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert len(engine._records) == 0


def test_compute_evolution_curve(engine: SolverPerformanceEvolutionEngine) -> None:
    for i in range(4):
        engine.add_record(solver_id="curve-agent", iteration=i, success_rate=0.5 + i * 0.1)
    curve = engine.compute_evolution_curve("curve-agent")
    assert len(curve) == 4
    assert curve[0]["iteration"] == 0


def test_detect_skill_plateaus(engine: SolverPerformanceEvolutionEngine) -> None:
    for i in range(4):
        engine.add_record(solver_id="plateau-agent", iteration=i, success_rate=0.75)
    plateaus = engine.detect_skill_plateaus()
    assert isinstance(plateaus, list)
    assert len(plateaus) >= 1
    assert plateaus[0]["is_plateau"] is True


def test_compare_iteration_deltas(engine: SolverPerformanceEvolutionEngine) -> None:
    rates = [0.4, 0.5, 0.6, 0.65]
    for i, r in enumerate(rates):
        engine.add_record(solver_id="delta-agent", iteration=i, success_rate=r)
    deltas = engine.compare_iteration_deltas()
    assert len(deltas) >= 1
    assert "avg_iteration_delta" in deltas[0]
