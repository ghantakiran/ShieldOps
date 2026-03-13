"""Tests for RewardSignalEngineeringEngine."""

from __future__ import annotations

from shieldops.analytics.reward_signal_engineering_engine import (
    OptimizationGoal,
    RewardSignalEngineeringEngine,
    RewardType,
    SignalQuality,
)


def _engine(**kw) -> RewardSignalEngineeringEngine:
    return RewardSignalEngineeringEngine(**kw)


def test_add_record_basic():
    eng = _engine()
    r = eng.add_record(agent_id="a1", reward_value=0.8)
    assert r.agent_id == "a1"
    assert r.reward_value == 0.8


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(6):
        eng.add_record(agent_id=f"a{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(agent_id="a1", reward_value=0.9)
    analysis = eng.process(r.id)
    assert hasattr(analysis, "agent_id")
    assert analysis.agent_id == "a1"


def test_process_not_found():
    result = _engine().process("missing-key")
    assert result["status"] == "not_found"


def test_generate_report_populated():
    eng = _engine()
    eng.add_record(agent_id="a1", reward_type=RewardType.DENSE, reward_value=0.7)
    eng.add_record(agent_id="a2", reward_type=RewardType.SPARSE, reward_value=0.5)
    rpt = eng.generate_report()
    assert rpt.total_records == 2
    assert "dense" in rpt.by_reward_type or "sparse" in rpt.by_reward_type


def test_generate_report_empty():
    rpt = _engine().generate_report()
    assert rpt.total_records == 0
    assert rpt.avg_reward == 0.0


def test_get_stats():
    eng = _engine()
    eng.add_record(agent_id="a1", reward_type=RewardType.INTRINSIC)
    stats = eng.get_stats()
    assert stats["total_records"] == 1
    assert "intrinsic" in stats["reward_type_distribution"]


def test_clear_data():
    eng = _engine()
    eng.add_record(agent_id="a1")
    eng.clear_data()
    assert len(eng._records) == 0
    assert eng.get_stats()["total_records"] == 0


def test_design_reward_functions():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        reward_type=RewardType.SPARSE,
        optimization_goal=OptimizationGoal.MAXIMIZE_THROUGHPUT,
        reward_value=0.3,
    )
    eng.add_record(agent_id="a1", reward_type=RewardType.DENSE, reward_value=0.8)
    eng.add_record(agent_id="a2", reward_type=RewardType.SHAPED, reward_value=0.9)
    result = eng.design_reward_functions()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "agent_id" in result[0]
    assert "recommended_type" in result[0]


def test_evaluate_signal_quality():
    eng = _engine()
    eng.add_record(agent_id="a1", signal_quality=SignalQuality.CLEAN, noise_level=0.01)
    eng.add_record(agent_id="a1", signal_quality=SignalQuality.NOISY, noise_level=0.5)
    eng.add_record(agent_id="a2", signal_quality=SignalQuality.CORRUPTED, noise_level=0.9)
    result = eng.evaluate_signal_quality()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "overall_score" in result[0]


def test_optimize_reward_shaping():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        optimization_goal=OptimizationGoal.MINIMIZE_LATENCY,
        reward_value=0.4,
    )
    eng.add_record(
        agent_id="a2",
        optimization_goal=OptimizationGoal.BALANCE_COST,
        reward_value=0.9,
    )
    result = eng.optimize_reward_shaping()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "shaping_suggestion" in result[0]
    assert "needs_adjustment" in result[0]
