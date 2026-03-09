"""Predictive Alert Engine V2 — next-gen predictive alerting with ML models."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PredictionConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


class AlertSeverity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    LOW = "low"


class ModelStatus(StrEnum):
    TRAINED = "trained"
    TRAINING = "training"
    UNTRAINED = "untrained"
    STALE = "stale"
    FAILED = "failed"


# --- Models ---


class PredictionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    predicted_value: float = 0.0
    actual_value: float | None = None
    severity: AlertSeverity = AlertSeverity.INFO
    confidence: PredictionConfidence = PredictionConfidence.UNCERTAIN
    score: float = 0.0
    horizon_minutes: int = 30
    created_at: float = Field(default_factory=time.time)


class ModelInfo(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    status: ModelStatus = ModelStatus.UNTRAINED
    accuracy: float = 0.0
    samples_trained: int = 0
    last_trained_at: float = 0.0
    created_at: float = Field(default_factory=time.time)


class PredictiveAlertReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_predictions: int = 0
    total_models: int = 0
    avg_accuracy: float = 0.0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PredictiveAlertEngineV2:
    """Next-gen predictive alerting with ML models."""

    def __init__(
        self,
        max_predictions: int = 100000,
        default_horizon: int = 30,
    ) -> None:
        self._max_predictions = max_predictions
        self._default_horizon = default_horizon
        self._predictions: list[PredictionRecord] = []
        self._models: list[ModelInfo] = []
        logger.info(
            "predictive_alert_engine_v2.initialized",
            max_predictions=max_predictions,
            default_horizon=default_horizon,
        )

    def predict_alerts(
        self,
        metric_name: str,
        current_value: float,
        horizon_minutes: int | None = None,
    ) -> PredictionRecord:
        """Generate a predicted alert for a metric."""
        horizon = horizon_minutes or self._default_horizon
        predicted = current_value * 1.15
        if predicted > 90:
            severity = AlertSeverity.CRITICAL
            confidence = PredictionConfidence.HIGH
        elif predicted > 70:
            severity = AlertSeverity.WARNING
            confidence = PredictionConfidence.MEDIUM
        else:
            severity = AlertSeverity.INFO
            confidence = PredictionConfidence.LOW
        score = round(min(predicted / 100.0, 1.0), 4)
        record = PredictionRecord(
            metric_name=metric_name,
            predicted_value=round(predicted, 2),
            severity=severity,
            confidence=confidence,
            score=score,
            horizon_minutes=horizon,
        )
        self._predictions.append(record)
        if len(self._predictions) > self._max_predictions:
            self._predictions = self._predictions[-self._max_predictions :]
        logger.info(
            "predictive_alert_engine_v2.predicted",
            metric=metric_name,
            severity=severity.value,
        )
        return record

    def train_model(
        self,
        name: str,
        samples: int = 0,
    ) -> ModelInfo:
        """Train or update a prediction model."""
        accuracy = min(0.95, 0.5 + samples * 0.001) if samples > 0 else 0.0
        status = ModelStatus.TRAINED if samples > 10 else ModelStatus.UNTRAINED
        model = ModelInfo(
            name=name,
            status=status,
            accuracy=round(accuracy, 4),
            samples_trained=samples,
            last_trained_at=time.time() if status == ModelStatus.TRAINED else 0.0,
        )
        self._models.append(model)
        logger.info(
            "predictive_alert_engine_v2.model_trained",
            name=name,
            status=status.value,
            accuracy=model.accuracy,
        )
        return model

    def evaluate_predictions(self) -> dict[str, Any]:
        """Evaluate prediction accuracy against actuals."""
        evaluated = [p for p in self._predictions if p.actual_value is not None]
        if not evaluated:
            return {"evaluated": 0, "accuracy": 0.0}
        errors = [abs(p.predicted_value - (p.actual_value or 0.0)) for p in evaluated]
        avg_error = sum(errors) / len(errors) if errors else 0
        accuracy = max(0.0, 1.0 - avg_error / 100.0)
        return {
            "evaluated": len(evaluated),
            "avg_error": round(avg_error, 2),
            "accuracy": round(accuracy, 4),
        }

    def get_alert_forecast(
        self,
        hours_ahead: int = 24,
    ) -> list[dict[str, Any]]:
        """Forecast alerts for the next N hours."""
        forecast: list[dict[str, Any]] = []
        severity_counts: dict[str, int] = {}
        for p in self._predictions:
            key = p.severity.value
            severity_counts[key] = severity_counts.get(key, 0) + 1
        for sev, count in severity_counts.items():
            rate = count / max(1, len(self._predictions))
            projected = round(rate * hours_ahead * 2, 1)
            forecast.append(
                {
                    "severity": sev,
                    "projected_count": projected,
                    "rate_per_hour": round(rate, 4),
                }
            )
        forecast.sort(key=lambda x: x["projected_count"], reverse=True)
        return forecast

    def tune_sensitivity(
        self,
        metric_name: str,
        adjustment: float = 0.0,
    ) -> dict[str, Any]:
        """Tune prediction sensitivity for a metric."""
        affected = [p for p in self._predictions if p.metric_name == metric_name]
        for p in affected:
            p.score = round(max(0.0, min(1.0, p.score + adjustment)), 4)
        return {
            "metric": metric_name,
            "adjustment": adjustment,
            "affected_count": len(affected),
        }

    def generate_report(self) -> PredictiveAlertReport:
        """Generate predictive alerting report."""
        by_sev: dict[str, int] = {}
        by_conf: dict[str, int] = {}
        for p in self._predictions:
            by_sev[p.severity.value] = by_sev.get(p.severity.value, 0) + 1
            by_conf[p.confidence.value] = by_conf.get(p.confidence.value, 0) + 1
        accs = [m.accuracy for m in self._models if m.status == ModelStatus.TRAINED]
        avg_acc = round(sum(accs) / len(accs), 4) if accs else 0.0
        recs: list[str] = []
        if avg_acc < 0.7:
            recs.append("Model accuracy below 70% — retrain recommended")
        if not recs:
            recs.append("Predictive alerting performing within targets")
        return PredictiveAlertReport(
            total_predictions=len(self._predictions),
            total_models=len(self._models),
            avg_accuracy=avg_acc,
            by_severity=by_sev,
            by_confidence=by_conf,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all predictions and models."""
        self._predictions.clear()
        self._models.clear()
        logger.info("predictive_alert_engine_v2.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        return {
            "total_predictions": len(self._predictions),
            "total_models": len(self._models),
            "default_horizon": self._default_horizon,
            "unique_metrics": len({p.metric_name for p in self._predictions}),
        }
