"""Agent Confidence Calibration Engine —
evaluate calibration quality, detect confidence drift,
and optimize calibration parameters for agents."""

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
    PLATT = "platt"
    ISOTONIC = "isotonic"
    TEMPERATURE = "temperature"
    HISTOGRAM = "histogram"


class ConfidenceBand(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CalibrationQuality(StrEnum):
    WELL_CALIBRATED = "well_calibrated"
    OVERCONFIDENT = "overconfident"
    UNDERCONFIDENT = "underconfident"
    MISCALIBRATED = "miscalibrated"


# --- Models ---


class ConfidenceCalibrationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    calibration_method: CalibrationMethod = CalibrationMethod.TEMPERATURE
    confidence_band: ConfidenceBand = ConfidenceBand.HIGH
    calibration_quality: CalibrationQuality = CalibrationQuality.WELL_CALIBRATED
    predicted_confidence: float = 0.0
    actual_accuracy: float = 0.0
    calibration_error: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConfidenceCalibrationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    avg_calibration_error: float = 0.0
    dominant_method: CalibrationMethod = CalibrationMethod.TEMPERATURE
    dominant_quality: CalibrationQuality = CalibrationQuality.WELL_CALIBRATED
    avg_predicted_confidence: float = 0.0
    record_count: int = 0
    calibration_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConfidenceCalibrationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_calibration_error: float = 0.0
    by_calibration_method: dict[str, int] = Field(default_factory=dict)
    by_confidence_band: dict[str, int] = Field(default_factory=dict)
    by_calibration_quality: dict[str, int] = Field(default_factory=dict)
    top_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentConfidenceCalibrationEngine:
    """Calibrate agent confidence scores, detect confidence drift,
    and optimize calibration parameters for decision quality."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ConfidenceCalibrationRecord] = []
        self._analyses: dict[str, ConfidenceCalibrationAnalysis] = {}
        logger.info(
            "agent_confidence_calibration.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        calibration_method: CalibrationMethod = CalibrationMethod.TEMPERATURE,
        confidence_band: ConfidenceBand = ConfidenceBand.HIGH,
        calibration_quality: CalibrationQuality = CalibrationQuality.WELL_CALIBRATED,
        predicted_confidence: float = 0.0,
        actual_accuracy: float = 0.0,
        calibration_error: float = 0.0,
        description: str = "",
    ) -> ConfidenceCalibrationRecord:
        record = ConfidenceCalibrationRecord(
            agent_id=agent_id,
            calibration_method=calibration_method,
            confidence_band=confidence_band,
            calibration_quality=calibration_quality,
            predicted_confidence=predicted_confidence,
            actual_accuracy=actual_accuracy,
            calibration_error=calibration_error,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "confidence_calibration.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> ConfidenceCalibrationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        agent_recs = [r for r in self._records if r.agent_id == rec.agent_id]
        errors = [r.calibration_error for r in agent_recs]
        confidences = [r.predicted_confidence for r in agent_recs]
        avg_error = round(sum(errors) / len(errors), 4) if errors else 0.0
        avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
        method_counts: dict[str, int] = {}
        quality_counts: dict[str, int] = {}
        for r in agent_recs:
            method_counts[r.calibration_method.value] = (
                method_counts.get(r.calibration_method.value, 0) + 1
            )
            quality_counts[r.calibration_quality.value] = (
                quality_counts.get(r.calibration_quality.value, 0) + 1
            )
        dominant_method = (
            CalibrationMethod(max(method_counts, key=lambda x: method_counts[x]))
            if method_counts
            else CalibrationMethod.TEMPERATURE
        )
        dominant_quality = (
            CalibrationQuality(max(quality_counts, key=lambda x: quality_counts[x]))
            if quality_counts
            else CalibrationQuality.WELL_CALIBRATED
        )
        calibration_score = round(max(0.0, 100.0 - avg_error * 100), 2)
        analysis = ConfidenceCalibrationAnalysis(
            agent_id=rec.agent_id,
            avg_calibration_error=avg_error,
            dominant_method=dominant_method,
            dominant_quality=dominant_quality,
            avg_predicted_confidence=avg_conf,
            record_count=len(agent_recs),
            calibration_score=calibration_score,
            description=f"Agent {rec.agent_id} calibration score {calibration_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ConfidenceCalibrationReport:
        by_cm: dict[str, int] = {}
        by_cb: dict[str, int] = {}
        by_cq: dict[str, int] = {}
        errors: list[float] = []
        for r in self._records:
            by_cm[r.calibration_method.value] = by_cm.get(r.calibration_method.value, 0) + 1
            by_cb[r.confidence_band.value] = by_cb.get(r.confidence_band.value, 0) + 1
            by_cq[r.calibration_quality.value] = by_cq.get(r.calibration_quality.value, 0) + 1
            errors.append(r.calibration_error)
        avg = round(sum(errors) / len(errors), 4) if errors else 0.0
        agent_errors: dict[str, float] = {}
        for r in self._records:
            agent_errors[r.agent_id] = agent_errors.get(r.agent_id, 0.0) + (
                1.0 - r.calibration_error
            )
        ranked = sorted(
            agent_errors,
            key=lambda x: agent_errors[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        overconfident = by_cq.get("overconfident", 0)
        if overconfident > 0:
            recs.append(f"{overconfident} overconfident agents — apply temperature scaling")
        miscalibrated = by_cq.get("miscalibrated", 0)
        if miscalibrated > 0:
            recs.append(f"{miscalibrated} miscalibrated agents — run isotonic recalibration")
        if not recs:
            recs.append("Agent confidence calibration is well-tuned")
        return ConfidenceCalibrationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_calibration_error=avg,
            by_calibration_method=by_cm,
            by_confidence_band=by_cb,
            by_calibration_quality=by_cq,
            top_agents=ranked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            dist[r.calibration_method.value] = dist.get(r.calibration_method.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "calibration_method_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("agent_confidence_calibration.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def evaluate_calibration_quality(self) -> list[dict[str, Any]]:
        """Evaluate calibration quality distribution per agent."""
        agent_data: dict[str, list[ConfidenceCalibrationRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for aid, recs in agent_data.items():
            errors = [r.calibration_error for r in recs]
            predicted = [r.predicted_confidence for r in recs]
            actual = [r.actual_accuracy for r in recs]
            avg_error = round(sum(errors) / len(errors), 4) if errors else 0.0
            avg_pred = round(sum(predicted) / len(predicted), 4) if predicted else 0.0
            avg_actual = round(sum(actual) / len(actual), 4) if actual else 0.0
            quality_counts: dict[str, int] = {}
            for r in recs:
                quality_counts[r.calibration_quality.value] = (
                    quality_counts.get(r.calibration_quality.value, 0) + 1
                )
            calibration_score = round(max(0.0, 100.0 - avg_error * 100), 2)
            results.append(
                {
                    "agent_id": aid,
                    "avg_calibration_error": avg_error,
                    "avg_predicted_confidence": avg_pred,
                    "avg_actual_accuracy": avg_actual,
                    "calibration_score": calibration_score,
                    "quality_distribution": quality_counts,
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["calibration_score"], reverse=True)
        return results

    def detect_confidence_drift(self) -> list[dict[str, Any]]:
        """Detect agents whose confidence calibration is drifting."""
        agent_data: dict[str, list[ConfidenceCalibrationRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for aid, recs in agent_data.items():
            if len(recs) < 2:
                continue
            errors = [r.calibration_error for r in recs]
            confidences = [r.predicted_confidence for r in recs]
            error_trend = errors[-1] - errors[0] if len(errors) > 1 else 0.0
            conf_trend = confidences[-1] - confidences[0] if len(confidences) > 1 else 0.0
            is_drifting = abs(error_trend) > 0.05 or abs(conf_trend) > 0.1
            results.append(
                {
                    "agent_id": aid,
                    "error_trend": round(error_trend, 4),
                    "confidence_trend": round(conf_trend, 4),
                    "is_drifting": is_drifting,
                    "drift_direction": (
                        "worsening"
                        if error_trend > 0
                        else "improving"
                        if error_trend < 0
                        else "stable"
                    ),
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: abs(x["error_trend"]), reverse=True)
        return results

    def optimize_calibration_parameters(self) -> list[dict[str, Any]]:
        """Recommend calibration method and parameters per agent."""
        method_data: dict[str, list[float]] = {}
        for r in self._records:
            method_data.setdefault(r.calibration_method.value, []).append(r.calibration_error)
        results: list[dict[str, Any]] = []
        method_params: dict[str, dict[str, Any]] = {
            "platt": {"alpha": 1.0, "beta": 0.0},
            "isotonic": {"out_of_bounds": "clip"},
            "temperature": {"temperature": 1.0},
            "histogram": {"bins": 10},
        }
        for method, errors in method_data.items():
            avg_err = round(sum(errors) / len(errors), 4) if errors else 0.0
            params = method_params.get(method, {})
            adjusted_params = dict(params)
            if method == "temperature" and avg_err > 0.1:
                adjusted_params["temperature"] = round(1.0 + avg_err * 2, 2)
            results.append(
                {
                    "calibration_method": method,
                    "avg_error": avg_err,
                    "current_params": params,
                    "recommended_params": adjusted_params,
                    "needs_tuning": avg_err > 0.1,
                    "sample_count": len(errors),
                }
            )
        results.sort(key=lambda x: x["avg_error"])
        return results
