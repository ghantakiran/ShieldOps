"""Tests for CoevolutionComputeEfficiencyEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.coevolution_compute_efficiency_engine import (
    BatchConfiguration,
    CoevolutionComputeEfficiencyEngine,
    EfficiencyMetric,
    GroupingStrategy,
)


@pytest.fixture()
def engine() -> CoevolutionComputeEfficiencyEngine:
    return CoevolutionComputeEfficiencyEngine(max_records=100)


def test_add_record(engine: CoevolutionComputeEfficiencyEngine) -> None:
    rec = engine.add_record(
        experiment_id="exp-1",
        grouping=GroupingStrategy.HOP_GROUPED,
        batch_config=BatchConfiguration.LARGE_BATCH,
        metric=EfficiencyMetric.THROUGHPUT,
        throughput=50.0,
        latency_ms=200.0,
        cost_per_sample=0.01,
        memory_gb=4.0,
        speedup_ratio=2.0,
    )
    assert rec.experiment_id == "exp-1"
    assert rec.grouping == GroupingStrategy.HOP_GROUPED
    assert len(engine._records) == 1


def test_process(engine: CoevolutionComputeEfficiencyEngine) -> None:
    rec = engine.add_record(experiment_id="exp-2", throughput=30.0, speedup_ratio=1.5)
    result = engine.process(rec.id)
    assert hasattr(result, "experiment_id")
    assert result.experiment_id == "exp-2"  # type: ignore[union-attr]


def test_process_not_found(engine: CoevolutionComputeEfficiencyEngine) -> None:
    result = engine.process("nonexistent")
    assert result["status"] == "not_found"


def test_generate_report(engine: CoevolutionComputeEfficiencyEngine) -> None:
    engine.add_record(experiment_id="e1", grouping=GroupingStrategy.UNGROUPED, throughput=10.0)
    engine.add_record(experiment_id="e2", grouping=GroupingStrategy.HOP_GROUPED, throughput=45.0)
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.avg_throughput > 0


def test_get_stats(engine: CoevolutionComputeEfficiencyEngine) -> None:
    engine.add_record(experiment_id="e3", grouping=GroupingStrategy.ADAPTIVE_GROUPED)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "grouping_distribution" in stats


def test_clear_data(engine: CoevolutionComputeEfficiencyEngine) -> None:
    engine.add_record(experiment_id="e4")
    engine.clear_data()
    assert engine._records == []


def test_benchmark_grouping_strategies(engine: CoevolutionComputeEfficiencyEngine) -> None:
    engine.add_record(
        experiment_id="bench-1",
        grouping=GroupingStrategy.HOP_GROUPED,
        throughput=60.0,
        latency_ms=100.0,
        speedup_ratio=3.0,
    )
    engine.add_record(
        experiment_id="bench-2",
        grouping=GroupingStrategy.UNGROUPED,
        throughput=20.0,
        latency_ms=300.0,
        speedup_ratio=1.0,
    )
    results = engine.benchmark_grouping_strategies()
    assert len(results) >= 2
    assert results[0]["avg_throughput"] >= results[1]["avg_throughput"]


def test_compute_speedup_ratio(engine: CoevolutionComputeEfficiencyEngine) -> None:
    engine.add_record(
        experiment_id="sp-1",
        grouping=GroupingStrategy.UNGROUPED,
        throughput=20.0,
    )
    engine.add_record(
        experiment_id="sp-2",
        grouping=GroupingStrategy.HOP_GROUPED,
        throughput=60.0,
    )
    result = engine.compute_speedup_ratio(baseline_strategy=GroupingStrategy.UNGROUPED)
    assert "speedup_ratios" in result
    hop_speedup = result["speedup_ratios"].get(GroupingStrategy.HOP_GROUPED.value, 0)
    assert hop_speedup == pytest.approx(3.0, abs=0.1)


def test_optimize_batch_size(engine: CoevolutionComputeEfficiencyEngine) -> None:
    engine.add_record(
        experiment_id="opt-1",
        batch_config=BatchConfiguration.LARGE_BATCH,
        throughput=80.0,
        memory_gb=8.0,
        cost_per_sample=0.005,
    )
    engine.add_record(
        experiment_id="opt-2",
        batch_config=BatchConfiguration.SMALL_BATCH,
        throughput=20.0,
        memory_gb=1.0,
        cost_per_sample=0.02,
    )
    result = engine.optimize_batch_size()
    assert "recommended_batch_config" in result
    assert "batch_rankings" in result
    assert len(result["batch_rankings"]) >= 2
