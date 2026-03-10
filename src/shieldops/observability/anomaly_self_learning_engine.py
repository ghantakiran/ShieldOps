"""Anomaly Self-Learning Engine

Adaptive anomaly detection that incorporates operator
feedback to reduce false positives and improve accuracy.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FeedbackType(StrEnum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    TRUE_NEGATIVE = "true_negative"
    FALSE_NEGATIVE = "false_negative"
    UNLABELED = "unlabeled"


class ModelState(StrEnum):
    TRAINING = "training"
    ACTIVE = "active"
    DEGRADED = "degraded"
    RETRAINING = "retraining"
    RETIRED = "retired"


class SensitivityLevel(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


# --- Models ---


class AnomalyLearningRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    service: str = ""
    predicted_anomaly: bool = False
    actual_anomaly: bool = False
    feedback_type: FeedbackType = FeedbackType.UNLABELED
    model_version: str = ""
    confidence_score: float = 0.0
    sensitivity_level: SensitivityLevel = SensitivityLevel.MEDIUM
    created_at: float = Field(default_factory=time.time)


class AnomalyLearningAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_version: str = ""
    accuracy_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AnomalyLearningReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    overall_accuracy: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    by_feedback: dict[str, int] = Field(default_factory=dict)
    by_sensitivity: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AnomalySelfLearningEngine:
    """Anomaly Self-Learning Engine

    Adaptive anomaly detection that incorporates
    feedback to reduce false positives over time.
    """

    def __init__(
        self,
        max_records: int = 200000,
        accuracy_threshold: float = 0.85,
    ) -> None:
        self._max_records = max_records
        self._accuracy_threshold = accuracy_threshold
        self._records: list[AnomalyLearningRecord] = []
        self._analyses: list[AnomalyLearningAnalysis] = []
        logger.info(
            "anomaly_self_learning_engine.initialized",
            max_records=max_records,
            accuracy_threshold=accuracy_threshold,
        )

    def add_record(
        self,
        metric_name: str,
        service: str,
        predicted_anomaly: bool = False,
        actual_anomaly: bool = False,
        feedback_type: FeedbackType = (FeedbackType.UNLABELED),
        model_version: str = "",
        confidence_score: float = 0.0,
        sensitivity_level: SensitivityLevel = (SensitivityLevel.MEDIUM),
    ) -> AnomalyLearningRecord:
        record = AnomalyLearningRecord(
            metric_name=metric_name,
            service=service,
            predicted_anomaly=predicted_anomaly,
            actual_anomaly=actual_anomaly,
            feedback_type=feedback_type,
            model_version=model_version,
            confidence_score=confidence_score,
            sensitivity_level=sensitivity_level,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "anomaly_self_learning_engine.record_added",
            record_id=record.id,
            metric_name=metric_name,
            service=service,
        )
        return record

    def compute_model_accuracy(self, model_version: str = "") -> dict[str, Any]:
        matching = [r for r in self._records if r.feedback_type != FeedbackType.UNLABELED]
        if model_version:
            matching = [r for r in matching if r.model_version == model_version]
        if not matching:
            return {
                "model_version": model_version or "all",
                "status": "no_labeled_data",
            }
        correct = sum(
            1
            for r in matching
            if r.feedback_type
            in (
                FeedbackType.TRUE_POSITIVE,
                FeedbackType.TRUE_NEGATIVE,
            )
        )
        accuracy = round(correct / len(matching), 4)
        fp = sum(1 for r in matching if r.feedback_type == FeedbackType.FALSE_POSITIVE)
        fn = sum(1 for r in matching if r.feedback_type == FeedbackType.FALSE_NEGATIVE)
        return {
            "model_version": model_version or "all",
            "accuracy": accuracy,
            "false_positive_count": fp,
            "false_negative_count": fn,
            "labeled_samples": len(matching),
        }

    def adjust_sensitivity(self, service: str) -> dict[str, Any]:
        matching = [
            r
            for r in self._records
            if r.service == service and r.feedback_type != FeedbackType.UNLABELED
        ]
        if not matching:
            return {
                "service": service,
                "status": "no_data",
            }
        fp = sum(1 for r in matching if r.feedback_type == FeedbackType.FALSE_POSITIVE)
        fn = sum(1 for r in matching if r.feedback_type == FeedbackType.FALSE_NEGATIVE)
        fp_rate = round(fp / len(matching), 4)
        fn_rate = round(fn / len(matching), 4)
        recommendation = "maintain"
        if fp_rate > 0.3:
            recommendation = "decrease_sensitivity"
        elif fn_rate > 0.2:
            recommendation = "increase_sensitivity"
        return {
            "service": service,
            "fp_rate": fp_rate,
            "fn_rate": fn_rate,
            "recommendation": recommendation,
        }

    def identify_drift(self, model_version: str) -> dict[str, Any]:
        matching = [
            r
            for r in self._records
            if r.model_version == model_version and r.feedback_type != FeedbackType.UNLABELED
        ]
        if len(matching) < 10:
            return {
                "model_version": model_version,
                "status": "insufficient_data",
            }
        mid = len(matching) // 2
        first_half = matching[:mid]
        second_half = matching[mid:]

        def acc(recs: list[AnomalyLearningRecord]) -> float:
            c = sum(
                1
                for r in recs
                if r.feedback_type
                in (
                    FeedbackType.TRUE_POSITIVE,
                    FeedbackType.TRUE_NEGATIVE,
                )
            )
            return round(c / len(recs), 4) if recs else 0

        early = acc(first_half)
        recent = acc(second_half)
        drift = round(early - recent, 4)
        drifting = drift > 0.1
        return {
            "model_version": model_version,
            "early_accuracy": early,
            "recent_accuracy": recent,
            "drift_magnitude": drift,
            "drifting": drifting,
        }

    def process(self, model_version: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.model_version == model_version]
        if not matching:
            return {
                "model_version": model_version,
                "status": "no_data",
            }
        labeled = [r for r in matching if r.feedback_type != FeedbackType.UNLABELED]
        correct = sum(
            1
            for r in labeled
            if r.feedback_type
            in (
                FeedbackType.TRUE_POSITIVE,
                FeedbackType.TRUE_NEGATIVE,
            )
        )
        accuracy = round(correct / len(labeled), 4) if labeled else 0.0
        state = "active"
        if accuracy < self._accuracy_threshold:
            state = "degraded"
        return {
            "model_version": model_version,
            "total_predictions": len(matching),
            "labeled_count": len(labeled),
            "accuracy": accuracy,
            "state": state,
        }

    def generate_report(self) -> AnomalyLearningReport:
        by_fb: dict[str, int] = {}
        by_sens: dict[str, int] = {}
        for r in self._records:
            fv = r.feedback_type.value
            by_fb[fv] = by_fb.get(fv, 0) + 1
            sv = r.sensitivity_level.value
            by_sens[sv] = by_sens.get(sv, 0) + 1
        labeled = [r for r in self._records if r.feedback_type != FeedbackType.UNLABELED]
        correct = sum(
            1
            for r in labeled
            if r.feedback_type
            in (
                FeedbackType.TRUE_POSITIVE,
                FeedbackType.TRUE_NEGATIVE,
            )
        )
        accuracy = round(correct / len(labeled), 4) if labeled else 0.0
        fp = by_fb.get("false_positive", 0)
        fn = by_fb.get("false_negative", 0)
        total_labeled = len(labeled) if labeled else 1
        fp_rate = round(fp / total_labeled, 4)
        fn_rate = round(fn / total_labeled, 4)
        recs: list[str] = []
        if fp_rate > 0.2:
            recs.append(f"FP rate {fp_rate:.0%} — reduce sensitivity or retrain")
        if fn_rate > 0.1:
            recs.append(f"FN rate {fn_rate:.0%} — increase sensitivity")
        if accuracy < self._accuracy_threshold:
            recs.append(
                f"Accuracy {accuracy:.0%} below {self._accuracy_threshold:.0%} — retrain models"
            )
        if not recs:
            recs.append("Anomaly detection accuracy is nominal")
        return AnomalyLearningReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            overall_accuracy=accuracy,
            false_positive_rate=fp_rate,
            false_negative_rate=fn_rate,
            by_feedback=by_fb,
            by_sensitivity=by_sens,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        fb_dist: dict[str, int] = {}
        for r in self._records:
            k = r.feedback_type.value
            fb_dist[k] = fb_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "accuracy_threshold": (self._accuracy_threshold),
            "feedback_distribution": fb_dist,
            "unique_metrics": len({r.metric_name for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("anomaly_self_learning_engine.cleared")
        return {"status": "cleared"}
