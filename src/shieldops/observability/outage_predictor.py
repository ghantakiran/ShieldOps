"""Predictive Outage Detector.

Fuse multiple weak signals into composite outage probability score.
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


class OutageProbability(StrEnum):
    NEGLIGIBLE = "negligible"
    LOW = "low"
    ELEVATED = "elevated"
    HIGH = "high"
    IMMINENT = "imminent"


class SignalType(StrEnum):
    METRIC_DRIFT = "metric_drift"
    DEPENDENCY_DEGRADATION = "dependency_degradation"
    ERROR_BUDGET_BURN = "error_budget_burn"
    DEPLOY_RECENCY = "deploy_recency"
    ALERT_VELOCITY = "alert_velocity"


class MitigationAction(StrEnum):
    NO_ACTION = "no_action"
    INCREASE_MONITORING = "increase_monitoring"
    PRE_SCALE = "pre_scale"
    FREEZE_CHANGES = "freeze_changes"
    ACTIVATE_INCIDENT = "activate_incident"


# --- Models ---


class SignalReading(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    signal_type: SignalType = SignalType.METRIC_DRIFT
    value: float = 0.0
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class OutagePrediction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    composite_score: float = 0.0
    probability: OutageProbability = OutageProbability.NEGLIGIBLE
    signal_count: int = 0
    recommended_action: MitigationAction = MitigationAction.NO_ACTION
    lead_time_minutes: int = 0
    created_at: float = Field(default_factory=time.time)


class OutagePredictionReport(BaseModel):
    total_signals: int = 0
    total_predictions: int = 0
    by_probability: dict[str, int] = Field(default_factory=dict)
    by_signal_type: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    high_risk_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PredictiveOutageDetector:
    """Fuse multiple weak signals into composite outage probability score."""

    def __init__(
        self,
        max_records: int = 300000,
        composite_threshold: float = 0.75,
    ) -> None:
        self._max_records = max_records
        self._composite_threshold = composite_threshold
        self._signals: list[SignalReading] = []
        self._predictions: list[OutagePrediction] = []
        logger.info(
            "outage_predictor.initialized",
            max_records=max_records,
            composite_threshold=composite_threshold,
        )

    # -- signals -----------------------------------------------------

    def record_signal(
        self,
        service_name: str,
        signal_type: SignalType = SignalType.METRIC_DRIFT,
        value: float = 0.0,
        weight: float = 1.0,
        **kw: Any,
    ) -> SignalReading:
        signal = SignalReading(
            service_name=service_name,
            signal_type=signal_type,
            value=value,
            weight=weight,
            **kw,
        )
        self._signals.append(signal)
        if len(self._signals) > self._max_records:
            self._signals = self._signals[-self._max_records :]
        logger.info(
            "outage_predictor.signal_recorded",
            signal_id=signal.id,
            service_name=service_name,
        )
        return signal

    def get_signal(self, signal_id: str) -> SignalReading | None:
        for s in self._signals:
            if s.id == signal_id:
                return s
        return None

    def list_signals(
        self,
        service_name: str | None = None,
        signal_type: SignalType | None = None,
        limit: int = 50,
    ) -> list[SignalReading]:
        results = list(self._signals)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if signal_type is not None:
            results = [r for r in results if r.signal_type == signal_type]
        return results[-limit:]

    # -- predictions -------------------------------------------------

    def compute_prediction(
        self,
        service_name: str,
    ) -> OutagePrediction:
        """Compute outage prediction from recorded signals for a service."""
        signals = [s for s in self._signals if s.service_name == service_name]
        if not signals:
            pred = OutagePrediction(
                service_name=service_name,
                composite_score=0.0,
                probability=OutageProbability.NEGLIGIBLE,
                signal_count=0,
                recommended_action=MitigationAction.NO_ACTION,
            )
            self._predictions.append(pred)
            return pred
        total_weight = sum(s.weight for s in signals)
        if total_weight == 0:
            composite = 0.0
        else:
            composite = round(sum(s.value * s.weight for s in signals) / total_weight, 4)
        composite = max(0.0, min(1.0, composite))
        probability = self._score_to_probability(composite)
        action = self._probability_to_action(probability)
        lead_time = self._estimate_lead_time(composite)
        pred = OutagePrediction(
            service_name=service_name,
            composite_score=composite,
            probability=probability,
            signal_count=len(signals),
            recommended_action=action,
            lead_time_minutes=lead_time,
        )
        self._predictions.append(pred)
        if len(self._predictions) > self._max_records:
            self._predictions = self._predictions[-self._max_records :]
        logger.info(
            "outage_predictor.prediction_computed",
            prediction_id=pred.id,
            service_name=service_name,
            composite_score=composite,
        )
        return pred

    def get_prediction(self, prediction_id: str) -> OutagePrediction | None:
        for p in self._predictions:
            if p.id == prediction_id:
                return p
        return None

    def list_predictions(
        self,
        service_name: str | None = None,
        probability: OutageProbability | None = None,
        limit: int = 50,
    ) -> list[OutagePrediction]:
        results = list(self._predictions)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if probability is not None:
            results = [r for r in results if r.probability == probability]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def assess_lead_time(self, service_name: str) -> dict[str, Any]:
        """Assess how much lead time we have before a potential outage."""
        preds = [p for p in self._predictions if p.service_name == service_name]
        if not preds:
            return {
                "service_name": service_name,
                "lead_time_minutes": 0,
                "confidence": "none",
                "has_predictions": False,
            }
        latest = preds[-1]
        return {
            "service_name": service_name,
            "lead_time_minutes": latest.lead_time_minutes,
            "confidence": latest.probability.value,
            "composite_score": latest.composite_score,
            "has_predictions": True,
        }

    def recommend_mitigation(
        self,
        service_name: str,
    ) -> dict[str, Any]:
        """Recommend mitigation based on current prediction state."""
        preds = [p for p in self._predictions if p.service_name == service_name]
        if not preds:
            return {
                "service_name": service_name,
                "action": MitigationAction.NO_ACTION.value,
                "reason": "No predictions available",
            }
        latest = preds[-1]
        return {
            "service_name": service_name,
            "action": latest.recommended_action.value,
            "probability": latest.probability.value,
            "composite_score": latest.composite_score,
            "reason": f"Based on {latest.signal_count} signal(s)",
        }

    # -- report / stats ----------------------------------------------

    def generate_prediction_report(self) -> OutagePredictionReport:
        by_probability: dict[str, int] = {}
        for p in self._predictions:
            key = p.probability.value
            by_probability[key] = by_probability.get(key, 0) + 1
        by_signal_type: dict[str, int] = {}
        for s in self._signals:
            key = s.signal_type.value
            by_signal_type[key] = by_signal_type.get(key, 0) + 1
        by_action: dict[str, int] = {}
        for p in self._predictions:
            key = p.recommended_action.value
            by_action[key] = by_action.get(key, 0) + 1
        high_risk = list(
            {
                p.service_name
                for p in self._predictions
                if p.probability in (OutageProbability.HIGH, OutageProbability.IMMINENT)
            }
        )
        recs: list[str] = []
        if high_risk:
            recs.append(f"{len(high_risk)} service(s) at high/imminent outage risk")
        if not recs:
            recs.append("No services at elevated outage risk")
        return OutagePredictionReport(
            total_signals=len(self._signals),
            total_predictions=len(self._predictions),
            by_probability=by_probability,
            by_signal_type=by_signal_type,
            by_action=by_action,
            high_risk_services=sorted(high_risk),
            recommendations=recs,
        )

    def clear_data(self) -> int:
        count = len(self._signals) + len(self._predictions)
        self._signals.clear()
        self._predictions.clear()
        logger.info("outage_predictor.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        prob_dist: dict[str, int] = {}
        for p in self._predictions:
            key = p.probability.value
            prob_dist[key] = prob_dist.get(key, 0) + 1
        return {
            "total_signals": len(self._signals),
            "total_predictions": len(self._predictions),
            "composite_threshold": self._composite_threshold,
            "probability_distribution": prob_dist,
        }

    # -- internal helpers --------------------------------------------

    def _score_to_probability(self, score: float) -> OutageProbability:
        if score >= 0.9:
            return OutageProbability.IMMINENT
        if score >= 0.75:
            return OutageProbability.HIGH
        if score >= 0.5:
            return OutageProbability.ELEVATED
        if score >= 0.25:
            return OutageProbability.LOW
        return OutageProbability.NEGLIGIBLE

    def _probability_to_action(self, prob: OutageProbability) -> MitigationAction:
        mapping = {
            OutageProbability.NEGLIGIBLE: MitigationAction.NO_ACTION,
            OutageProbability.LOW: MitigationAction.INCREASE_MONITORING,
            OutageProbability.ELEVATED: MitigationAction.PRE_SCALE,
            OutageProbability.HIGH: MitigationAction.FREEZE_CHANGES,
            OutageProbability.IMMINENT: MitigationAction.ACTIVATE_INCIDENT,
        }
        return mapping.get(prob, MitigationAction.NO_ACTION)

    def _estimate_lead_time(self, score: float) -> int:
        if score >= 0.9:
            return 5
        if score >= 0.75:
            return 15
        if score >= 0.5:
            return 30
        if score >= 0.25:
            return 60
        return 120
