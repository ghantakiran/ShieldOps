"""Anomaly Forecast Engine — predict metric anomalies before alerts."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ForecastHorizon(StrEnum):
    MINUTES_15 = "minutes_15"
    HOUR_1 = "hour_1"
    HOURS_4 = "hours_4"
    HOURS_12 = "hours_12"
    HOURS_24 = "hours_24"


class AnomalyLikelihood(StrEnum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ForecastModel(StrEnum):
    ARIMA = "arima"
    PROPHET = "prophet"
    HOLT_WINTERS = "holt_winters"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    ENSEMBLE = "ensemble"


# --- Models ---


class ForecastPoint(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    service_name: str = ""
    metric_name: str = ""
    current_value: float = 0.0
    predicted_value: float = 0.0
    anomaly_likelihood: AnomalyLikelihood = AnomalyLikelihood.VERY_LOW
    horizon: ForecastHorizon = ForecastHorizon.HOUR_1
    confidence: float = 0.0
    model: ForecastModel = ForecastModel.ARIMA
    created_at: float = Field(default_factory=time.time)


class ForecastAlert(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    forecast_id: str = ""
    service_name: str = ""
    metric_name: str = ""
    predicted_breach_at: float = 0.0
    severity: str = "warning"
    acknowledged: bool = False
    created_at: float = Field(default_factory=time.time)


class ForecastReport(BaseModel):
    total_forecasts: int = 0
    total_alerts: int = 0
    accuracy_pct: float = 0.0
    by_likelihood: dict[str, int] = Field(
        default_factory=dict,
    )
    by_horizon: dict[str, int] = Field(
        default_factory=dict,
    )
    by_model: dict[str, int] = Field(
        default_factory=dict,
    )
    upcoming_anomalies: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AnomalyForecastEngine:
    """Predict metric anomalies before they trigger alerts
    using trend analysis and seasonal patterns."""

    def __init__(
        self,
        max_forecasts: int = 200000,
        alert_threshold: float = 0.7,
    ) -> None:
        self._max_forecasts = max_forecasts
        self._alert_threshold = alert_threshold
        self._items: list[ForecastPoint] = []
        self._alerts: list[ForecastAlert] = []
        logger.info(
            "anomaly_forecast.initialized",
            max_forecasts=max_forecasts,
            alert_threshold=alert_threshold,
        )

    # -- create / get / list -----------------------------------------

    def create_forecast(
        self,
        service_name: str,
        metric_name: str,
        current_value: float = 0.0,
        predicted_value: float = 0.0,
        anomaly_likelihood: AnomalyLikelihood = (AnomalyLikelihood.VERY_LOW),
        horizon: ForecastHorizon = ForecastHorizon.HOUR_1,
        confidence: float = 0.0,
        model: ForecastModel = ForecastModel.ARIMA,
        **kw: Any,
    ) -> ForecastPoint:
        """Create a new forecast point."""
        point = ForecastPoint(
            service_name=service_name,
            metric_name=metric_name,
            current_value=current_value,
            predicted_value=predicted_value,
            anomaly_likelihood=anomaly_likelihood,
            horizon=horizon,
            confidence=confidence,
            model=model,
            **kw,
        )
        self._items.append(point)
        if len(self._items) > self._max_forecasts:
            self._items = self._items[-self._max_forecasts :]
        logger.info(
            "anomaly_forecast.created",
            forecast_id=point.id,
            service_name=service_name,
            metric_name=metric_name,
        )
        return point

    def get_forecast(
        self,
        forecast_id: str,
    ) -> ForecastPoint | None:
        """Get a forecast by ID."""
        for item in self._items:
            if item.id == forecast_id:
                return item
        return None

    def list_forecasts(
        self,
        service_name: str | None = None,
        anomaly_likelihood: AnomalyLikelihood | None = None,
        limit: int = 50,
    ) -> list[ForecastPoint]:
        """List forecasts with optional filters."""
        results = list(self._items)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if anomaly_likelihood is not None:
            results = [r for r in results if r.anomaly_likelihood == anomaly_likelihood]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def predict_anomaly(
        self,
        service_name: str,
        metric_name: str,
        values: list[float],
    ) -> ForecastPoint:
        """Predict anomaly from a list of metric values."""
        if not values:
            return self.create_forecast(
                service_name,
                metric_name,
            )
        current = values[-1]
        avg = sum(values) / len(values)
        std = (sum((v - avg) ** 2 for v in values) / len(values)) ** 0.5
        predicted = avg + (current - avg) * 0.5
        # Determine likelihood from deviation
        if std == 0:
            likelihood = AnomalyLikelihood.VERY_LOW
            conf = 1.0
        else:
            z = abs(current - avg) / std
            conf = round(min(z / 4.0, 1.0), 4)
            likelihood = self._z_to_likelihood(z)
        return self.create_forecast(
            service_name=service_name,
            metric_name=metric_name,
            current_value=current,
            predicted_value=round(predicted, 4),
            anomaly_likelihood=likelihood,
            confidence=conf,
        )

    def create_alert(
        self,
        forecast_id: str,
        severity: str = "warning",
    ) -> ForecastAlert | None:
        """Create an alert from a forecast point."""
        fp = self.get_forecast(forecast_id)
        if fp is None:
            return None
        alert = ForecastAlert(
            forecast_id=forecast_id,
            service_name=fp.service_name,
            metric_name=fp.metric_name,
            predicted_breach_at=fp.predicted_value,
            severity=severity,
        )
        self._alerts.append(alert)
        logger.info(
            "anomaly_forecast.alert_created",
            alert_id=alert.id,
            forecast_id=forecast_id,
        )
        return alert

    def evaluate_accuracy(self) -> float:
        """Evaluate forecast accuracy as percentage."""
        if not self._items:
            return 0.0
        high_conf = [p for p in self._items if p.confidence >= self._alert_threshold]
        if not high_conf:
            return 100.0
        accurate = sum(
            1
            for p in high_conf
            if p.anomaly_likelihood
            in (
                AnomalyLikelihood.HIGH,
                AnomalyLikelihood.VERY_HIGH,
            )
        )
        return round(accurate / len(high_conf) * 100, 2)

    def identify_trending_metrics(
        self,
    ) -> list[dict[str, Any]]:
        """Identify metrics trending toward anomalies."""
        by_key: dict[str, list[ForecastPoint]] = {}
        for p in self._items:
            key = f"{p.service_name}:{p.metric_name}"
            by_key.setdefault(key, []).append(p)
        trending: list[dict[str, Any]] = []
        for key, points in sorted(by_key.items()):
            if len(points) < 2:
                continue
            first_half = points[: len(points) // 2]
            second_half = points[len(points) // 2 :]
            avg_first = sum(p.predicted_value for p in first_half) / len(first_half)
            avg_second = sum(p.predicted_value for p in second_half) / len(second_half)
            if avg_second > avg_first * 1.2:
                svc, metric = key.split(":", 1)
                trending.append(
                    {
                        "service_name": svc,
                        "metric_name": metric,
                        "trend": "increasing",
                        "point_count": len(points),
                    }
                )
        return trending

    def rank_by_risk(self) -> list[ForecastPoint]:
        """Rank forecasts by risk (likelihood + confidence)."""
        likelihood_order = {
            AnomalyLikelihood.VERY_LOW: 0,
            AnomalyLikelihood.LOW: 1,
            AnomalyLikelihood.MODERATE: 2,
            AnomalyLikelihood.HIGH: 3,
            AnomalyLikelihood.VERY_HIGH: 4,
        }
        scored = list(self._items)
        scored.sort(
            key=lambda p: (
                likelihood_order.get(p.anomaly_likelihood, 0),
                p.confidence,
            ),
            reverse=True,
        )
        return scored

    # -- report / stats ----------------------------------------------

    def generate_forecast_report(self) -> ForecastReport:
        """Generate a comprehensive forecast report."""
        by_likelihood: dict[str, int] = {}
        for p in self._items:
            key = p.anomaly_likelihood.value
            by_likelihood[key] = by_likelihood.get(key, 0) + 1
        by_horizon: dict[str, int] = {}
        for p in self._items:
            key = p.horizon.value
            by_horizon[key] = by_horizon.get(key, 0) + 1
        by_model: dict[str, int] = {}
        for p in self._items:
            key = p.model.value
            by_model[key] = by_model.get(key, 0) + 1
        upcoming = [
            p.id
            for p in self._items
            if p.anomaly_likelihood
            in (
                AnomalyLikelihood.HIGH,
                AnomalyLikelihood.VERY_HIGH,
            )
        ]
        recs = self._build_recommendations(
            by_likelihood,
            len(self._alerts),
        )
        return ForecastReport(
            total_forecasts=len(self._items),
            total_alerts=len(self._alerts),
            accuracy_pct=self.evaluate_accuracy(),
            by_likelihood=by_likelihood,
            by_horizon=by_horizon,
            by_model=by_model,
            upcoming_anomalies=upcoming,
            recommendations=recs,
        )

    def clear_data(self) -> int:
        """Clear all data. Returns count cleared."""
        count = len(self._items)
        self._items.clear()
        self._alerts.clear()
        logger.info("anomaly_forecast.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        likelihood_dist: dict[str, int] = {}
        for p in self._items:
            key = p.anomaly_likelihood.value
            likelihood_dist[key] = likelihood_dist.get(key, 0) + 1
        return {
            "total_forecasts": len(self._items),
            "total_alerts": len(self._alerts),
            "alert_threshold": self._alert_threshold,
            "likelihood_distribution": likelihood_dist,
        }

    # -- internal helpers --------------------------------------------

    def _z_to_likelihood(
        self,
        z: float,
    ) -> AnomalyLikelihood:
        if z >= 3.0:
            return AnomalyLikelihood.VERY_HIGH
        if z >= 2.0:
            return AnomalyLikelihood.HIGH
        if z >= 1.5:
            return AnomalyLikelihood.MODERATE
        if z >= 1.0:
            return AnomalyLikelihood.LOW
        return AnomalyLikelihood.VERY_LOW

    def _build_recommendations(
        self,
        by_likelihood: dict[str, int],
        total_alerts: int,
    ) -> list[str]:
        recs: list[str] = []
        high = by_likelihood.get(AnomalyLikelihood.VERY_HIGH.value, 0)
        if high > 0:
            recs.append(f"{high} very-high likelihood forecast(s) — investigate immediately")
        if total_alerts > 50:
            recs.append("High alert volume — review thresholds")
        if not recs:
            recs.append("Anomaly forecasts within normal range")
        return recs
