"""Tests for OutcomeBasedRewardScorerEngine."""

from __future__ import annotations

import pytest

from shieldops.security.outcome_based_reward_scorer_engine import (
    OutcomeBasedRewardScorerEngine,
    OutcomeType,
    RewardGranularity,
    VerificationMethod,
)


@pytest.fixture()
def engine() -> OutcomeBasedRewardScorerEngine:
    return OutcomeBasedRewardScorerEngine(max_records=100)


def test_add_record(engine: OutcomeBasedRewardScorerEngine) -> None:
    rec = engine.add_record(
        task_id="task-1",
        agent_id="agent-1",
        outcome_type=OutcomeType.CORRECT_DETECTION,
        verification_method=VerificationMethod.GROUND_TRUTH,
        reward_granularity=RewardGranularity.GRADED,
        outcome_score=0.9,
        difficulty_score=0.6,
        reward_value=1.0,
    )
    assert rec.task_id == "task-1"
    assert rec.outcome_score == 0.9
    assert len(engine._records) == 1


def test_process(engine: OutcomeBasedRewardScorerEngine) -> None:
    rec = engine.add_record(
        task_id="t1",
        outcome_type=OutcomeType.CORRECT_DETECTION,
        difficulty_score=0.5,
        reward_value=1.0,
    )
    result = engine.process(rec.id)
    assert hasattr(result, "is_correct")
    assert result.is_correct is True  # type: ignore[union-attr]
    assert result.computed_reward > 0  # type: ignore[union-attr]


def test_process_not_found(engine: OutcomeBasedRewardScorerEngine) -> None:
    result = engine.process("bad-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: OutcomeBasedRewardScorerEngine) -> None:
    engine.add_record(agent_id="low", outcome_score=0.1, outcome_type=OutcomeType.MISSED_THREAT)
    engine.add_record(
        agent_id="good",
        outcome_score=0.95,
        outcome_type=OutcomeType.CORRECT_DETECTION,
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert "missed_threat" in report.by_outcome_type


def test_get_stats(engine: OutcomeBasedRewardScorerEngine) -> None:
    engine.add_record(outcome_type=OutcomeType.FALSE_POSITIVE)
    stats = engine.get_stats()
    assert "outcome_type_distribution" in stats
    assert stats["total_records"] == 1


def test_clear_data(engine: OutcomeBasedRewardScorerEngine) -> None:
    engine.add_record(task_id="t1")
    engine.clear_data()
    assert len(engine._records) == 0
    assert len(engine._analyses) == 0


def test_score_outcome(engine: OutcomeBasedRewardScorerEngine) -> None:
    engine.add_record(outcome_type=OutcomeType.CORRECT_DETECTION, reward_value=1.0)
    engine.add_record(outcome_type=OutcomeType.MISSED_THREAT, reward_value=1.0)
    result = engine.score_outcome()
    assert isinstance(result, list)
    assert result[0]["scored_reward"] >= result[-1]["scored_reward"]
    neg = next(r for r in result if r["outcome_type"] == "missed_threat")
    assert neg["scored_reward"] < 0


def test_aggregate_outcome_statistics(engine: OutcomeBasedRewardScorerEngine) -> None:
    engine.add_record(outcome_type=OutcomeType.CORRECT_DETECTION, reward_value=1.0)
    engine.add_record(outcome_type=OutcomeType.CORRECT_DETECTION, reward_value=0.8)
    engine.add_record(outcome_type=OutcomeType.FALSE_POSITIVE, reward_value=0.5)
    result = engine.aggregate_outcome_statistics()
    assert "outcome_stats" in result
    stats = result["outcome_stats"]
    assert "correct_detection" in stats
    assert stats["correct_detection"]["count"] == 2.0


def test_correlate_outcome_with_difficulty(
    engine: OutcomeBasedRewardScorerEngine,
) -> None:
    engine.add_record(outcome_type=OutcomeType.CORRECT_DETECTION, difficulty_score=0.3)
    engine.add_record(outcome_type=OutcomeType.MISSED_THREAT, difficulty_score=0.9)
    result = engine.correlate_outcome_with_difficulty()
    assert isinstance(result, list)
    # should be sorted by difficulty_bin ascending
    if len(result) >= 2:
        assert result[0]["difficulty_bin"] <= result[-1]["difficulty_bin"]


def test_max_records_eviction(engine: OutcomeBasedRewardScorerEngine) -> None:
    for i in range(110):
        engine.add_record(task_id=f"t-{i}")
    assert len(engine._records) == 100
