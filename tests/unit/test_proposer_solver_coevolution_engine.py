"""Tests for ProposerSolverCoevolutionEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.proposer_solver_coevolution_engine import (
    CoevolutionState,
    FeedbackDirection,
    IterationOutcome,
    ProposerSolverCoevolutionEngine,
)


@pytest.fixture()
def engine() -> ProposerSolverCoevolutionEngine:
    return ProposerSolverCoevolutionEngine(max_records=100)


def test_add_record(engine: ProposerSolverCoevolutionEngine) -> None:
    rec = engine.add_record(
        coevolution_id="coevo-1",
        iteration=1,
        state=CoevolutionState.EVOLVING,
        feedback_direction=FeedbackDirection.BIDIRECTIONAL,
        outcome=IterationOutcome.BOTH_IMPROVED,
        solver_delta=0.05,
        proposer_delta=0.03,
        efficiency_score=0.8,
    )
    assert rec.coevolution_id == "coevo-1"
    assert rec.outcome == IterationOutcome.BOTH_IMPROVED
    assert len(engine._records) == 1


def test_process(engine: ProposerSolverCoevolutionEngine) -> None:
    rec = engine.add_record(coevolution_id="coevo-2", efficiency_score=0.75)
    result = engine.process(rec.id)
    assert hasattr(result, "coevolution_id")
    assert result.coevolution_id == "coevo-2"  # type: ignore[union-attr]


def test_process_not_found(engine: ProposerSolverCoevolutionEngine) -> None:
    result = engine.process("no-such-key")
    assert result["status"] == "not_found"


def test_generate_report(engine: ProposerSolverCoevolutionEngine) -> None:
    engine.add_record(coevolution_id="c1", state=CoevolutionState.CONVERGED, efficiency_score=0.9)
    engine.add_record(
        coevolution_id="c2", state=CoevolutionState.INITIALIZING, efficiency_score=0.3
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.avg_efficiency > 0


def test_get_stats(engine: ProposerSolverCoevolutionEngine) -> None:
    engine.add_record(coevolution_id="c3", state=CoevolutionState.CONVERGING)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "state_distribution" in stats


def test_clear_data(engine: ProposerSolverCoevolutionEngine) -> None:
    engine.add_record(coevolution_id="c4")
    engine.clear_data()
    assert engine._records == []


def test_execute_coevolution_step(engine: ProposerSolverCoevolutionEngine) -> None:
    engine.add_record(coevolution_id="step-test", iteration=1, efficiency_score=0.7)
    result = engine.execute_coevolution_step(
        coevolution_id="step-test",
        solver_success_rate=0.8,
        current_difficulty=0.5,
    )
    assert "next_difficulty" in result
    assert result["next_difficulty"] > 0.5  # solver improved, difficulty increases


def test_detect_coevolution_divergence(engine: ProposerSolverCoevolutionEngine) -> None:
    for i in range(5):
        engine.add_record(
            coevolution_id="div-test",
            iteration=i,
            outcome=IterationOutcome.NO_CHANGE,
            feedback_direction=FeedbackDirection.STALLED,
        )
    divergences = engine.detect_coevolution_divergence()
    assert len(divergences) >= 1
    assert divergences[0]["divergence_detected"] is True


def test_compute_coevolution_efficiency(engine: ProposerSolverCoevolutionEngine) -> None:
    for i in range(3):
        engine.add_record(coevolution_id="eff-test", iteration=i, efficiency_score=0.6 + i * 0.1)
    result = engine.compute_coevolution_efficiency()
    assert "global_avg_efficiency" in result
    assert "per_coevolution" in result
    assert len(result["per_coevolution"]) >= 1
