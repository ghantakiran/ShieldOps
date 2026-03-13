"""Tests for GroupBaselineEstimatorEngine."""

from __future__ import annotations

import pytest

from shieldops.security.group_baseline_estimator_engine import (
    BaselineMethod,
    GroupBaselineEstimatorEngine,
    GroupSize,
    UpdateFrequency,
)


@pytest.fixture()
def engine() -> GroupBaselineEstimatorEngine:
    return GroupBaselineEstimatorEngine(max_records=100)


def test_add_record(engine: GroupBaselineEstimatorEngine) -> None:
    rec = engine.add_record(
        group_id="g1",
        task_id="task-1",
        baseline_method=BaselineMethod.GROUP_MEAN,
        group_size=GroupSize.MEDIUM_GROUP,
        update_frequency=UpdateFrequency.PER_BATCH,
        reward=0.8,
        baseline_value=0.6,
        staleness_score=0.1,
    )
    assert rec.group_id == "g1"
    assert rec.reward == 0.8
    assert len(engine._records) == 1


def test_process(engine: GroupBaselineEstimatorEngine) -> None:
    engine.add_record(group_id="g1", reward=0.4)
    engine.add_record(group_id="g1", reward=0.6)
    rec = engine.add_record(group_id="g1", reward=0.8)
    result = engine.process(rec.id)
    assert hasattr(result, "computed_baseline")
    assert isinstance(result.computed_baseline, float)  # type: ignore[union-attr]


def test_process_not_found(engine: GroupBaselineEstimatorEngine) -> None:
    result = engine.process("bad-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: GroupBaselineEstimatorEngine) -> None:
    engine.add_record(
        group_id="g1",
        baseline_method=BaselineMethod.WINDOWED,
        staleness_score=0.7,
    )
    engine.add_record(
        group_id="g2",
        baseline_method=BaselineMethod.EXPONENTIAL_DECAY,
        staleness_score=0.1,
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert "g1" in report.stale_groups


def test_get_stats(engine: GroupBaselineEstimatorEngine) -> None:
    engine.add_record(baseline_method=BaselineMethod.GROUP_MEDIAN)
    stats = engine.get_stats()
    assert "baseline_method_distribution" in stats
    assert stats["total_records"] == 1


def test_clear_data(engine: GroupBaselineEstimatorEngine) -> None:
    engine.add_record(group_id="g1")
    engine.clear_data()
    assert len(engine._records) == 0
    assert len(engine._analyses) == 0


def test_compute_group_baselines(engine: GroupBaselineEstimatorEngine) -> None:
    engine.add_record(group_id="g1", reward=0.4)
    engine.add_record(group_id="g1", reward=0.6)
    engine.add_record(group_id="g2", reward=1.0)
    result = engine.compute_group_baselines()
    assert isinstance(result, list)
    g1_entry = next(r for r in result if r["group_id"] == "g1")
    assert g1_entry["mean_baseline"] == pytest.approx(0.5, abs=1e-3)


def test_evaluate_baseline_staleness(engine: GroupBaselineEstimatorEngine) -> None:
    engine.add_record(group_id="g1", staleness_score=0.8)
    engine.add_record(group_id="g2", staleness_score=0.1)
    result = engine.evaluate_baseline_staleness()
    assert isinstance(result, list)
    assert result[0]["mean_staleness"] >= result[-1]["mean_staleness"]
    g1_entry = next(r for r in result if r["group_id"] == "g1")
    assert g1_entry["is_stale"] is True


def test_compare_baseline_methods(engine: GroupBaselineEstimatorEngine) -> None:
    engine.add_record(baseline_method=BaselineMethod.GROUP_MEAN, baseline_value=0.6)
    engine.add_record(baseline_method=BaselineMethod.GROUP_MEDIAN, baseline_value=0.55)
    result = engine.compare_baseline_methods()
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["mean_baseline"] >= result[-1]["mean_baseline"]


def test_max_records_eviction(engine: GroupBaselineEstimatorEngine) -> None:
    for i in range(110):
        engine.add_record(group_id=f"g-{i}")
    assert len(engine._records) == 100
