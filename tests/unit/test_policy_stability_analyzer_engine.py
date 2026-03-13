"""Tests for PolicyStabilityAnalyzerEngine."""

from __future__ import annotations

import pytest

from shieldops.security.policy_stability_analyzer_engine import (
    InstabilityIndicator,
    PolicyStabilityAnalyzerEngine,
    RemediationAction,
    StabilityStatus,
)


@pytest.fixture()
def engine() -> PolicyStabilityAnalyzerEngine:
    return PolicyStabilityAnalyzerEngine(max_records=100)


def test_add_record(engine: PolicyStabilityAnalyzerEngine) -> None:
    rec = engine.add_record(
        agent_id="agent-1",
        stability_status=StabilityStatus.CRITICAL,
        instability_indicator=InstabilityIndicator.MODE_COLLAPSE,
        remediation_action=RemediationAction.RESET_TO_CHECKPOINT,
        entropy=0.05,
        reward_variance=2.5,
        gradient_norm=0.001,
        training_step=500,
    )
    assert rec.agent_id == "agent-1"
    assert rec.entropy == 0.05
    assert len(engine._records) == 1


def test_process(engine: PolicyStabilityAnalyzerEngine) -> None:
    rec = engine.add_record(
        agent_id="a1",
        stability_status=StabilityStatus.CRITICAL,
        entropy=0.05,
    )
    result = engine.process(rec.id)
    assert hasattr(result, "stability_score")
    assert result.stability_score == 0.0  # type: ignore[union-attr]
    assert result.recommended_action == RemediationAction.RESET_TO_CHECKPOINT  # type: ignore[union-attr]


def test_process_not_found(engine: PolicyStabilityAnalyzerEngine) -> None:
    result = engine.process("bad-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: PolicyStabilityAnalyzerEngine) -> None:
    engine.add_record(
        agent_id="a1",
        stability_status=StabilityStatus.CRITICAL,
        entropy=0.03,
        reward_variance=3.0,
    )
    engine.add_record(
        agent_id="a2",
        stability_status=StabilityStatus.STABLE,
        entropy=1.5,
        reward_variance=0.1,
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert "a1" in report.critical_agents


def test_get_stats(engine: PolicyStabilityAnalyzerEngine) -> None:
    engine.add_record(stability_status=StabilityStatus.MARGINALLY_STABLE)
    stats = engine.get_stats()
    assert "stability_status_distribution" in stats
    assert stats["total_records"] == 1


def test_clear_data(engine: PolicyStabilityAnalyzerEngine) -> None:
    engine.add_record(agent_id="a1")
    engine.clear_data()
    assert len(engine._records) == 0
    assert len(engine._analyses) == 0


def test_assess_policy_stability(engine: PolicyStabilityAnalyzerEngine) -> None:
    engine.add_record(agent_id="a1", stability_status=StabilityStatus.STABLE)
    engine.add_record(agent_id="a2", stability_status=StabilityStatus.CRITICAL)
    result = engine.assess_policy_stability()
    assert isinstance(result, list)
    a1_entry = next(r for r in result if r["agent_id"] == "a1")
    assert a1_entry["is_stable"] is True
    a2_entry = next(r for r in result if r["agent_id"] == "a2")
    assert a2_entry["is_stable"] is False


def test_detect_entropy_collapse(engine: PolicyStabilityAnalyzerEngine) -> None:
    engine.add_record(agent_id="collapse", entropy=0.05, training_step=200)
    engine.add_record(agent_id="normal", entropy=1.8, training_step=200)
    result = engine.detect_entropy_collapse()
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["agent_id"] == "collapse"


def test_recommend_stabilization(engine: PolicyStabilityAnalyzerEngine) -> None:
    engine.add_record(
        agent_id="a1",
        stability_status=StabilityStatus.UNSTABLE,
        entropy=0.5,
        training_step=300,
    )
    engine.add_record(
        agent_id="a2",
        stability_status=StabilityStatus.STABLE,
        entropy=1.5,
        training_step=300,
    )
    result = engine.recommend_stabilization()
    assert isinstance(result, list)
    a1_entry = next(r for r in result if r["agent_id"] == "a1")
    assert a1_entry["recommended_action"] == RemediationAction.REDUCE_LEARNING_RATE.value


def test_max_records_eviction(engine: PolicyStabilityAnalyzerEngine) -> None:
    for i in range(110):
        engine.add_record(agent_id=f"a-{i}")
    assert len(engine._records) == 100
