"""Tests for CurriculumDifficultyCalibratorEngine."""

from __future__ import annotations

import pytest

from shieldops.security.curriculum_difficulty_calibrator_engine import (
    AdjustmentMagnitude,
    CalibrationMode,
    CurriculumDifficultyCalibratorEngine,
    DifficultySignal,
)


@pytest.fixture()
def engine() -> CurriculumDifficultyCalibratorEngine:
    return CurriculumDifficultyCalibratorEngine(max_records=100)


def test_add_record(engine: CurriculumDifficultyCalibratorEngine) -> None:
    rec = engine.add_record(
        task_id="task-1",
        agent_id="agent-1",
        calibration_mode=CalibrationMode.AUTOMATIC,
        difficulty_signal=DifficultySignal.SUCCESS_RATE,
        adjustment_magnitude=AdjustmentMagnitude.SMALL,
        current_difficulty=0.5,
        target_difficulty=0.6,
        success_rate=0.7,
    )
    assert rec.task_id == "task-1"
    assert rec.current_difficulty == 0.5
    assert len(engine._records) == 1


def test_process(engine: CurriculumDifficultyCalibratorEngine) -> None:
    rec = engine.add_record(
        task_id="t1",
        current_difficulty=0.5,
        target_difficulty=0.6,
        success_rate=0.9,  # high -> should increase difficulty
    )
    result = engine.process(rec.id)
    assert hasattr(result, "recommended_difficulty")
    assert result.recommended_difficulty > 0.5  # type: ignore[union-attr]


def test_process_not_found(engine: CurriculumDifficultyCalibratorEngine) -> None:
    result = engine.process("bad-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: CurriculumDifficultyCalibratorEngine) -> None:
    engine.add_record(
        calibration_mode=CalibrationMode.MANUAL,
        current_difficulty=0.3,
        target_difficulty=0.8,
        success_rate=0.5,
    )
    engine.add_record(
        calibration_mode=CalibrationMode.SCHEDULED,
        current_difficulty=0.7,
        target_difficulty=0.7,
        success_rate=0.6,
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert "manual" in report.by_calibration_mode


def test_get_stats(engine: CurriculumDifficultyCalibratorEngine) -> None:
    engine.add_record(calibration_mode=CalibrationMode.SEMI_AUTOMATIC)
    stats = engine.get_stats()
    assert "calibration_mode_distribution" in stats
    assert stats["total_records"] == 1


def test_clear_data(engine: CurriculumDifficultyCalibratorEngine) -> None:
    engine.add_record(task_id="t1")
    engine.clear_data()
    assert len(engine._records) == 0
    assert len(engine._analyses) == 0


def test_calibrate_current_difficulty(
    engine: CurriculumDifficultyCalibratorEngine,
) -> None:
    engine.add_record(agent_id="a1", success_rate=0.9, current_difficulty=0.5)
    engine.add_record(agent_id="a2", success_rate=0.2, current_difficulty=0.8)
    result = engine.calibrate_current_difficulty()
    assert isinstance(result, list)
    a1_entry = next(r for r in result if r["agent_id"] == "a1")
    assert a1_entry["recommended_action"] == "increase_difficulty"
    a2_entry = next(r for r in result if r["agent_id"] == "a2")
    assert a2_entry["recommended_action"] == "decrease_difficulty"


def test_predict_optimal_difficulty(
    engine: CurriculumDifficultyCalibratorEngine,
) -> None:
    engine.add_record(current_difficulty=0.5, target_difficulty=0.5, success_rate=0.5)
    engine.add_record(current_difficulty=0.6, target_difficulty=0.6, success_rate=0.5)
    result = engine.predict_optimal_difficulty()
    assert "predicted_optimal" in result
    assert "confidence" in result
    assert 0.0 <= result["predicted_optimal"] <= 1.0


def test_evaluate_calibration_accuracy(
    engine: CurriculumDifficultyCalibratorEngine,
) -> None:
    engine.add_record(current_difficulty=0.5, target_difficulty=0.5)
    engine.add_record(current_difficulty=0.8, target_difficulty=0.5)
    result = engine.evaluate_calibration_accuracy()
    assert "mean_error" in result
    assert "well_calibrated_pct" in result
    assert result["mean_error"] > 0.0


def test_max_records_eviction(engine: CurriculumDifficultyCalibratorEngine) -> None:
    for i in range(110):
        engine.add_record(task_id=f"t-{i}")
    assert len(engine._records) == 100
