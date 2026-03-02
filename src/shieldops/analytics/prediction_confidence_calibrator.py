"""Prediction Confidence Calibrator — calibrate ML model prediction confidence."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CalibrationMethod(StrEnum):
    PLATT_SCALING = "platt_scaling"
    ISOTONIC = "isotonic"
    TEMPERATURE = "temperature"
    BETA = "beta"
    HISTOGRAM = "histogram"


class ConfidenceBand(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class CalibrationStatus(StrEnum):
    CALIBRATED = "calibrated"
    NEEDS_CALIBRATION = "needs_calibration"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"
    SKIPPED = "skipped"


# --- Models ---


class CalibrationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    calibration_method: CalibrationMethod = CalibrationMethod.PLATT_SCALING
    confidence_band: ConfidenceBand = ConfidenceBand.MEDIUM
    calibration_status: CalibrationStatus = CalibrationStatus.NEEDS_CALIBRATION
    calibration_error: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CalibrationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    calibration_method: CalibrationMethod = CalibrationMethod.PLATT_SCALING
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CalibrationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    uncalibrated_count: int = 0
    avg_calibration_error: float = 0.0
    by_method: dict[str, int] = Field(default_factory=dict)
    by_band: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_uncalibrated: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PredictionConfidenceCalibrator:
    """Calibrate and monitor ML model prediction confidence."""

    def __init__(
        self,
        max_records: int = 200000,
        calibration_error_threshold: float = 0.05,
    ) -> None:
        self._max_records = max_records
        self._calibration_error_threshold = calibration_error_threshold
        self._records: list[CalibrationRecord] = []
        self._analyses: list[CalibrationAnalysis] = []
        logger.info(
            "prediction_confidence_calibrator.initialized",
            max_records=max_records,
            calibration_error_threshold=calibration_error_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_calibration(
        self,
        model_id: str,
        calibration_method: CalibrationMethod = CalibrationMethod.PLATT_SCALING,
        confidence_band: ConfidenceBand = ConfidenceBand.MEDIUM,
        calibration_status: CalibrationStatus = CalibrationStatus.NEEDS_CALIBRATION,
        calibration_error: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CalibrationRecord:
        record = CalibrationRecord(
            model_id=model_id,
            calibration_method=calibration_method,
            confidence_band=confidence_band,
            calibration_status=calibration_status,
            calibration_error=calibration_error,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "prediction_confidence_calibrator.calibration_recorded",
            record_id=record.id,
            model_id=model_id,
            calibration_method=calibration_method.value,
        )
        return record

    def get_calibration(self, record_id: str) -> CalibrationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_calibrations(
        self,
        calibration_method: CalibrationMethod | None = None,
        calibration_status: CalibrationStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CalibrationRecord]:
        results = list(self._records)
        if calibration_method is not None:
            results = [r for r in results if r.calibration_method == calibration_method]
        if calibration_status is not None:
            results = [r for r in results if r.calibration_status == calibration_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        model_id: str,
        calibration_method: CalibrationMethod = CalibrationMethod.PLATT_SCALING,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CalibrationAnalysis:
        analysis = CalibrationAnalysis(
            model_id=model_id,
            calibration_method=calibration_method,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "prediction_confidence_calibrator.analysis_added",
            model_id=model_id,
            calibration_method=calibration_method.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by calibration_method; return count and avg calibration_error."""
        method_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.calibration_method.value
            method_data.setdefault(key, []).append(r.calibration_error)
        result: dict[str, Any] = {}
        for method, errors in method_data.items():
            result[method] = {
                "count": len(errors),
                "avg_calibration_error": round(sum(errors) / len(errors), 4),
            }
        return result

    def identify_severe_drifts(self) -> list[dict[str, Any]]:
        """Return records where calibration_error > calibration_error_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.calibration_error > self._calibration_error_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "model_id": r.model_id,
                        "calibration_method": r.calibration_method.value,
                        "calibration_error": r.calibration_error,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["calibration_error"], reverse=True)

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by model_id, avg calibration_error, sort descending."""
        model_errors: dict[str, list[float]] = {}
        for r in self._records:
            model_errors.setdefault(r.model_id, []).append(r.calibration_error)
        results: list[dict[str, Any]] = []
        for model_id, errors in model_errors.items():
            results.append(
                {
                    "model_id": model_id,
                    "avg_calibration_error": round(sum(errors) / len(errors), 4),
                }
            )
        results.sort(key=lambda x: x["avg_calibration_error"], reverse=True)
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> CalibrationReport:
        by_method: dict[str, int] = {}
        by_band: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_method[r.calibration_method.value] = by_method.get(r.calibration_method.value, 0) + 1
            by_band[r.confidence_band.value] = by_band.get(r.confidence_band.value, 0) + 1
            by_status[r.calibration_status.value] = by_status.get(r.calibration_status.value, 0) + 1
        uncalibrated_count = sum(
            1 for r in self._records if r.calibration_error > self._calibration_error_threshold
        )
        errors = [r.calibration_error for r in self._records]
        avg_calibration_error = round(sum(errors) / len(errors), 4) if errors else 0.0
        uncalibrated_list = self.identify_severe_drifts()
        top_uncalibrated = [o["model_id"] for o in uncalibrated_list[:5]]
        recs: list[str] = []
        if self._records and uncalibrated_count > 0:
            recs.append(
                f"{uncalibrated_count} model(s) exceeding calibration error threshold "
                f"({self._calibration_error_threshold})"
            )
        if self._records and avg_calibration_error > self._calibration_error_threshold:
            recs.append(
                f"Avg calibration error {avg_calibration_error} exceeds threshold "
                f"({self._calibration_error_threshold})"
            )
        if not recs:
            recs.append("Model calibration is within acceptable bounds")
        return CalibrationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            uncalibrated_count=uncalibrated_count,
            avg_calibration_error=avg_calibration_error,
            by_method=by_method,
            by_band=by_band,
            by_status=by_status,
            top_uncalibrated=top_uncalibrated,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("prediction_confidence_calibrator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            key = r.calibration_method.value
            method_dist[key] = method_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "calibration_error_threshold": self._calibration_error_threshold,
            "method_distribution": method_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_models": len({r.model_id for r in self._records}),
        }
