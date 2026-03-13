"""Tests for IncidentScenarioProposerEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.incident_scenario_proposer_engine import (
    IncidentScenarioProposerEngine,
    ProposerStrategy,
    ScenarioCategory,
    ScenarioComplexity,
)


@pytest.fixture()
def engine() -> IncidentScenarioProposerEngine:
    return IncidentScenarioProposerEngine(max_records=100)


def test_add_record(engine: IncidentScenarioProposerEngine) -> None:
    rec = engine.add_record(
        scenario_id="s1",
        complexity=ScenarioComplexity.TWO_HOP,
        category=ScenarioCategory.APPLICATION,
        strategy=ProposerStrategy.ADAPTIVE,
        novelty_score=0.7,
        difficulty_rating=0.5,
        solver_success_rate=0.65,
    )
    assert rec.scenario_id == "s1"
    assert rec.complexity == ScenarioComplexity.TWO_HOP
    assert rec.novelty_score == 0.7
    assert len(engine._records) == 1


def test_process(engine: IncidentScenarioProposerEngine) -> None:
    rec = engine.add_record(scenario_id="s2", difficulty_rating=0.6, novelty_score=0.8)
    result = engine.process(rec.id)
    assert hasattr(result, "scenario_id")
    assert result.scenario_id == "s2"  # type: ignore[union-attr]


def test_process_not_found(engine: IncidentScenarioProposerEngine) -> None:
    result = engine.process("nonexistent-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: IncidentScenarioProposerEngine) -> None:
    engine.add_record(scenario_id="s3", category=ScenarioCategory.CASCADING, difficulty_rating=0.9)
    engine.add_record(scenario_id="s4", category=ScenarioCategory.SECURITY, difficulty_rating=0.4)
    report = engine.generate_report()
    assert report.total_records == 2
    assert "cascading" in report.by_category or "security" in report.by_category


def test_get_stats(engine: IncidentScenarioProposerEngine) -> None:
    engine.add_record(scenario_id="s5", category=ScenarioCategory.INFRASTRUCTURE)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "category_distribution" in stats


def test_clear_data(engine: IncidentScenarioProposerEngine) -> None:
    engine.add_record(scenario_id="s6")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert len(engine._records) == 0


def test_generate_scenario_batch(engine: IncidentScenarioProposerEngine) -> None:
    batch = engine.generate_scenario_batch(batch_size=5, strategy=ProposerStrategy.CURRICULUM)
    assert len(batch) == 5
    for item in batch:
        assert "scenario_id" in item
        assert "difficulty_rating" in item


def test_calibrate_difficulty_to_solver(engine: IncidentScenarioProposerEngine) -> None:
    result = engine.calibrate_difficulty_to_solver(solver_success_rate=0.9)
    assert result["recommended_complexity"] == ScenarioComplexity.FOUR_HOP.value
    result2 = engine.calibrate_difficulty_to_solver(solver_success_rate=0.2)
    assert result2["recommended_complexity"] == ScenarioComplexity.SINGLE_HOP.value


def test_rank_scenarios_by_novelty(engine: IncidentScenarioProposerEngine) -> None:
    engine.add_record(scenario_id="n1", novelty_score=0.9)
    engine.add_record(scenario_id="n2", novelty_score=0.3)
    engine.add_record(scenario_id="n3", novelty_score=0.6)
    ranked = engine.rank_scenarios_by_novelty()
    assert ranked[0]["novelty_score"] >= ranked[1]["novelty_score"]
    assert ranked[0]["rank"] == 1


def test_max_records_eviction(engine: IncidentScenarioProposerEngine) -> None:
    eng = IncidentScenarioProposerEngine(max_records=3)
    for i in range(5):
        eng.add_record(scenario_id=f"s{i}")
    assert len(eng._records) == 3
