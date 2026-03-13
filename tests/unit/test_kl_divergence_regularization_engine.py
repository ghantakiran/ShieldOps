"""Tests for KLDivergenceRegularizationEngine."""

from __future__ import annotations

import pytest

from shieldops.security.kl_divergence_regularization_engine import (
    DivergenceLevel,
    KLDivergenceRegularizationEngine,
    ReferencePolicy,
    RegularizationStrength,
)


@pytest.fixture()
def engine() -> KLDivergenceRegularizationEngine:
    return KLDivergenceRegularizationEngine(max_records=100)


def test_add_record(engine: KLDivergenceRegularizationEngine) -> None:
    rec = engine.add_record(
        agent_id="agent-1",
        regularization_strength=RegularizationStrength.STRONG,
        divergence_level=DivergenceLevel.HIGH,
        reference_policy=ReferencePolicy.BEST_SO_FAR,
        kl_value=0.8,
        penalty_coefficient=0.5,
        policy_step=100,
    )
    assert rec.agent_id == "agent-1"
    assert rec.kl_value == 0.8
    assert len(engine._records) == 1


def test_process(engine: KLDivergenceRegularizationEngine) -> None:
    rec = engine.add_record(
        agent_id="a1",
        divergence_level=DivergenceLevel.EXCESSIVE,
        regularization_strength=RegularizationStrength.STRONG,
        kl_value=1.5,
        penalty_coefficient=0.5,
    )
    result = engine.process(rec.id)
    assert hasattr(result, "is_drifting")
    assert result.is_drifting is True  # type: ignore[union-attr]


def test_process_not_found(engine: KLDivergenceRegularizationEngine) -> None:
    result = engine.process("bad-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: KLDivergenceRegularizationEngine) -> None:
    engine.add_record(
        agent_id="a1",
        divergence_level=DivergenceLevel.EXCESSIVE,
        kl_value=2.0,
    )
    engine.add_record(
        agent_id="a2",
        divergence_level=DivergenceLevel.MINIMAL,
        kl_value=0.05,
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert "a1" in report.drifting_agents


def test_get_stats(engine: KLDivergenceRegularizationEngine) -> None:
    engine.add_record(divergence_level=DivergenceLevel.ACCEPTABLE)
    stats = engine.get_stats()
    assert "divergence_level_distribution" in stats
    assert stats["total_records"] == 1


def test_clear_data(engine: KLDivergenceRegularizationEngine) -> None:
    engine.add_record(agent_id="a1")
    engine.clear_data()
    assert len(engine._records) == 0
    assert len(engine._analyses) == 0


def test_compute_kl_divergence(engine: KLDivergenceRegularizationEngine) -> None:
    engine.add_record(agent_id="a1", kl_value=0.4)
    engine.add_record(agent_id="a1", kl_value=0.6)
    engine.add_record(agent_id="a2", kl_value=0.1)
    result = engine.compute_kl_divergence()
    assert isinstance(result, list)
    assert result[0]["mean_kl"] >= result[-1]["mean_kl"]
    a1_entry = next(r for r in result if r["agent_id"] == "a1")
    assert a1_entry["mean_kl"] == pytest.approx(0.5, abs=1e-3)


def test_adjust_kl_penalty(engine: KLDivergenceRegularizationEngine) -> None:
    engine.add_record(
        agent_id="a1",
        divergence_level=DivergenceLevel.EXCESSIVE,
        penalty_coefficient=0.5,
        policy_step=100,
    )
    result = engine.adjust_kl_penalty()
    assert isinstance(result, list)
    entry = next(r for r in result if r["agent_id"] == "a1")
    assert entry["suggested_penalty"] > entry["current_penalty"]


def test_detect_policy_drift(engine: KLDivergenceRegularizationEngine) -> None:
    engine.add_record(agent_id="drifter", kl_value=1.5)
    engine.add_record(agent_id="stable", kl_value=0.1)
    result = engine.detect_policy_drift()
    assert isinstance(result, list)
    drifter = next(r for r in result if r["agent_id"] == "drifter")
    assert drifter["is_drifting"] is True


def test_max_records_eviction(engine: KLDivergenceRegularizationEngine) -> None:
    for i in range(110):
        engine.add_record(agent_id=f"a-{i}")
    assert len(engine._records) == 100
