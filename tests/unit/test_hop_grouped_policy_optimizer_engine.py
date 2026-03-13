"""Tests for HopGroupedPolicyOptimizerEngine."""

from __future__ import annotations

import pytest

from shieldops.security.hop_grouped_policy_optimizer_engine import (
    GroupingMethod,
    HopGroupedPolicyOptimizerEngine,
    OptimizationPhase,
    PolicyGroupType,
)


@pytest.fixture()
def engine() -> HopGroupedPolicyOptimizerEngine:
    return HopGroupedPolicyOptimizerEngine(max_records=100)


def test_add_record(engine: HopGroupedPolicyOptimizerEngine) -> None:
    rec = engine.add_record(
        task_id="task-1",
        group_type=PolicyGroupType.SIMPLE_DETECTION,
        optimization_phase=OptimizationPhase.GROUPING,
        grouping_method=GroupingMethod.COMPLEXITY_BASED,
        reward=0.8,
        complexity_score=0.3,
        group_id="g1",
    )
    assert rec.task_id == "task-1"
    assert rec.group_type == PolicyGroupType.SIMPLE_DETECTION
    assert rec.reward == 0.8
    assert len(engine._records) == 1


def test_process(engine: HopGroupedPolicyOptimizerEngine) -> None:
    rec = engine.add_record(task_id="task-2", reward=1.0, group_id="g2")
    result = engine.process(rec.id)
    assert hasattr(result, "task_id")
    assert result.task_id == "task-2"  # type: ignore[union-attr]
    assert isinstance(result.advantage_estimate, float)  # type: ignore[union-attr]


def test_process_not_found(engine: HopGroupedPolicyOptimizerEngine) -> None:
    result = engine.process("nonexistent-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: HopGroupedPolicyOptimizerEngine) -> None:
    engine.add_record(task_id="t1", group_type=PolicyGroupType.MULTI_STAGE, reward=0.5)
    engine.add_record(task_id="t2", group_type=PolicyGroupType.SIMPLE_DETECTION, reward=0.9)
    report = engine.generate_report()
    assert report.total_records == 2
    assert isinstance(report.by_group_type, dict)
    assert isinstance(report.recommendations, list)


def test_get_stats(engine: HopGroupedPolicyOptimizerEngine) -> None:
    engine.add_record(optimization_phase=OptimizationPhase.POLICY_UPDATE)
    stats = engine.get_stats()
    assert "total_records" in stats
    assert "phase_distribution" in stats
    assert stats["total_records"] == 1


def test_clear_data(engine: HopGroupedPolicyOptimizerEngine) -> None:
    engine.add_record(task_id="t1")
    engine.clear_data()
    assert len(engine._records) == 0
    assert len(engine._analyses) == 0


def test_group_tasks_by_complexity(engine: HopGroupedPolicyOptimizerEngine) -> None:
    engine.add_record(group_type=PolicyGroupType.SIMPLE_DETECTION, complexity_score=0.2, reward=0.5)
    engine.add_record(
        group_type=PolicyGroupType.ADVANCED_PERSISTENT, complexity_score=0.9, reward=0.7
    )
    result = engine.group_tasks_by_complexity()
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["avg_complexity"] >= result[-1]["avg_complexity"]


def test_compute_group_baselines(engine: HopGroupedPolicyOptimizerEngine) -> None:
    engine.add_record(group_id="grp-a", reward=0.4)
    engine.add_record(group_id="grp-a", reward=0.6)
    engine.add_record(group_id="grp-b", reward=1.0)
    baselines = engine.compute_group_baselines()
    assert "grp-a" in baselines
    assert baselines["grp-a"] == pytest.approx(0.5, abs=1e-3)
    assert "grp-b" in baselines


def test_compare_grouped_vs_flat(engine: HopGroupedPolicyOptimizerEngine) -> None:
    engine.add_record(group_id="g1", reward=0.8)
    engine.add_record(group_id="g1", reward=0.6)
    engine.add_record(group_id="g2", reward=0.4)
    result = engine.compare_grouped_vs_flat()
    assert "grouped_avg" in result
    assert "flat_avg" in result
    assert "improvement_pct" in result
    assert result["num_groups"] == 2


def test_max_records_eviction(engine: HopGroupedPolicyOptimizerEngine) -> None:
    for i in range(110):
        engine.add_record(task_id=f"t-{i}")
    assert len(engine._records) == 100
