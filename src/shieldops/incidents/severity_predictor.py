"""Incident Severity Predictor — predicts incident severity from initial signals before triage."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PredictedSeverity(StrEnum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"
    SEV5 = "sev5"


class SignalType(StrEnum):
    ALERT = "alert"
    ERROR_SPIKE = "error_spike"
    LATENCY = "latency"
    AVAILABILITY = "availability"
    SECURITY = "security"
    CAPACITY = "capacity"


class PredictionOutcome(StrEnum):
    PENDING = "pending"
    CORRECT = "correct"
    OVER_ESTIMATED = "over_estimated"
    UNDER_ESTIMATED = "under_estimated"


# --- Models ---


class IncidentSignal(BaseModel):
    signal_type: SignalType
    value: float = 0.0
    service: str = ""
    description: str = ""


class ServiceProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str
    criticality: int = 3
    historical_incidents: int = 0
    avg_severity: float = 3.0
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class SeverityPrediction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    predicted_severity: PredictedSeverity
    confidence: float = 0.0
    signals: list[IncidentSignal] = Field(default_factory=list)
    actual_severity: PredictedSeverity | None = None
    outcome: PredictionOutcome = PredictionOutcome.PENDING
    predicted_at: float = Field(default_factory=time.time)


# --- Predictor ---


class IncidentSeverityPredictor:
    """Predicts incident severity from initial signals before triage."""

    def __init__(
        self,
        max_predictions: int = 50000,
        max_profiles: int = 1000,
    ) -> None:
        self._max_predictions = max_predictions
        self._max_profiles = max_profiles
        self._predictions: dict[str, SeverityPrediction] = {}
        self._profiles: dict[str, ServiceProfile] = {}
        logger.info(
            "severity_predictor.initialized",
            max_predictions=max_predictions,
            max_profiles=max_profiles,
        )

    def register_service(
        self,
        service_name: str,
        criticality: int = 3,
        **kw: Any,
    ) -> ServiceProfile:
        """Register a service profile for severity prediction."""
        profile = ServiceProfile(
            service_name=service_name,
            criticality=criticality,
            **kw,
        )
        self._profiles[profile.id] = profile
        if len(self._profiles) > self._max_profiles:
            oldest = next(iter(self._profiles))
            del self._profiles[oldest]
        logger.info(
            "severity_predictor.service_registered",
            profile_id=profile.id,
            service_name=service_name,
            criticality=criticality,
        )
        return profile

    def predict(
        self,
        service: str,
        signals: list[dict[str, Any]],
    ) -> SeverityPrediction:
        """Predict incident severity from signals."""
        parsed_signals = [IncidentSignal(**s) for s in signals]
        score = self._calculate_severity_score(service, parsed_signals)
        if score >= 90:
            severity = PredictedSeverity.SEV1
        elif score >= 70:
            severity = PredictedSeverity.SEV2
        elif score >= 50:
            severity = PredictedSeverity.SEV3
        elif score >= 30:
            severity = PredictedSeverity.SEV4
        else:
            severity = PredictedSeverity.SEV5
        confidence = min(0.95, 0.5 + len(parsed_signals) * 0.1)
        prediction = SeverityPrediction(
            service=service,
            predicted_severity=severity,
            confidence=round(confidence, 4),
            signals=parsed_signals,
        )
        self._predictions[prediction.id] = prediction
        if len(self._predictions) > self._max_predictions:
            oldest = next(iter(self._predictions))
            del self._predictions[oldest]
        logger.info(
            "severity_predictor.prediction_made",
            prediction_id=prediction.id,
            service=service,
            severity=severity,
            confidence=prediction.confidence,
        )
        return prediction

    def _calculate_severity_score(
        self,
        service: str,
        signals: list[IncidentSignal],
    ) -> float:
        """Calculate a severity score from signals and service profile."""
        base_score = 0.0
        signal_weights = {
            SignalType.AVAILABILITY: 25.0,
            SignalType.SECURITY: 22.0,
            SignalType.ERROR_SPIKE: 18.0,
            SignalType.LATENCY: 15.0,
            SignalType.CAPACITY: 12.0,
            SignalType.ALERT: 10.0,
        }
        for signal in signals:
            base_score += signal_weights.get(signal.signal_type, 10.0)
        # Adjust for service criticality
        profile = self._find_profile(service)
        if profile is not None:
            criticality_multiplier = (6 - profile.criticality) / 5.0
            base_score *= 0.5 + criticality_multiplier * 0.5
        return min(100.0, base_score)

    def _find_profile(self, service_name: str) -> ServiceProfile | None:
        """Find a service profile by name."""
        for p in self._profiles.values():
            if p.service_name == service_name:
                return p
        return None

    def record_actual(
        self,
        prediction_id: str,
        actual_severity: PredictedSeverity,
    ) -> SeverityPrediction | None:
        """Record the actual severity to evaluate prediction accuracy."""
        prediction = self._predictions.get(prediction_id)
        if prediction is None:
            return None
        prediction.actual_severity = actual_severity
        sev_order = list(PredictedSeverity)
        pred_idx = sev_order.index(prediction.predicted_severity)
        actual_idx = sev_order.index(actual_severity)
        if pred_idx == actual_idx:
            prediction.outcome = PredictionOutcome.CORRECT
        elif pred_idx < actual_idx:
            prediction.outcome = PredictionOutcome.OVER_ESTIMATED
        else:
            prediction.outcome = PredictionOutcome.UNDER_ESTIMATED
        logger.info(
            "severity_predictor.actual_recorded",
            prediction_id=prediction_id,
            actual_severity=actual_severity,
            outcome=prediction.outcome,
        )
        return prediction

    def get_prediction(self, prediction_id: str) -> SeverityPrediction | None:
        """Retrieve a prediction by ID."""
        return self._predictions.get(prediction_id)

    def list_predictions(
        self,
        service: str | None = None,
        outcome: PredictionOutcome | None = None,
    ) -> list[SeverityPrediction]:
        """List predictions with optional filters."""
        results = list(self._predictions.values())
        if service is not None:
            results = [p for p in results if p.service == service]
        if outcome is not None:
            results = [p for p in results if p.outcome == outcome]
        return results

    def get_accuracy(self) -> dict[str, Any]:
        """Get prediction accuracy metrics."""
        evaluated = [
            p for p in self._predictions.values() if p.outcome != PredictionOutcome.PENDING
        ]
        total = len(evaluated)
        if total == 0:
            return {
                "total_evaluated": 0,
                "accuracy": 0.0,
                "over_estimated": 0,
                "under_estimated": 0,
            }
        correct = sum(1 for p in evaluated if p.outcome == PredictionOutcome.CORRECT)
        over = sum(1 for p in evaluated if p.outcome == PredictionOutcome.OVER_ESTIMATED)
        under = sum(1 for p in evaluated if p.outcome == PredictionOutcome.UNDER_ESTIMATED)
        return {
            "total_evaluated": total,
            "correct": correct,
            "over_estimated": over,
            "under_estimated": under,
            "accuracy": round(correct / total, 4),
        }

    def get_service_profile(self, profile_id: str) -> ServiceProfile | None:
        """Retrieve a service profile by ID."""
        return self._profiles.get(profile_id)

    def list_profiles(self) -> list[ServiceProfile]:
        """List all service profiles."""
        return list(self._profiles.values())

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        severity_counts: dict[str, int] = {}
        outcome_counts: dict[str, int] = {}
        for p in self._predictions.values():
            severity_counts[p.predicted_severity] = severity_counts.get(p.predicted_severity, 0) + 1
            outcome_counts[p.outcome] = outcome_counts.get(p.outcome, 0) + 1
        accuracy = self.get_accuracy()
        return {
            "total_predictions": len(self._predictions),
            "total_profiles": len(self._profiles),
            "severity_distribution": severity_counts,
            "outcome_distribution": outcome_counts,
            "accuracy": accuracy.get("accuracy", 0.0),
        }
