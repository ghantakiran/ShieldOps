"""Curriculum Difficulty Calibrator Engine —
calibrates security training task difficulty,
predicts optimal difficulty, evaluates calibration accuracy."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CalibrationMode(StrEnum):
    AUTOMATIC = "automatic"
    SEMI_AUTOMATIC = "semi_automatic"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class DifficultySignal(StrEnum):
    SUCCESS_RATE = "success_rate"
    REWARD_MEAN = "reward_mean"
    SOLVE_TIME = "solve_time"
    ERROR_PATTERN = "error_pattern"


class AdjustmentMagnitude(StrEnum):
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# --- Models ---


class CalibrationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    agent_id: str = ""
    calibration_mode: CalibrationMode = CalibrationMode.AUTOMATIC
    difficulty_signal: DifficultySignal = DifficultySignal.SUCCESS_RATE
    adjustment_magnitude: AdjustmentMagnitude = AdjustmentMagnitude.SMALL
    current_difficulty: float = 0.5
    target_difficulty: float = 0.5
    success_rate: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CalibrationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    agent_id: str = ""
    calibration_mode: CalibrationMode = CalibrationMode.AUTOMATIC
    difficulty_signal: DifficultySignal = DifficultySignal.SUCCESS_RATE
    recommended_difficulty: float = 0.5
    calibration_error: float = 0.0
    is_well_calibrated: bool = True
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CalibrationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_current_difficulty: float = 0.0
    avg_calibration_error: float = 0.0
    by_calibration_mode: dict[str, int] = Field(default_factory=dict)
    by_difficulty_signal: dict[str, int] = Field(default_factory=dict)
    by_adjustment_magnitude: dict[str, int] = Field(default_factory=dict)
    miscalibrated_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CurriculumDifficultyCalibratorEngine:
    """Calibrates security training task difficulty."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CalibrationRecord] = []
        self._analyses: dict[str, CalibrationAnalysis] = {}
        logger.info(
            "curriculum_difficulty_calibrator_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        task_id: str = "",
        agent_id: str = "",
        calibration_mode: CalibrationMode = CalibrationMode.AUTOMATIC,
        difficulty_signal: DifficultySignal = DifficultySignal.SUCCESS_RATE,
        adjustment_magnitude: AdjustmentMagnitude = AdjustmentMagnitude.SMALL,
        current_difficulty: float = 0.5,
        target_difficulty: float = 0.5,
        success_rate: float = 0.0,
        description: str = "",
    ) -> CalibrationRecord:
        record = CalibrationRecord(
            task_id=task_id,
            agent_id=agent_id,
            calibration_mode=calibration_mode,
            difficulty_signal=difficulty_signal,
            adjustment_magnitude=adjustment_magnitude,
            current_difficulty=current_difficulty,
            target_difficulty=target_difficulty,
            success_rate=success_rate,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "curriculum_difficulty_calibrator.record_added",
            record_id=record.id,
            task_id=task_id,
        )
        return record

    def process(self, key: str) -> CalibrationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        if rec.success_rate > 0.8:
            recommended = min(1.0, rec.current_difficulty + 0.1)
        elif rec.success_rate < 0.3:
            recommended = max(0.0, rec.current_difficulty - 0.1)
        else:
            recommended = rec.current_difficulty
        calibration_error = round(abs(recommended - rec.target_difficulty), 4)
        analysis = CalibrationAnalysis(
            task_id=rec.task_id,
            agent_id=rec.agent_id,
            calibration_mode=rec.calibration_mode,
            difficulty_signal=rec.difficulty_signal,
            recommended_difficulty=round(recommended, 4),
            calibration_error=calibration_error,
            is_well_calibrated=calibration_error < 0.1,
            description=(
                f"Task {rec.task_id} recommended difficulty "
                f"{recommended:.4f}, error {calibration_error:.4f}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CalibrationReport:
        by_cm: dict[str, int] = {}
        by_ds: dict[str, int] = {}
        by_am: dict[str, int] = {}
        difficulties: list[float] = []
        for r in self._records:
            k = r.calibration_mode.value
            by_cm[k] = by_cm.get(k, 0) + 1
            k2 = r.difficulty_signal.value
            by_ds[k2] = by_ds.get(k2, 0) + 1
            k3 = r.adjustment_magnitude.value
            by_am[k3] = by_am.get(k3, 0) + 1
            difficulties.append(r.current_difficulty)
        avg_diff = round(sum(difficulties) / len(difficulties), 4) if difficulties else 0.0
        errors = [a.calibration_error for a in self._analyses.values()]
        avg_err = round(sum(errors) / len(errors), 4) if errors else 0.0
        miscalibrated = list(
            {a.agent_id for a in self._analyses.values() if not a.is_well_calibrated}
        )[:10]
        recs_list: list[str] = []
        if miscalibrated:
            recs_list.append(f"{len(miscalibrated)} agents with miscalibrated difficulty")
        if not recs_list:
            recs_list.append("Curriculum difficulty well-calibrated")
        return CalibrationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_current_difficulty=avg_diff,
            avg_calibration_error=avg_err,
            by_calibration_mode=by_cm,
            by_difficulty_signal=by_ds,
            by_adjustment_magnitude=by_am,
            miscalibrated_agents=miscalibrated,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        mode_dist: dict[str, int] = {}
        for r in self._records:
            k = r.calibration_mode.value
            mode_dist[k] = mode_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "calibration_mode_distribution": mode_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("curriculum_difficulty_calibrator_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def calibrate_current_difficulty(self) -> list[dict[str, Any]]:
        """Calibrate current difficulty per agent based on success rate."""
        agent_data: dict[str, list[CalibrationRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for agent_id, recs in agent_data.items():
            mean_success = sum(r.success_rate for r in recs) / len(recs)
            mean_difficulty = sum(r.current_difficulty for r in recs) / len(recs)
            if mean_success > 0.8:
                action = "increase_difficulty"
            elif mean_success < 0.3:
                action = "decrease_difficulty"
            else:
                action = "maintain"
            results.append(
                {
                    "agent_id": agent_id,
                    "mean_success_rate": round(mean_success, 4),
                    "mean_difficulty": round(mean_difficulty, 4),
                    "recommended_action": action,
                    "sample_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["mean_success_rate"], reverse=True)
        return results

    def predict_optimal_difficulty(self) -> dict[str, Any]:
        """Predict optimal difficulty levels for the next training batch."""
        if not self._records:
            return {"predicted_optimal": 0.5, "confidence": 0.0}
        success_rates = [r.success_rate for r in self._records]
        difficulties = [r.current_difficulty for r in self._records]
        mean_success = sum(success_rates) / len(success_rates)
        mean_diff = sum(difficulties) / len(difficulties)
        if mean_success > 0.8:
            predicted = min(1.0, mean_diff + 0.1)
        elif mean_success < 0.3:
            predicted = max(0.0, mean_diff - 0.1)
        else:
            predicted = mean_diff
        confidence = round(1.0 - abs(mean_success - 0.5), 4)
        return {
            "predicted_optimal": round(predicted, 4),
            "confidence": confidence,
            "mean_success_rate": round(mean_success, 4),
            "mean_difficulty": round(mean_diff, 4),
        }

    def evaluate_calibration_accuracy(self) -> dict[str, Any]:
        """Evaluate how accurately current difficulties match targets."""
        if not self._records:
            return {"mean_error": 0.0, "well_calibrated_pct": 0.0}
        errors = [abs(r.current_difficulty - r.target_difficulty) for r in self._records]
        mean_error = sum(errors) / len(errors)
        well_calibrated = sum(1 for e in errors if e < 0.1)
        well_calibrated_pct = round(well_calibrated / len(errors) * 100, 2)
        return {
            "mean_error": round(mean_error, 4),
            "max_error": round(max(errors), 4),
            "well_calibrated_pct": well_calibrated_pct,
            "total_records": len(self._records),
        }
