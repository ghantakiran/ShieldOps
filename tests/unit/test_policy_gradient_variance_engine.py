"""Tests for PolicyGradientVarianceEngine."""

from __future__ import annotations

import pytest

from shieldops.security.policy_gradient_variance_engine import (
    PolicyGradientVarianceEngine,
    ReductionTechnique,
    VarianceLevel,
    VarianceSource,
)


@pytest.fixture()
def engine() -> PolicyGradientVarianceEngine:
    return PolicyGradientVarianceEngine(max_records=100)


def test_add_record(engine: PolicyGradientVarianceEngine) -> None:
    rec = engine.add_record(
        task_id="task-1",
        group_id="g1",
        variance_source=VarianceSource.REWARD_NOISE,
        reduction_technique=ReductionTechnique.HOP_GROUPING,
        variance_level=VarianceLevel.LOW,
        raw_variance=0.4,
        reduced_variance=0.1,
        reward=0.8,
    )
    assert rec.task_id == "task-1"
    assert rec.raw_variance == 0.4
    assert len(engine._records) == 1


def test_process(engine: PolicyGradientVarianceEngine) -> None:
    rec = engine.add_record(task_id="t1", raw_variance=0.4, reduced_variance=0.2)
    result = engine.process(rec.id)
    assert hasattr(result, "variance_reduction_pct")
    assert result.variance_reduction_pct == pytest.approx(50.0, abs=0.1)  # type: ignore[union-attr]


def test_process_not_found(engine: PolicyGradientVarianceEngine) -> None:
    result = engine.process("nonexistent")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: PolicyGradientVarianceEngine) -> None:
    engine.add_record(
        variance_source=VarianceSource.SAMPLE_BIAS,
        variance_level=VarianceLevel.CRITICAL,
        group_id="g1",
        raw_variance=1.0,
        reduced_variance=0.5,
    )
    engine.add_record(
        variance_source=VarianceSource.TEMPORAL_SHIFT,
        variance_level=VarianceLevel.LOW,
        raw_variance=0.1,
        reduced_variance=0.05,
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert "critical" in report.by_variance_level
    assert len(report.high_variance_groups) >= 1


def test_get_stats(engine: PolicyGradientVarianceEngine) -> None:
    engine.add_record(variance_source=VarianceSource.GROUP_HETEROGENEITY)
    stats = engine.get_stats()
    assert "variance_source_distribution" in stats
    assert stats["total_records"] == 1


def test_clear_data(engine: PolicyGradientVarianceEngine) -> None:
    engine.add_record(task_id="t1")
    engine.clear_data()
    assert len(engine._records) == 0
    assert len(engine._analyses) == 0


def test_measure_gradient_variance(engine: PolicyGradientVarianceEngine) -> None:
    engine.add_record(group_id="g1", raw_variance=0.5)
    engine.add_record(group_id="g1", raw_variance=0.3)
    engine.add_record(group_id="g2", raw_variance=0.9)
    result = engine.measure_gradient_variance()
    assert isinstance(result, list)
    assert result[0]["mean_variance"] >= result[-1]["mean_variance"]


def test_decompose_variance_sources(engine: PolicyGradientVarianceEngine) -> None:
    engine.add_record(variance_source=VarianceSource.REWARD_NOISE, raw_variance=0.6)
    engine.add_record(variance_source=VarianceSource.SAMPLE_BIAS, raw_variance=0.4)
    result = engine.decompose_variance_sources()
    assert isinstance(result, dict)
    total_pct = sum(result.values())
    assert total_pct == pytest.approx(100.0, abs=0.1)


def test_apply_variance_reduction(engine: PolicyGradientVarianceEngine) -> None:
    engine.add_record(
        reduction_technique=ReductionTechnique.BASELINE_SUBTRACTION,
        raw_variance=0.8,
        reduced_variance=0.2,
    )
    engine.add_record(
        reduction_technique=ReductionTechnique.CLIPPING,
        raw_variance=0.6,
        reduced_variance=0.4,
    )
    result = engine.apply_variance_reduction()
    assert isinstance(result, list)
    assert result[0]["reduction_pct"] >= result[-1]["reduction_pct"]


def test_max_records_eviction(engine: PolicyGradientVarianceEngine) -> None:
    for i in range(110):
        engine.add_record(task_id=f"t-{i}")
    assert len(engine._records) == 100
