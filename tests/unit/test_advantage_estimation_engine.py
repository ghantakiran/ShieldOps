"""Tests for AdvantageEstimationEngine."""

from __future__ import annotations

import pytest

from shieldops.security.advantage_estimation_engine import (
    AdvantageEstimationEngine,
    AdvantageSign,
    BaselineType,
    EstimationMethod,
)


@pytest.fixture()
def engine() -> AdvantageEstimationEngine:
    return AdvantageEstimationEngine(max_records=100)


def test_add_record(engine: AdvantageEstimationEngine) -> None:
    rec = engine.add_record(
        task_id="task-1",
        group_id="g1",
        estimation_method=EstimationMethod.GROUP_RELATIVE,
        advantage_sign=AdvantageSign.POSITIVE,
        baseline_type=BaselineType.GROUP_MEAN,
        reward=1.0,
        baseline_value=0.5,
        advantage_value=0.5,
    )
    assert rec.task_id == "task-1"
    assert rec.reward == 1.0
    assert len(engine._records) == 1


def test_process(engine: AdvantageEstimationEngine) -> None:
    rec = engine.add_record(task_id="t1", group_id="g1", reward=1.0, baseline_value=0.5)
    result = engine.process(rec.id)
    assert hasattr(result, "computed_advantage")
    assert result.computed_advantage == pytest.approx(0.5, abs=1e-3)  # type: ignore[union-attr]


def test_process_not_found(engine: AdvantageEstimationEngine) -> None:
    result = engine.process("bad-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: AdvantageEstimationEngine) -> None:
    engine.add_record(estimation_method=EstimationMethod.GAE, advantage_value=0.3)
    engine.add_record(estimation_method=EstimationMethod.TEMPORAL_DIFFERENCE, advantage_value=0.1)
    report = engine.generate_report()
    assert report.total_records == 2
    assert isinstance(report.by_estimation_method, dict)


def test_get_stats(engine: AdvantageEstimationEngine) -> None:
    engine.add_record(estimation_method=EstimationMethod.GLOBAL_RELATIVE)
    stats = engine.get_stats()
    assert "method_distribution" in stats
    assert stats["total_records"] == 1


def test_clear_data(engine: AdvantageEstimationEngine) -> None:
    engine.add_record(task_id="t1")
    engine.clear_data()
    assert len(engine._records) == 0
    assert len(engine._analyses) == 0


def test_compute_group_advantages(engine: AdvantageEstimationEngine) -> None:
    engine.add_record(group_id="g1", reward=1.0, baseline_value=0.5)
    engine.add_record(group_id="g1", reward=0.8, baseline_value=0.5)
    engine.add_record(group_id="g2", reward=0.3, baseline_value=0.6)
    result = engine.compute_group_advantages()
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["mean_advantage"] >= result[-1]["mean_advantage"]


def test_analyze_advantage_stability(engine: AdvantageEstimationEngine) -> None:
    engine.add_record(group_id="g1", reward=1.0, baseline_value=0.5)
    engine.add_record(group_id="g1", reward=1.0, baseline_value=0.5)
    result = engine.analyze_advantage_stability()
    assert isinstance(result, list)
    assert "variance" in result[0]


def test_visualize_advantage_landscape(engine: AdvantageEstimationEngine) -> None:
    engine.add_record(
        estimation_method=EstimationMethod.GROUP_RELATIVE, reward=1.0, baseline_value=0.5
    )
    engine.add_record(estimation_method=EstimationMethod.GAE, reward=0.8, baseline_value=0.6)
    result = engine.visualize_advantage_landscape()
    assert "landscape" in result
    assert "total_methods" in result
    assert result["total_methods"] >= 1


def test_max_records_eviction(engine: AdvantageEstimationEngine) -> None:
    for i in range(110):
        engine.add_record(task_id=f"t-{i}")
    assert len(engine._records) == 100
