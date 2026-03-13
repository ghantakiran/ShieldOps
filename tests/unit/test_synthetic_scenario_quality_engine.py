"""Tests for SyntheticScenarioQualityEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.synthetic_scenario_quality_engine import (
    QualityDimension,
    QualityVerdict,
    ScenarioRealism,
    SyntheticScenarioQualityEngine,
)


@pytest.fixture()
def engine() -> SyntheticScenarioQualityEngine:
    return SyntheticScenarioQualityEngine(max_records=100)


def test_add_record(engine: SyntheticScenarioQualityEngine) -> None:
    rec = engine.add_record(
        scenario_id="sq-1",
        realism=ScenarioRealism.REALISTIC,
        dimension=QualityDimension.SOLVABILITY,
        verdict=QualityVerdict.ACCEPTED,
        realism_score=0.85,
        diversity_score=0.7,
        complexity_score=0.6,
        overall_quality=0.75,
    )
    assert rec.scenario_id == "sq-1"
    assert rec.verdict == QualityVerdict.ACCEPTED
    assert len(engine._records) == 1


def test_process(engine: SyntheticScenarioQualityEngine) -> None:
    rec = engine.add_record(scenario_id="sq-2", overall_quality=0.8, realism_score=0.9)
    result = engine.process(rec.id)
    assert hasattr(result, "scenario_id")
    assert result.scenario_id == "sq-2"  # type: ignore[union-attr]


def test_process_not_found(engine: SyntheticScenarioQualityEngine) -> None:
    result = engine.process("missing-key")
    assert result["status"] == "not_found"


def test_generate_report(engine: SyntheticScenarioQualityEngine) -> None:
    engine.add_record(
        scenario_id="sq-3", realism=ScenarioRealism.DEGENERATE, verdict=QualityVerdict.REJECTED
    )
    engine.add_record(
        scenario_id="sq-4", realism=ScenarioRealism.PLAUSIBLE, verdict=QualityVerdict.ACCEPTED
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert len(report.recommendations) > 0


def test_get_stats(engine: SyntheticScenarioQualityEngine) -> None:
    engine.add_record(scenario_id="sq-5", verdict=QualityVerdict.MARGINAL)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "verdict_distribution" in stats


def test_clear_data(engine: SyntheticScenarioQualityEngine) -> None:
    engine.add_record(scenario_id="sq-6")
    engine.clear_data()
    assert engine._records == []


def test_score_scenario_realism(engine: SyntheticScenarioQualityEngine) -> None:
    engine.add_record(scenario_id="real-1", realism_score=0.9, overall_quality=0.85)
    engine.add_record(scenario_id="real-1", realism_score=0.85, overall_quality=0.8)
    result = engine.score_scenario_realism("real-1")
    assert result["scenario_id"] == "real-1"
    assert result["realism_verdict"] == ScenarioRealism.REALISTIC.value
    assert result["avg_realism_score"] >= 0.8


def test_evaluate_scenario_diversity(engine: SyntheticScenarioQualityEngine) -> None:
    engine.add_record(scenario_id="div-1", diversity_score=0.9, overall_quality=0.8)
    engine.add_record(scenario_id="div-2", diversity_score=0.2, overall_quality=0.4)
    result = engine.evaluate_scenario_diversity()
    assert "avg_diversity" in result
    assert "total_scenarios" in result
    assert result["total_scenarios"] == 2


def test_filter_degenerate_scenarios(engine: SyntheticScenarioQualityEngine) -> None:
    engine.add_record(
        scenario_id="deg-1",
        realism=ScenarioRealism.DEGENERATE,
        verdict=QualityVerdict.REJECTED,
        overall_quality=0.1,
    )
    engine.add_record(
        scenario_id="good-1",
        realism=ScenarioRealism.REALISTIC,
        verdict=QualityVerdict.ACCEPTED,
        overall_quality=0.9,
    )
    filtered = engine.filter_degenerate_scenarios()
    assert len(filtered) == 1
    assert filtered[0]["scenario_id"] == "deg-1"
