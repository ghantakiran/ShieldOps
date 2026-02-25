"""Cost Anomaly Predictor — predict future cost spikes
from leading infrastructure signals."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CostSpikeRisk(StrEnum):
    NEGLIGIBLE = "negligible"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    IMMINENT = "imminent"


class LeadingIndicator(StrEnum):
    RESOURCE_PROVISIONING = "resource_provisioning"
    AUTOSCALER_ACTIVITY = "autoscaler_activity"
    TRAFFIC_SURGE = "traffic_surge"
    NEW_DEPLOYMENT = "new_deployment"
    DATA_TRANSFER_SPIKE = "data_transfer_spike"


class PreventionAction(StrEnum):
    NO_ACTION = "no_action"
    ALERT_FINOPS = "alert_finops"
    APPLY_BUDGET_CAP = "apply_budget_cap"
    THROTTLE_SCALING = "throttle_scaling"
    EMERGENCY_REVIEW = "emergency_review"


# --- Models ---


class IndicatorReading(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    indicator: LeadingIndicator = LeadingIndicator.RESOURCE_PROVISIONING
    value: float = 0.0
    baseline_value: float = 0.0
    deviation_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CostSpikePrediction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    predicted_spike_usd: float = 0.0
    risk_level: CostSpikeRisk = CostSpikeRisk.NEGLIGIBLE
    indicator_count: int = 0
    recommended_action: PreventionAction = PreventionAction.NO_ACTION
    preventable_spend_usd: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CostPredictionReport(BaseModel):
    total_indicators: int = 0
    total_predictions: int = 0
    total_predicted_spend_usd: float = 0.0
    total_preventable_usd: float = 0.0
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_indicator: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    high_risk_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostAnomalyPredictor:
    """Predict future cost spikes from leading
    infrastructure signals."""

    def __init__(
        self,
        max_records: int = 300000,
        spike_threshold_usd: float = 1000.0,
    ) -> None:
        self._max_records = max_records
        self._spike_threshold_usd = spike_threshold_usd
        self._indicators: list[IndicatorReading] = []
        self._predictions: list[CostSpikePrediction] = []
        logger.info(
            "cost_anomaly_predictor.initialized",
            max_records=max_records,
            spike_threshold_usd=spike_threshold_usd,
        )

    # -- indicators --------------------------------------------------

    def record_indicator(
        self,
        service_name: str,
        indicator: LeadingIndicator = LeadingIndicator.RESOURCE_PROVISIONING,
        value: float = 0.0,
        baseline_value: float = 0.0,
        **kw: Any,
    ) -> IndicatorReading:
        deviation = (
            round(((value - baseline_value) / baseline_value) * 100, 2)
            if baseline_value > 0
            else 0.0
        )
        reading = IndicatorReading(
            service_name=service_name,
            indicator=indicator,
            value=value,
            baseline_value=baseline_value,
            deviation_pct=deviation,
            **kw,
        )
        self._indicators.append(reading)
        if len(self._indicators) > self._max_records:
            self._indicators = self._indicators[-self._max_records :]
        logger.info(
            "cost_anomaly_predictor.indicator_recorded",
            indicator_id=reading.id,
            service_name=service_name,
        )
        return reading

    def get_indicator(self, indicator_id: str) -> IndicatorReading | None:
        for i in self._indicators:
            if i.id == indicator_id:
                return i
        return None

    def list_indicators(
        self,
        service_name: str | None = None,
        indicator: LeadingIndicator | None = None,
        limit: int = 50,
    ) -> list[IndicatorReading]:
        results = list(self._indicators)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if indicator is not None:
            results = [r for r in results if r.indicator == indicator]
        return results[-limit:]

    # -- predictions -------------------------------------------------

    def predict_cost_spike(
        self,
        service_name: str,
    ) -> CostSpikePrediction:
        """Predict cost spike from leading indicators for a service."""
        indicators = [i for i in self._indicators if i.service_name == service_name]
        if not indicators:
            pred = CostSpikePrediction(
                service_name=service_name,
                risk_level=CostSpikeRisk.NEGLIGIBLE,
            )
            self._predictions.append(pred)
            return pred
        avg_deviation = sum(i.deviation_pct for i in indicators) / len(indicators)
        # Estimate spike amount from deviation
        spike_usd = round(abs(avg_deviation) * self._spike_threshold_usd / 100, 2)
        risk = self._deviation_to_risk(abs(avg_deviation))
        action = self._risk_to_action(risk)
        preventable = round(spike_usd * 0.6, 2) if risk != CostSpikeRisk.NEGLIGIBLE else 0.0
        pred = CostSpikePrediction(
            service_name=service_name,
            predicted_spike_usd=spike_usd,
            risk_level=risk,
            indicator_count=len(indicators),
            recommended_action=action,
            preventable_spend_usd=preventable,
        )
        self._predictions.append(pred)
        if len(self._predictions) > self._max_records:
            self._predictions = self._predictions[-self._max_records :]
        logger.info(
            "cost_anomaly_predictor.prediction_created",
            prediction_id=pred.id,
            service_name=service_name,
            risk_level=risk.value,
        )
        return pred

    def get_prediction(self, prediction_id: str) -> CostSpikePrediction | None:
        for p in self._predictions:
            if p.id == prediction_id:
                return p
        return None

    def list_predictions(
        self,
        service_name: str | None = None,
        risk_level: CostSpikeRisk | None = None,
        limit: int = 50,
    ) -> list[CostSpikePrediction]:
        results = list(self._predictions)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if risk_level is not None:
            results = [r for r in results if r.risk_level == risk_level]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def suggest_prevention(
        self,
        service_name: str,
    ) -> dict[str, Any]:
        """Suggest prevention actions based on current predictions."""
        preds = [p for p in self._predictions if p.service_name == service_name]
        if not preds:
            return {
                "service_name": service_name,
                "action": PreventionAction.NO_ACTION.value,
                "reason": "No predictions available",
            }
        latest = preds[-1]
        return {
            "service_name": service_name,
            "action": latest.recommended_action.value,
            "risk_level": latest.risk_level.value,
            "predicted_spike_usd": latest.predicted_spike_usd,
            "reason": f"Based on {latest.indicator_count} indicator(s)",
        }

    def estimate_preventable_spend(self) -> dict[str, Any]:
        """Estimate total preventable spend across all predictions."""
        total_predicted = sum(p.predicted_spike_usd for p in self._predictions)
        total_preventable = sum(p.preventable_spend_usd for p in self._predictions)
        high_risk = [
            p
            for p in self._predictions
            if p.risk_level in (CostSpikeRisk.HIGH, CostSpikeRisk.IMMINENT)
        ]
        return {
            "total_predicted_spend_usd": round(total_predicted, 2),
            "total_preventable_usd": round(total_preventable, 2),
            "high_risk_prediction_count": len(high_risk),
            "total_predictions": len(self._predictions),
        }

    # -- report / stats ----------------------------------------------

    def generate_prediction_report(self) -> CostPredictionReport:
        by_risk: dict[str, int] = {}
        for p in self._predictions:
            key = p.risk_level.value
            by_risk[key] = by_risk.get(key, 0) + 1
        by_indicator: dict[str, int] = {}
        for i in self._indicators:
            key = i.indicator.value
            by_indicator[key] = by_indicator.get(key, 0) + 1
        by_action: dict[str, int] = {}
        for p in self._predictions:
            key = p.recommended_action.value
            by_action[key] = by_action.get(key, 0) + 1
        total_predicted = round(sum(p.predicted_spike_usd for p in self._predictions), 2)
        total_preventable = round(sum(p.preventable_spend_usd for p in self._predictions), 2)
        high_risk = list(
            {
                p.service_name
                for p in self._predictions
                if p.risk_level in (CostSpikeRisk.HIGH, CostSpikeRisk.IMMINENT)
            }
        )
        recs: list[str] = []
        if high_risk:
            recs.append(f"{len(high_risk)} service(s) at high/imminent cost spike risk")
        if total_preventable > 0:
            recs.append(f"${total_preventable:,.2f} in preventable spend identified")
        if not recs:
            recs.append("No significant cost spike risks detected")
        return CostPredictionReport(
            total_indicators=len(self._indicators),
            total_predictions=len(self._predictions),
            total_predicted_spend_usd=total_predicted,
            total_preventable_usd=total_preventable,
            by_risk=by_risk,
            by_indicator=by_indicator,
            by_action=by_action,
            high_risk_services=sorted(high_risk),
            recommendations=recs,
        )

    def clear_data(self) -> int:
        count = len(self._indicators) + len(self._predictions)
        self._indicators.clear()
        self._predictions.clear()
        logger.info("cost_anomaly_predictor.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        risk_dist: dict[str, int] = {}
        for p in self._predictions:
            key = p.risk_level.value
            risk_dist[key] = risk_dist.get(key, 0) + 1
        return {
            "total_indicators": len(self._indicators),
            "total_predictions": len(self._predictions),
            "spike_threshold_usd": self._spike_threshold_usd,
            "risk_distribution": risk_dist,
        }

    # -- internal helpers --------------------------------------------

    def _deviation_to_risk(self, deviation_pct: float) -> CostSpikeRisk:
        if deviation_pct >= 200:
            return CostSpikeRisk.IMMINENT
        if deviation_pct >= 100:
            return CostSpikeRisk.HIGH
        if deviation_pct >= 50:
            return CostSpikeRisk.MODERATE
        if deviation_pct >= 20:
            return CostSpikeRisk.LOW
        return CostSpikeRisk.NEGLIGIBLE

    def _risk_to_action(self, risk: CostSpikeRisk) -> PreventionAction:
        mapping = {
            CostSpikeRisk.NEGLIGIBLE: PreventionAction.NO_ACTION,
            CostSpikeRisk.LOW: PreventionAction.ALERT_FINOPS,
            CostSpikeRisk.MODERATE: PreventionAction.APPLY_BUDGET_CAP,
            CostSpikeRisk.HIGH: PreventionAction.THROTTLE_SCALING,
            CostSpikeRisk.IMMINENT: PreventionAction.EMERGENCY_REVIEW,
        }
        return mapping.get(risk, PreventionAction.NO_ACTION)
