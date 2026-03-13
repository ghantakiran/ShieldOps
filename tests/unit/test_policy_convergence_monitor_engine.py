"""Tests for PolicyConvergenceMonitorEngine."""

from __future__ import annotations

import pytest

from shieldops.security.policy_convergence_monitor_engine import (
    ConvergencePhase,
    InstabilityType,
    MonitoringGranularity,
    PolicyConvergenceMonitorEngine,
)


@pytest.fixture()
def engine() -> PolicyConvergenceMonitorEngine:
    return PolicyConvergenceMonitorEngine(max_records=100)


def test_add_record(engine: PolicyConvergenceMonitorEngine) -> None:
    rec = engine.add_record(
        agent_id="agent-1",
        convergence_phase=ConvergencePhase.LEARNING,
        instability_type=InstabilityType.ENTROPY_COLLAPSE,
        monitoring_granularity=MonitoringGranularity.PER_EPOCH,
        reward=0.7,
        entropy=1.5,
        gradient_norm=0.3,
        step=100,
    )
    assert rec.agent_id == "agent-1"
    assert rec.step == 100
    assert len(engine._records) == 1


def test_process(engine: PolicyConvergenceMonitorEngine) -> None:
    rec = engine.add_record(
        agent_id="a1",
        convergence_phase=ConvergencePhase.CONVERGED,
        step=500,
    )
    result = engine.process(rec.id)
    assert hasattr(result, "convergence_eta_steps")
    assert result.convergence_eta_steps == 0  # type: ignore[union-attr]


def test_process_not_found(engine: PolicyConvergenceMonitorEngine) -> None:
    result = engine.process("bad-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: PolicyConvergenceMonitorEngine) -> None:
    engine.add_record(
        agent_id="a1",
        convergence_phase=ConvergencePhase.EXPLORATION,
        reward=0.2,
        entropy=2.0,
    )
    engine.add_record(
        agent_id="a2",
        convergence_phase=ConvergencePhase.CONVERGED,
        reward=0.9,
        entropy=0.5,
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert "exploration" in report.by_convergence_phase


def test_get_stats(engine: PolicyConvergenceMonitorEngine) -> None:
    engine.add_record(convergence_phase=ConvergencePhase.STABILIZING)
    stats = engine.get_stats()
    assert "phase_distribution" in stats
    assert stats["total_records"] == 1


def test_clear_data(engine: PolicyConvergenceMonitorEngine) -> None:
    engine.add_record(agent_id="a1")
    engine.clear_data()
    assert len(engine._records) == 0
    assert len(engine._analyses) == 0


def test_detect_convergence_state(engine: PolicyConvergenceMonitorEngine) -> None:
    engine.add_record(agent_id="a1", convergence_phase=ConvergencePhase.CONVERGED, step=900)
    engine.add_record(agent_id="a2", convergence_phase=ConvergencePhase.LEARNING, step=200)
    result = engine.detect_convergence_state()
    assert isinstance(result, list)
    assert any(r["agent_id"] == "a1" and r["is_converged"] for r in result)


def test_alert_on_instability(engine: PolicyConvergenceMonitorEngine) -> None:
    engine.add_record(
        agent_id="a1",
        instability_type=InstabilityType.ENTROPY_COLLAPSE,
        entropy=0.01,
        step=300,
    )
    engine.add_record(
        agent_id="a2",
        instability_type=InstabilityType.REWARD_OSCILLATION,
        entropy=1.5,
        step=200,
    )
    result = engine.alert_on_instability()
    assert isinstance(result, list)
    agent_ids = [r["agent_id"] for r in result]
    assert "a1" in agent_ids


def test_estimate_convergence_eta(engine: PolicyConvergenceMonitorEngine) -> None:
    engine.add_record(agent_id="a1", convergence_phase=ConvergencePhase.LEARNING, step=300)
    engine.add_record(agent_id="a2", convergence_phase=ConvergencePhase.CONVERGED, step=900)
    result = engine.estimate_convergence_eta()
    assert isinstance(result, list)
    converged_entry = next(r for r in result if r["agent_id"] == "a2")
    assert converged_entry["eta_steps"] == 0


def test_max_records_eviction(engine: PolicyConvergenceMonitorEngine) -> None:
    for i in range(110):
        engine.add_record(agent_id=f"a-{i}")
    assert len(engine._records) == 100
