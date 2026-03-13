"""Tests for AutomatedCurriculumProgressionEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.automated_curriculum_progression_engine import (
    AutomatedCurriculumProgressionEngine,
    CurriculumStage,
    DifficultyAdjustment,
    ProgressionTrigger,
)


@pytest.fixture()
def engine() -> AutomatedCurriculumProgressionEngine:
    return AutomatedCurriculumProgressionEngine(max_records=100)


def test_add_record(engine: AutomatedCurriculumProgressionEngine) -> None:
    rec = engine.add_record(
        curriculum_id="cur-1",
        stage=CurriculumStage.FOUNDATION,
        trigger=ProgressionTrigger.SCORE_THRESHOLD,
        adjustment=DifficultyAdjustment.INCREASE,
        current_difficulty=0.2,
        solver_score=0.85,
        iteration=1,
    )
    assert rec.curriculum_id == "cur-1"
    assert rec.stage == CurriculumStage.FOUNDATION
    assert len(engine._records) == 1


def test_process(engine: AutomatedCurriculumProgressionEngine) -> None:
    rec = engine.add_record(curriculum_id="cur-2", solver_score=0.75, current_difficulty=0.3)
    result = engine.process(rec.id)
    assert hasattr(result, "curriculum_id")
    assert result.curriculum_id == "cur-2"  # type: ignore[union-attr]


def test_process_not_found(engine: AutomatedCurriculumProgressionEngine) -> None:
    result = engine.process("nonexistent")
    assert result["status"] == "not_found"


def test_generate_report(engine: AutomatedCurriculumProgressionEngine) -> None:
    engine.add_record(curriculum_id="c1", stage=CurriculumStage.ADVANCED, solver_score=0.9)
    engine.add_record(curriculum_id="c2", stage=CurriculumStage.MASTERY, solver_score=0.95)
    report = engine.generate_report()
    assert report.total_records == 2
    assert "advanced" in report.by_stage or "mastery" in report.by_stage


def test_get_stats(engine: AutomatedCurriculumProgressionEngine) -> None:
    engine.add_record(curriculum_id="c3", stage=CurriculumStage.INTERMEDIATE)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "stage_distribution" in stats


def test_clear_data(engine: AutomatedCurriculumProgressionEngine) -> None:
    engine.add_record(curriculum_id="c4")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine._records == []


def test_evaluate_progression_readiness(engine: AutomatedCurriculumProgressionEngine) -> None:
    for i in range(6):
        engine.add_record(
            curriculum_id="ready-cur",
            stage=CurriculumStage.FOUNDATION,
            solver_score=0.9,
            iteration=i,
        )
    result = engine.evaluate_progression_readiness("ready-cur", score_threshold=0.8)
    assert result["ready"] is True
    assert result["next_stage"] == CurriculumStage.INTERMEDIATE.value


def test_compute_optimal_difficulty_schedule(
    engine: AutomatedCurriculumProgressionEngine,
) -> None:
    schedule = engine.compute_optimal_difficulty_schedule(total_iterations=40)
    assert len(schedule) > 0
    assert schedule[0]["iteration"] == 0
    assert "difficulty" in schedule[0]
    assert "stage" in schedule[0]


def test_track_curriculum_coverage(engine: AutomatedCurriculumProgressionEngine) -> None:
    for stage in CurriculumStage:
        engine.add_record(curriculum_id="full-cur", stage=stage, solver_score=0.8)
    result = engine.track_curriculum_coverage()
    assert result["total_curricula"] >= 1
    full = next((c for c in result["coverage_details"] if c["curriculum_id"] == "full-cur"), None)
    assert full is not None
    assert full["complete"] is True
