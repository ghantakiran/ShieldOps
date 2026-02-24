"""SLO Burn Rate Predictor — predictive SLO violation forecasting, dynamic alert thresholds."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BurnSeverity(StrEnum):
    SAFE = "safe"
    WATCH = "watch"
    WARNING = "warning"
    DANGER = "danger"
    BREACH = "breach"


class PredictionHorizon(StrEnum):
    ONE_HOUR = "one_hour"
    SIX_HOURS = "six_hours"
    ONE_DAY = "one_day"
    ONE_WEEK = "one_week"
    ONE_MONTH = "one_month"


class AlertSensitivity(StrEnum):
    RELAXED = "relaxed"
    NORMAL = "normal"
    ELEVATED = "elevated"
    AGGRESSIVE = "aggressive"


# --- Models ---


class SLOTarget(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    service: str = ""
    target_pct: float = 99.9
    window_days: int = 30
    error_budget_total: float = 0.0
    error_budget_remaining: float = 0.0
    current_burn_rate: float = 0.0
    total_events: int = 0
    error_events: int = 0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class BurnPrediction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_id: str = ""
    horizon: PredictionHorizon = PredictionHorizon.ONE_DAY
    predicted_burn_rate: float = 0.0
    severity: BurnSeverity = BurnSeverity.SAFE
    budget_exhaustion_hours: float | None = None
    confidence: float = 0.0
    predicted_at: float = Field(default_factory=time.time)


class ViolationForecast(BaseModel):
    slo_id: str = ""
    slo_name: str = ""
    service: str = ""
    current_burn_rate: float = 0.0
    hours_until_breach: float | None = None
    severity: BurnSeverity = BurnSeverity.SAFE
    recommendation: str = ""


# --- Engine ---


class SLOBurnRatePredictor:
    """Predictive SLO violation forecasting, dynamic alert thresholds."""

    def __init__(
        self,
        max_slos: int = 5000,
        forecast_hours: int = 24,
    ) -> None:
        self._max_slos = max_slos
        self._forecast_hours = forecast_hours
        self._slos: list[SLOTarget] = []
        self._predictions: list[BurnPrediction] = []
        self._deployments: list[dict[str, Any]] = []
        logger.info(
            "burn_predictor.initialized",
            max_slos=max_slos,
            forecast_hours=forecast_hours,
        )

    def register_slo(
        self,
        name: str,
        service: str = "",
        target_pct: float = 99.9,
        window_days: int = 30,
    ) -> SLOTarget:
        budget = round((100.0 - target_pct) / 100.0 * window_days * 24 * 60, 2)  # error minutes
        slo = SLOTarget(
            name=name,
            service=service,
            target_pct=target_pct,
            window_days=window_days,
            error_budget_total=budget,
            error_budget_remaining=budget,
        )
        self._slos.append(slo)
        if len(self._slos) > self._max_slos:
            self._slos = self._slos[-self._max_slos :]
        logger.info(
            "burn_predictor.slo_registered",
            slo_id=slo.id,
            name=name,
            target_pct=target_pct,
        )
        return slo

    def get_slo(self, slo_id: str) -> SLOTarget | None:
        for s in self._slos:
            if s.id == slo_id:
                return s
        return None

    def list_slos(
        self,
        service: str | None = None,
        limit: int = 100,
    ) -> list[SLOTarget]:
        results = list(self._slos)
        if service is not None:
            results = [s for s in results if s.service == service]
        return results[-limit:]

    def record_error_event(
        self,
        slo_id: str,
        error_count: int = 1,
        total_count: int = 1,
    ) -> dict[str, Any]:
        slo = self.get_slo(slo_id)
        if slo is None:
            return {"error": "slo_not_found"}
        slo.error_events += error_count
        slo.total_events += total_count
        # Update burn rate
        if slo.total_events > 0:
            observed_error_rate = slo.error_events / slo.total_events
            allowed_error_rate = (100.0 - slo.target_pct) / 100.0
            slo.current_burn_rate = round(
                observed_error_rate / allowed_error_rate if allowed_error_rate > 0 else 0.0, 3
            )
        # Update remaining budget
        consumed = slo.error_events / max(slo.total_events, 1) * slo.error_budget_total
        slo.error_budget_remaining = round(max(0.0, slo.error_budget_total - consumed), 2)
        slo.updated_at = time.time()
        return {
            "slo_id": slo_id,
            "burn_rate": slo.current_burn_rate,
            "budget_remaining": slo.error_budget_remaining,
        }

    def predict_burn(
        self,
        slo_id: str,
        horizon: PredictionHorizon = PredictionHorizon.ONE_DAY,
    ) -> BurnPrediction | None:
        slo = self.get_slo(slo_id)
        if slo is None:
            return None
        # Simple linear prediction
        predicted_rate = slo.current_burn_rate
        # Determine severity
        if predicted_rate >= 10.0:
            severity = BurnSeverity.BREACH
        elif predicted_rate >= 5.0:
            severity = BurnSeverity.DANGER
        elif predicted_rate >= 2.0:
            severity = BurnSeverity.WARNING
        elif predicted_rate >= 1.0:
            severity = BurnSeverity.WATCH
        else:
            severity = BurnSeverity.SAFE
        # Estimate hours until budget exhaustion
        if predicted_rate > 0 and slo.error_budget_remaining > 0:
            hours = round(slo.error_budget_remaining / (predicted_rate * 0.1 + 0.001), 1)
        else:
            hours = None
        prediction = BurnPrediction(
            slo_id=slo_id,
            horizon=horizon,
            predicted_burn_rate=predicted_rate,
            severity=severity,
            budget_exhaustion_hours=hours,
            confidence=min(0.95, slo.total_events / 1000) if slo.total_events > 0 else 0.0,
        )
        self._predictions.append(prediction)
        return prediction

    def forecast_violation(self, slo_id: str) -> ViolationForecast | None:
        slo = self.get_slo(slo_id)
        if slo is None:
            return None
        prediction = self.predict_burn(slo_id)
        if prediction is None:
            return None
        if prediction.severity == BurnSeverity.BREACH:
            rec = "SLO breached — immediate action required"
        elif prediction.severity == BurnSeverity.DANGER:
            rec = "SLO at risk — reduce error rate immediately"
        elif prediction.severity == BurnSeverity.WARNING:
            rec = "Elevated burn rate — investigate contributing factors"
        elif prediction.severity == BurnSeverity.WATCH:
            rec = "Monitor burn rate trend closely"
        else:
            rec = "SLO healthy — no action needed"
        return ViolationForecast(
            slo_id=slo_id,
            slo_name=slo.name,
            service=slo.service,
            current_burn_rate=slo.current_burn_rate,
            hours_until_breach=prediction.budget_exhaustion_hours,
            severity=prediction.severity,
            recommendation=rec,
        )

    def get_budget_status(self, slo_id: str) -> dict[str, Any] | None:
        slo = self.get_slo(slo_id)
        if slo is None:
            return None
        consumed_pct = (
            round((1 - slo.error_budget_remaining / slo.error_budget_total) * 100, 1)
            if slo.error_budget_total > 0
            else 0.0
        )
        return {
            "slo_id": slo.id,
            "name": slo.name,
            "budget_total": slo.error_budget_total,
            "budget_remaining": slo.error_budget_remaining,
            "consumed_pct": consumed_pct,
            "burn_rate": slo.current_burn_rate,
        }

    def correlate_deployments(
        self,
        slo_id: str,
        deployment_time: float,
        deployment_id: str = "",
    ) -> dict[str, Any]:
        slo = self.get_slo(slo_id)
        if slo is None:
            return {"error": "slo_not_found"}
        self._deployments.append(
            {
                "slo_id": slo_id,
                "deployment_id": deployment_id,
                "deployment_time": deployment_time,
                "burn_rate_at_deploy": slo.current_burn_rate,
            }
        )
        return {
            "slo_id": slo_id,
            "deployment_id": deployment_id,
            "burn_rate_at_deploy": slo.current_burn_rate,
            "correlated": True,
        }

    def get_breach_risk(self, limit: int = 10) -> list[dict[str, Any]]:
        risks: list[dict[str, Any]] = []
        for slo in self._slos:
            if slo.current_burn_rate >= 1.0:
                risks.append(
                    {
                        "slo_id": slo.id,
                        "name": slo.name,
                        "service": slo.service,
                        "burn_rate": slo.current_burn_rate,
                        "budget_remaining": slo.error_budget_remaining,
                    }
                )
        risks.sort(key=lambda r: r["burn_rate"], reverse=True)
        return risks[:limit]

    def get_stats(self) -> dict[str, Any]:
        burn_rates = [s.current_burn_rate for s in self._slos]
        avg_burn = round(sum(burn_rates) / len(burn_rates), 3) if burn_rates else 0.0
        at_risk = sum(1 for s in self._slos if s.current_burn_rate >= 1.0)
        return {
            "total_slos": len(self._slos),
            "total_predictions": len(self._predictions),
            "avg_burn_rate": avg_burn,
            "slos_at_risk": at_risk,
            "total_deployments_correlated": len(self._deployments),
        }
