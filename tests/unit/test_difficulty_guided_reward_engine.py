"""Tests for DifficultyGuidedRewardEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.difficulty_guided_reward_engine import (
    DifficultyGuidedRewardEngine,
    FormatRewardLevel,
    PenaltyType,
    RewardZone,
)


@pytest.fixture()
def engine() -> DifficultyGuidedRewardEngine:
    return DifficultyGuidedRewardEngine(max_records=100)


def test_add_record(engine: DifficultyGuidedRewardEngine) -> None:
    rec = engine.add_record(
        solver_id="s1",
        reward_zone=RewardZone.PRODUCTIVE,
        format_reward=FormatRewardLevel.FULL,
        penalty_type=PenaltyType.NO_PENALTY,
        raw_reward=0.75,
        difficulty_score=0.5,
        correctness_score=0.8,
    )
    assert rec.solver_id == "s1"
    assert rec.reward_zone == RewardZone.PRODUCTIVE
    assert len(engine._records) == 1


def test_process(engine: DifficultyGuidedRewardEngine) -> None:
    rec = engine.add_record(solver_id="s2", reward_zone=RewardZone.CHALLENGING, raw_reward=0.9)
    result = engine.process(rec.id)
    assert hasattr(result, "solver_id")
    assert result.solver_id == "s2"  # type: ignore[union-attr]


def test_process_not_found(engine: DifficultyGuidedRewardEngine) -> None:
    result = engine.process("missing")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: DifficultyGuidedRewardEngine) -> None:
    engine.add_record(solver_id="s3", reward_zone=RewardZone.TRIVIAL, raw_reward=-0.5)
    engine.add_record(solver_id="s4", reward_zone=RewardZone.PRODUCTIVE, raw_reward=0.8)
    report = engine.generate_report()
    assert report.total_records == 2
    assert "trivial" in report.by_zone or "productive" in report.by_zone


def test_get_stats(engine: DifficultyGuidedRewardEngine) -> None:
    engine.add_record(solver_id="s5", reward_zone=RewardZone.IMPOSSIBLE)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "zone_distribution" in stats


def test_clear_data(engine: DifficultyGuidedRewardEngine) -> None:
    engine.add_record(solver_id="s6")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine._records == []


def test_compute_difficulty_reward(engine: DifficultyGuidedRewardEngine) -> None:
    result = engine.compute_difficulty_reward(difficulty_score=0.5, correctness_score=0.8)
    assert result["reward_zone"] == RewardZone.PRODUCTIVE.value
    result2 = engine.compute_difficulty_reward(difficulty_score=0.1, correctness_score=0.9)
    assert result2["reward_zone"] == RewardZone.TRIVIAL.value
    assert result2["final_reward"] < 0


def test_analyze_reward_distribution(engine: DifficultyGuidedRewardEngine) -> None:
    engine.add_record(solver_id="r1", reward_zone=RewardZone.PRODUCTIVE, raw_reward=0.7)
    engine.add_record(solver_id="r2", reward_zone=RewardZone.PRODUCTIVE, raw_reward=0.9)
    engine.add_record(solver_id="r3", reward_zone=RewardZone.TRIVIAL, raw_reward=-0.5)
    dist = engine.analyze_reward_distribution()
    assert "productive" in dist
    assert dist["productive"]["count"] == 2


def test_optimize_difficulty_ratio(engine: DifficultyGuidedRewardEngine) -> None:
    for _ in range(6):
        engine.add_record(solver_id="opt", reward_zone=RewardZone.PRODUCTIVE, raw_reward=0.8)
    for _ in range(4):
        engine.add_record(solver_id="opt", reward_zone=RewardZone.TRIVIAL, raw_reward=-0.5)
    result = engine.optimize_difficulty_ratio()
    assert "current_ratios" in result
    assert "productive_ratio" in result
    assert "is_optimal" in result
