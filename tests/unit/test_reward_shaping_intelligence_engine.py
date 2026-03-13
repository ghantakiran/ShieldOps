"""Tests for RewardShapingIntelligenceEngine."""

from __future__ import annotations

import pytest

from shieldops.security.reward_shaping_intelligence_engine import (
    RewardShape,
    RewardShapingIntelligenceEngine,
    ShapingObjective,
    TaskDifficulty,
)


@pytest.fixture()
def engine() -> RewardShapingIntelligenceEngine:
    return RewardShapingIntelligenceEngine(max_records=100)


def test_add_record(engine: RewardShapingIntelligenceEngine) -> None:
    rec = engine.add_record(
        task_id="task-1",
        agent_id="agent-1",
        reward_shape=RewardShape.EXPONENTIAL,
        task_difficulty=TaskDifficulty.EXTREME,
        shaping_objective=ShapingObjective.CURRICULUM,
        raw_reward=0.5,
        shaped_reward=1.0,
        hacking_score=0.1,
    )
    assert rec.task_id == "task-1"
    assert rec.shaped_reward == 1.0
    assert len(engine._records) == 1


def test_process(engine: RewardShapingIntelligenceEngine) -> None:
    rec = engine.add_record(
        task_id="t1",
        task_difficulty=TaskDifficulty.EXTREME,
        shaped_reward=1.0,
        hacking_score=0.5,
    )
    result = engine.process(rec.id)
    assert hasattr(result, "shaping_multiplier")
    assert result.shaping_multiplier == 2.0  # type: ignore[union-attr]


def test_process_not_found(engine: RewardShapingIntelligenceEngine) -> None:
    result = engine.process("bad-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: RewardShapingIntelligenceEngine) -> None:
    engine.add_record(agent_id="hacker", hacking_score=0.9, task_difficulty=TaskDifficulty.TRIVIAL)
    engine.add_record(
        agent_id="good", hacking_score=0.1, task_difficulty=TaskDifficulty.CHALLENGING
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert "hacker" in report.hacking_suspects


def test_get_stats(engine: RewardShapingIntelligenceEngine) -> None:
    engine.add_record(task_difficulty=TaskDifficulty.MODERATE)
    stats = engine.get_stats()
    assert "difficulty_distribution" in stats
    assert stats["total_records"] == 1


def test_clear_data(engine: RewardShapingIntelligenceEngine) -> None:
    engine.add_record(task_id="t1")
    engine.clear_data()
    assert len(engine._records) == 0
    assert len(engine._analyses) == 0


def test_shape_security_reward(engine: RewardShapingIntelligenceEngine) -> None:
    engine.add_record(task_id="t1", task_difficulty=TaskDifficulty.TRIVIAL, raw_reward=1.0)
    engine.add_record(task_id="t2", task_difficulty=TaskDifficulty.EXTREME, raw_reward=1.0)
    result = engine.shape_security_reward()
    assert isinstance(result, list)
    assert result[0]["shaped_reward"] >= result[-1]["shaped_reward"]


def test_calibrate_reward_scale(engine: RewardShapingIntelligenceEngine) -> None:
    engine.add_record(task_difficulty=TaskDifficulty.TRIVIAL, shaped_reward=0.5)
    engine.add_record(task_difficulty=TaskDifficulty.CHALLENGING, shaped_reward=1.5)
    result = engine.calibrate_reward_scale()
    assert "calibration" in result
    assert "total_tiers" in result
    assert result["total_tiers"] >= 1


def test_detect_reward_hacking(engine: RewardShapingIntelligenceEngine) -> None:
    engine.add_record(agent_id="hacker", hacking_score=0.95)
    engine.add_record(agent_id="hacker", hacking_score=0.85)
    engine.add_record(agent_id="normal", hacking_score=0.1)
    result = engine.detect_reward_hacking()
    assert isinstance(result, list)
    assert result[0]["agent_id"] == "hacker"
    assert result[0]["suspected"] is True


def test_max_records_eviction(engine: RewardShapingIntelligenceEngine) -> None:
    for i in range(110):
        engine.add_record(task_id=f"t-{i}")
    assert len(engine._records) == 100
