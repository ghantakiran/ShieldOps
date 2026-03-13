"""Tests for SelfPlayBenchmarkEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.self_play_benchmark_engine import (
    BenchmarkMetric,
    ComparisonOutcome,
    SelfPlayBenchmarkEngine,
    TrainingParadigm,
)


@pytest.fixture()
def engine() -> SelfPlayBenchmarkEngine:
    return SelfPlayBenchmarkEngine(max_records=100)


def test_add_record(engine: SelfPlayBenchmarkEngine) -> None:
    rec = engine.add_record(
        benchmark_id="bm-1",
        paradigm=TrainingParadigm.SELF_PLAY,
        metric=BenchmarkMetric.ACCURACY,
        outcome=ComparisonOutcome.SELF_PLAY_WINS,
        score=0.88,
        baseline_score=0.72,
        data_efficiency=1.4,
        generalization_gap=0.05,
    )
    assert rec.benchmark_id == "bm-1"
    assert rec.paradigm == TrainingParadigm.SELF_PLAY
    assert len(engine._records) == 1


def test_process(engine: SelfPlayBenchmarkEngine) -> None:
    rec = engine.add_record(benchmark_id="bm-2", score=0.9, paradigm=TrainingParadigm.HYBRID)
    result = engine.process(rec.id)
    assert hasattr(result, "benchmark_id")
    assert result.benchmark_id == "bm-2"  # type: ignore[union-attr]


def test_process_not_found(engine: SelfPlayBenchmarkEngine) -> None:
    result = engine.process("no-id")
    assert result["status"] == "not_found"


def test_generate_report(engine: SelfPlayBenchmarkEngine) -> None:
    engine.add_record(
        benchmark_id="b1",
        paradigm=TrainingParadigm.SELF_PLAY,
        outcome=ComparisonOutcome.SELF_PLAY_WINS,
        score=0.9,
    )
    engine.add_record(
        benchmark_id="b2",
        paradigm=TrainingParadigm.SUPERVISED,
        outcome=ComparisonOutcome.SUPERVISED_WINS,
        score=0.85,
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert len(report.recommendations) > 0


def test_get_stats(engine: SelfPlayBenchmarkEngine) -> None:
    engine.add_record(benchmark_id="b3", paradigm=TrainingParadigm.SEMI_SUPERVISED)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "paradigm_distribution" in stats


def test_clear_data(engine: SelfPlayBenchmarkEngine) -> None:
    engine.add_record(benchmark_id="b4")
    engine.clear_data()
    assert engine._records == []


def test_run_comparative_benchmark(engine: SelfPlayBenchmarkEngine) -> None:
    engine.add_record(
        benchmark_id="cmp-1",
        paradigm=TrainingParadigm.SELF_PLAY,
        score=0.88,
        data_efficiency=1.5,
        generalization_gap=0.04,
    )
    engine.add_record(
        benchmark_id="cmp-2",
        paradigm=TrainingParadigm.SUPERVISED,
        score=0.82,
        data_efficiency=1.0,
        generalization_gap=0.08,
    )
    results = engine.run_comparative_benchmark()
    assert len(results) >= 2
    assert results[0]["avg_score"] >= results[1]["avg_score"]


def test_measure_generalization_gap(engine: SelfPlayBenchmarkEngine) -> None:
    engine.add_record(
        benchmark_id="gap-1",
        paradigm=TrainingParadigm.SELF_PLAY,
        generalization_gap=0.03,
    )
    engine.add_record(
        benchmark_id="gap-2",
        paradigm=TrainingParadigm.SUPERVISED,
        generalization_gap=0.09,
    )
    result = engine.measure_generalization_gap()
    assert "self_play_gap" in result
    assert "supervised_gap" in result
    assert result["self_play_generalizes_better"] is True


def test_compute_data_efficiency_ratio(engine: SelfPlayBenchmarkEngine) -> None:
    engine.add_record(
        benchmark_id="eff-1",
        paradigm=TrainingParadigm.SELF_PLAY,
        data_efficiency=2.0,
    )
    engine.add_record(
        benchmark_id="eff-2",
        paradigm=TrainingParadigm.SUPERVISED,
        data_efficiency=1.0,
    )
    result = engine.compute_data_efficiency_ratio()
    assert "efficiency_ratio" in result
    assert result["efficiency_ratio"] == pytest.approx(2.0, abs=0.01)
    assert result["self_play_more_efficient"] is True
